# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections import namedtuple
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from bamboo_engine.eri import ScheduleType

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.case_types import (
    CHILD_START_LOST,
    EXECUTE_DISPATCH_LOST,
    PARENT_WAKEUP_LOST,
    POLL_DISPATCH_LOST,
)
from pipeline.contrib.diagnostics.cases import resolve_case
from pipeline.contrib.diagnostics.cursor import chunks
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.progress import root_states
from pipeline.contrib.diagnostics.types import DiagnosticHit
from pipeline.engine import states
from pipeline.eri.models import Node, Process, Schedule, State

POLL = ScheduleType.POLL.value
FORK_GATEWAY_TYPES = ("ParallelGateway", "ConditionalParallelGateway")

SignatureContext = namedtuple(
    "SignatureContext", ["now", "roots", "states", "schedules", "nodes", "parents", "live_children"]
)


def build_context(processes, now=None):
    """按一页进程批量读出判定所需的根流程状态、节点状态、调度、节点详情与父进程，避免逐个进程查库。"""
    parents = {}
    parent_ids = {process.parent_id for process in processes if process.parent_id and process.parent_id > 0}
    for chunk in chunks(parent_ids):
        for parent in Process.objects.defer("pipeline_stack").filter(id__in=chunk):
            parents[parent.id] = parent

    node_ids = {process.current_node_id for process in processes if not process.dead and process.current_node_id}
    node_ids.update(parent.current_node_id for parent in parents.values() if parent.current_node_id)
    state_map, schedule_map, node_map = {}, {}, {}
    for chunk in chunks(node_ids):
        for state in State.objects.filter(node_id__in=chunk):
            state_map[state.node_id] = state
        for schedule in Schedule.objects.filter(node_id__in=chunk):
            schedule_map[(schedule.node_id, schedule.version)] = schedule
        for node in Node.objects.filter(node_id__in=chunk):
            node_map.setdefault(node.node_id, json.loads(node.detail))

    live_children = {}
    for chunk in chunks(parents):
        rows = (
            Process.objects.filter(parent_id__in=chunk, dead=False)
            .values("parent_id")
            .annotate(live=Count("id"))
            .order_by()
        )
        live_children.update({row["parent_id"]: row["live"] for row in rows})

    roots = {}
    for chunk in chunks({process.root_pipeline_id for process in processes}):
        roots.update(root_states(chunk))
    return SignatureContext(now or timezone.now(), roots, state_map, schedule_map, node_map, parents, live_children)


def _cutoff(ctx, seconds):
    return ctx.now - timedelta(seconds=seconds)


def _parked(process):
    return bool(process.suspended or process.frozen)


def _asleep_alive(process):
    return not process.dead and process.asleep and not _parked(process) and bool(process.current_node_id)


def _root_running(process, ctx):
    return ctx.roots.get(process.root_pipeline_id) == states.RUNNING


def _hit(
    stuck_type,
    signature,
    severity,
    process,
    node_id,
    version,
    derived_message,
    message,
    extra_evidence=None,
    related_extra=None,
):
    evidence = {
        "signature": signature,
        "process_id": process.id,
        "node_id": node_id,
        "state_version": version,
        "last_heartbeat": process.last_heartbeat.isoformat(),
        "derived_message": derived_message,
    }
    evidence.update(extra_evidence or {})
    related = {"root_pipeline_id": process.root_pipeline_id, "process_id": process.id, "node_id": node_id}
    related.update(related_extra or {})
    return DiagnosticHit(
        type=stuck_type,
        severity=severity,
        confidence=0.95,
        evidence=evidence,
        related_objects=related,
        recommended_actions=["inspect_node_runtime_readiness"],
        forbidden_actions=[],
        message=message,
    )


def detect_execute_dispatch_lost(process, ctx):
    """S1：调度已把节点置为完成，但后继节点的执行消息没有被消费，进程仍睡在已完成的节点上。"""
    if not _asleep_alive(process):
        return None
    node_id = process.current_node_id
    detail = ctx.nodes.get(node_id) or {}
    state = ctx.states.get(node_id)
    if detail.get("type") != "ServiceActivity" or detail.get("reserve_rollback"):
        return None
    if state is None or state.name != states.FINISHED or state.archived_time is None:
        return None
    # 调度在置完成前会先刷新心跳，所以正常情况下完成时间严格晚于心跳；相等时无法与上一轮循环残留区分，不判
    if state.archived_time <= process.last_heartbeat:
        return None
    if state.archived_time > _cutoff(ctx, conf.signature_fast_threshold_seconds()):
        return None
    targets = list((detail.get("targets") or {}).values())
    next_node_id = targets[0] if len(targets) == 1 else ""
    return _hit(
        EXECUTE_DISPATCH_LOST,
        "S1",
        "critical",
        process,
        node_id,
        state.version,
        derived_message="execute(process_id={}, node_id={})".format(process.id, next_node_id),
        message="节点已完成，但后继节点的执行消息没有被消费",
        extra_evidence={"archived_time": state.archived_time.isoformat()},
        related_extra={"next_node_ids": targets},
    )


def detect_poll_dispatch_lost(process, ctx, continuation):
    """S2（continuation=False）：首次轮询消息没有被消费；S3（continuation=True）：轮询续派消息没有被消费。"""
    if not _asleep_alive(process):
        return None
    node_id = process.current_node_id
    state = ctx.states.get(node_id)
    if state is None or state.name != states.RUNNING:
        return None
    schedule = ctx.schedules.get((node_id, state.version))
    if schedule is None or schedule.type != POLL or schedule.finished or schedule.expired or schedule.scheduling:
        return None
    detail = ctx.nodes.get(node_id) or {}
    if continuation:
        if schedule.schedule_times < 1 or detail.get("code") in conf.poll_exclude_codes():
            return None
        signature, severity, threshold = "S3", "warning", conf.signature_slow_threshold_seconds()
        message = "轮询续派消息没有被消费"
    else:
        if schedule.schedule_times != 0:
            return None
        signature, severity, threshold = "S2", "critical", conf.signature_fast_threshold_seconds()
        message = "首次轮询消息没有被消费"
    if process.last_heartbeat > _cutoff(ctx, threshold):
        return None
    return _hit(
        POLL_DISPATCH_LOST,
        signature,
        severity,
        process,
        node_id,
        state.version,
        derived_message="schedule(process_id={}, node_id={}, schedule_id={})".format(process.id, node_id, schedule.id),
        message=message,
        extra_evidence={
            "schedule_id": schedule.id,
            "schedule_times": schedule.schedule_times,
            "code": detail.get("code", ""),
        },
        related_extra={"schedule_id": schedule.id},
    )


def detect_parent_wakeup_lost(child, ctx):
    """S5：最后一个子进程已把父进程的 ACK 记满（need_ack 归为 -1），但唤醒父进程的执行消息没有被消费。"""
    parent = ctx.parents.get(child.parent_id)
    if not child.dead or parent is None or not _asleep_alive(parent):
        return None
    state = ctx.states.get(parent.current_node_id)
    # 循环里上一轮的子进程仍以同一父进程、同一终点保持 dead；本轮子进程的心跳都严格晚于网关本轮的完成时间
    if state is None or state.archived_time is None or child.last_heartbeat <= state.archived_time:
        return None
    if parent.need_ack != -1 or ctx.live_children.get(parent.id, 0) != 0:
        return None
    detail = ctx.nodes.get(parent.current_node_id) or {}
    if detail.get("type") not in FORK_GATEWAY_TYPES or detail.get("converge_gateway_id") != child.destination_id:
        return None
    if child.last_heartbeat > _cutoff(ctx, conf.signature_fast_threshold_seconds()):
        return None
    return _hit(
        PARENT_WAKEUP_LOST,
        "S5",
        "critical",
        parent,
        parent.current_node_id,
        state.version,
        derived_message="execute(process_id={}, node_id={})".format(parent.id, child.destination_id),
        message="并行分支已全部结束，但唤醒父进程的执行消息没有被消费",
        extra_evidence={"child_process_id": child.id, "child_last_heartbeat": child.last_heartbeat.isoformat()},
        related_extra={"converge_gateway_id": child.destination_id},
    )


def detect_child_start_lost(child, ctx):
    """S6：父进程已 fork 并开始等待，但启动子进程的执行消息没有被消费，子进程从未跑过。"""
    parent = ctx.parents.get(child.parent_id)
    if not _asleep_alive(child) or parent is None or not _asleep_alive(parent) or parent.need_ack <= 0:
        return None
    node_id = child.current_node_id
    state = ctx.states.get(node_id)
    if state is not None:
        # 只接受上一轮循环残留的完成状态：它早于子进程创建时写下的唯一一次心跳；相等时无法区分，不判
        leftover = state.name == states.FINISHED and state.archived_time is not None
        if not leftover or state.archived_time >= child.last_heartbeat:
            return None
    if child.last_heartbeat > _cutoff(ctx, conf.signature_fast_threshold_seconds()):
        return None
    return _hit(
        CHILD_START_LOST,
        "S6",
        "critical",
        child,
        node_id,
        state.version if state is not None else "",
        derived_message="execute(process_id={}, node_id={})".format(child.id, node_id),
        message="子进程已创建，但启动它的执行消息没有被消费",
        extra_evidence={"parent_process_id": parent.id, "destination_id": child.destination_id},
        related_extra={"parent_process_id": parent.id},
    )


def evaluate(processes, ctx, slow):
    """返回 [(触发进程, 命中)]。已结束的子进程只用来发现父进程没被唤醒；慢档额外检查轮询续派。"""
    hits = []
    for process in processes:
        if not _root_running(process, ctx):
            continue
        if process.dead:
            found = [detect_parent_wakeup_lost(process, ctx)]
        else:
            found = [
                detect_execute_dispatch_lost(process, ctx),
                detect_poll_dispatch_lost(process, ctx, continuation=False),
                detect_child_start_lost(process, ctx),
            ]
            if slow:
                found.append(detect_poll_dispatch_lost(process, ctx, continuation=True))
        hits.extend((process, hit) for hit in found if hit is not None)
    return hits


def hit_identity(hit):
    related = hit.related_objects
    return hit.type, related["process_id"], related["node_id"], hit.evidence.get("state_version", "")


def _trigger_process_id(case):
    if case.stuck_type == PARENT_WAKEUP_LOST:
        return (case.evidence or {}).get("child_process_id")
    return (case.related_objects or {}).get("process_id")


def still_holds(case):
    """用案例里的触发进程重新判定；形态、进程、节点、版本都一致才算仍然卡着。"""
    process_id = _trigger_process_id(case)
    processes = list(Process.objects.defer("pipeline_stack").filter(id=process_id)) if process_id else []
    if not processes:
        return False
    identity = (
        case.stuck_type,
        (case.related_objects or {}).get("process_id"),
        case.node_id,
        (case.evidence or {}).get("state_version", ""),
    )
    hits = evaluate(processes, build_context(processes), slow=True)
    return any(hit_identity(hit) == identity for _process, hit in hits)


def close_resolved_signature_cases(stuck_types, holds=still_holds, now=None, batch=None):
    """按 updated_at 轮转复核一批未关闭的形态案例：不再成立的关闭，仍成立的刷新 updated_at 排到队尾。返回关闭数。"""
    now = now or timezone.now()
    batch = conf.signature_close_batch() if batch is None else batch
    cases = list(
        DiagnosticCase.objects.filter(status=DiagnosticCase.STATUS_OPEN, stuck_type__in=list(stuck_types)).order_by(
            "updated_at", "id"
        )[:batch]
    )
    closed = 0
    for case in cases:
        if holds(case):
            DiagnosticCase.objects.filter(id=case.id).update(updated_at=now)
        else:
            resolve_case(case, now=now)
            closed += 1
    return closed
