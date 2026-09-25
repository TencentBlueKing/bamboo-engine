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

import time
from collections import Counter

from django.utils import timezone

from bamboo_engine.eri import ScheduleType

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.case_types import CALLBACK_DISPATCH_LOST
from pipeline.contrib.diagnostics.cases import upsert_case
from pipeline.contrib.diagnostics.cursor import chunks, load_cursor, save_cursor
from pipeline.contrib.diagnostics.metrics import observe_hit, record_scan_report
from pipeline.contrib.diagnostics.progress import root_states
from pipeline.contrib.diagnostics.signatures import close_resolved_signature_cases
from pipeline.contrib.diagnostics.types import DiagnosticHit, ScanReport
from pipeline.engine import states
from pipeline.eri.models import CallbackData, Schedule, State

CURSOR_NAME = "callback_watermark"
BACKFILL_NAME = "callback_backfill"

OUTCOME_PENDING = "pending"
OUTCOME_SCHEDULING = "scheduling"
OUTCOME_CONSUMED = "consumed"
OUTCOME_STALE_VERSION = "stale_version"
OUTCOME_NO_SCHEDULE = "no_schedule"
OUTCOME_EXPIRED = "expired"
OUTCOME_MULTIPLE = "multiple_callback"
OUTCOME_NOT_CALLBACK = "not_callback"
OUTCOME_ROOT_INACTIVE = "root_inactive"
WATCHED = (OUTCOME_PENDING, OUTCOME_SCHEDULING)


def classify(callback, state, schedule, root_state=None):
    """判定一条回调数据当前的处境；只有 OUTCOME_PENDING / OUTCOME_SCHEDULING 需要继续观察。"""
    if state is None or state.version != callback.version:
        return OUTCOME_STALE_VERSION
    if schedule is None:
        return OUTCOME_NO_SCHEDULE
    if schedule.finished or state.name != states.RUNNING:
        return OUTCOME_CONSUMED
    if schedule.expired:
        return OUTCOME_EXPIRED
    # 多次回调的调度要等全部回调到齐才完成，单条回调是否被消费无从判断，只计数
    if schedule.type == ScheduleType.MULTIPLE_CALLBACK.value:
        return OUTCOME_MULTIPLE
    if schedule.type != ScheduleType.CALLBACK.value:
        return OUTCOME_NOT_CALLBACK
    if schedule.schedule_times > 0:
        return OUTCOME_CONSUMED
    if root_state != states.RUNNING:
        return OUTCOME_ROOT_INACTIVE
    if schedule.scheduling:
        return OUTCOME_SCHEDULING
    return OUTCOME_PENDING


def _judge(callbacks):
    """{callback_id: (outcome, state, schedule)}，按节点批量读状态与调度。"""
    node_ids = {callback.node_id for callback in callbacks}
    state_map, schedule_map, root_map = {}, {}, {}
    for chunk in chunks(node_ids):
        for state in State.objects.filter(node_id__in=chunk):
            state_map[state.node_id] = state
        for schedule in Schedule.objects.filter(node_id__in=chunk):
            schedule_map[(schedule.node_id, schedule.version)] = schedule
    for chunk in chunks({state.root_id for state in state_map.values() if state.root_id}):
        root_map.update(root_states(chunk))
    judged = {}
    for callback in callbacks:
        state = state_map.get(callback.node_id)
        schedule = schedule_map.get((callback.node_id, callback.version))
        root_state = root_map.get(state.root_id) if state is not None else None
        judged[callback.id] = (classify(callback, state, schedule, root_state), state, schedule)
    return judged


def _load(ids):
    callbacks = []
    for chunk in chunks(ids):
        callbacks.extend(CallbackData.objects.defer("data").filter(id__in=chunk).order_by("id"))
    return callbacks


def _settle(pending, now_ts, confirm_seconds, pending_max_seconds):
    """重判待确认的回调，返回 (确认丢失的 [(callback, state, schedule, age)], 仍需观察的 pending, 结果计数)。

    first_seen 为 None 表示回扫：数据年龄未知，按当前状态直接判定，不等确认窗口。
    """
    callbacks = _load(int(key) for key in pending)
    judged = _judge(callbacks)
    lost, keep, outcomes = [], {}, Counter()
    outcomes["missing"] = len(pending) - len(callbacks)
    for callback in callbacks:
        outcome, state, schedule = judged[callback.id]
        outcomes[outcome] += 1
        if outcome not in WATCHED:
            continue
        first_seen = pending[str(callback.id)]
        age = None if first_seen is None else now_ts - first_seen
        if outcome == OUTCOME_PENDING and (age is None or age > confirm_seconds):
            lost.append((callback, state, schedule, age))
        elif age is not None and age >= pending_max_seconds:
            outcomes["watch_timeout"] += 1
        else:
            keep[str(callback.id)] = first_seen
    return lost, keep, outcomes


def _callback_hit(callback, state, schedule, age):
    return DiagnosticHit(
        type=CALLBACK_DISPATCH_LOST,
        severity="critical",
        confidence=0.95,
        evidence={
            "signature": "S4",
            "callback_data_id": callback.id,
            "process_id": schedule.process_id,
            "node_id": callback.node_id,
            "state_version": callback.version,
            "schedule_id": schedule.id,
            "pending_seconds": None if age is None else int(age),
            "derived_message": "schedule(process_id={}, node_id={}, schedule_id={}, callback_data_id={})".format(
                schedule.process_id, callback.node_id, schedule.id, callback.id
            ),
        },
        related_objects={
            "root_pipeline_id": state.root_id,
            "process_id": schedule.process_id,
            "node_id": callback.node_id,
            "schedule_id": schedule.id,
            "callback_data_id": callback.id,
        },
        recommended_actions=["replay_callback_data"],
        forbidden_actions=[],
        message="回调数据已落库，但对应的调度没有消费它",
    )


def _emit(lost, dry_run):
    hits, cases = [], 0
    for callback, state, schedule, age in lost:
        hit = _callback_hit(callback, state, schedule, age)
        hits.append((state.root_id, callback.node_id, hit))
        if dry_run:
            continue
        case = upsert_case(state.root_id, callback.node_id, hit)
        if case is not None:
            cases += 1
            if case.hit_count == 1:
                observe_hit(CALLBACK_DISPATCH_LOST, age or 0)
    return hits, cases


def _still_pending(case):
    callback_id = (case.evidence or {}).get("callback_data_id")
    callbacks = _load([callback_id]) if callback_id else []
    if not callbacks:
        return False
    outcome, _state, _schedule = _judge(callbacks)[callbacks[0].id]
    return outcome in WATCHED


def scan_callbacks(now=None, dry_run=False, max_rows=None, force=False):
    """推进回调水位：确认上一轮留下的待观察回调，再把两轮之前落库、仍未被消费的新回调放进待观察集合。"""
    if not (force or conf.callback_scan_enabled()):
        return None
    now = now or timezone.now()
    now_ts = now.timestamp()
    max_rows = conf.callback_max_rows() if max_rows is None else max_rows
    cursor = load_cursor(CURSOR_NAME)
    extra = dict(cursor.extra) if cursor is not None else {}
    current_max = CallbackData.objects.order_by("-id").values_list("id", flat=True).first() or 0
    # 首次运行从当前最大 id 开始，存量回调用 backfill_callbacks 单独预演
    position = cursor.position_id if cursor is not None else current_max
    marks = list(extra.get("high_marks") or [])

    lost, pending, outcomes = _settle(
        dict(extra.get("pending") or {}), now_ts, conf.callback_confirm_seconds(), conf.callback_pending_max_seconds()
    )

    upper = marks[0] if len(marks) >= 2 else position
    rows = []
    if upper > position:
        rows = list(CallbackData.objects.defer("data").filter(id__gt=position, id__lte=upper).order_by("id")[:max_rows])
    capped = len(rows) >= max_rows
    next_position = rows[-1].id if capped else max(position, upper)
    judged = _judge(rows)
    for callback in rows:
        outcome = judged[callback.id][0]
        outcomes[outcome] += 1
        if outcome in WATCHED:
            pending.setdefault(str(callback.id), now_ts)

    limit = conf.callback_pending_limit()
    if len(pending) > limit:
        # 保留最早发现的，丢弃的计数进结果；持续溢出说明回调链路整体异常，应看告警而不是逐条立案
        kept = sorted(pending.items(), key=lambda item: item[1])[:limit]
        outcomes["pending_overflow"] += len(pending) - limit
        pending = dict(kept)
        capped = True

    hits, cases = _emit(lost, dry_run)
    if not dry_run:
        outcomes["closed"] = close_resolved_signature_cases([CALLBACK_DISPATCH_LOST], holds=_still_pending, now=now)
        save_cursor(
            CURSOR_NAME,
            position_id=next_position,
            extra={"high_marks": (marks + [current_max])[-2:], "pending": pending},
        )
    outcomes["id_lag"] = max(current_max - next_position, 0)
    report = ScanReport(
        CURSOR_NAME, len(rows), len(pending) + len(lost), hits, cases, None, capped, dry_run, dict(outcomes)
    )
    record_scan_report(report)
    return report


def backfill_callbacks(from_id, to_id=None, now=None, dry_run=True, max_rows=None, confirm_seconds=None):
    """一次性回扫 [from_id, to_id] 的存量回调；默认只预演、不立案。

    数据年龄未知，先按当前状态判定一次；判为丢失的等 confirm_seconds（默认 CALLBACK_CONFIRM_SECONDS，0 不等）后
    再判一次，两次都判为丢失才报告，避免把刚落库、仍在排队或回调锁重试中的回调误报为丢失。
    """
    now = now or timezone.now()
    max_rows = conf.callback_max_rows() if max_rows is None else max_rows
    confirm_seconds = conf.callback_confirm_seconds() if confirm_seconds is None else confirm_seconds
    queryset = CallbackData.objects.filter(id__gte=from_id).order_by("id")
    if to_id is not None:
        queryset = queryset.filter(id__lte=to_id)
    ids = list(queryset.values_list("id", flat=True)[:max_rows])
    lost, _keep, outcomes = _settle({str(callback_id): None for callback_id in ids}, now.timestamp(), 0, 0)
    if lost:
        if confirm_seconds:
            time.sleep(confirm_seconds)
        confirmed, _keep, _outcomes = _settle({str(item[0].id): None for item in lost}, now.timestamp(), 0, 0)
        outcomes["backfill_unconfirmed"] = len(lost) - len(confirmed)
        lost = confirmed
    hits, cases = _emit(lost, dry_run)
    report = ScanReport(
        BACKFILL_NAME, len(ids), len(lost), hits, cases, None, len(ids) >= max_rows, dry_run, dict(outcomes)
    )
    record_scan_report(report)
    return report
