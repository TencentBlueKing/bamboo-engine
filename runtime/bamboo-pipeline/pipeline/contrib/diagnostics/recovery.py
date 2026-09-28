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

import logging
from collections import Counter, namedtuple
from datetime import timedelta

from django.utils import timezone

from bamboo_engine import fence
from bamboo_engine.fence import ExecuteFence, ScheduleFence

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.callback_scan import OUTCOME_PENDING, OUTCOME_SCHEDULING, WATCHED, case_callback
from pipeline.contrib.diagnostics.case_types import (
    CALLBACK_DISPATCH_LOST,
    CHILD_START_LOST,
    EXECUTE_DISPATCH_LOST,
    PARENT_WAKEUP_LOST,
    REPLAYABLE_CASE_TYPES,
)
from pipeline.contrib.diagnostics.metrics import record_recovery
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticOperationAudit, DiagnosticRecovery
from pipeline.contrib.diagnostics.progress import root_states
from pipeline.contrib.diagnostics.signatures import matching_hit
from pipeline.contrib.diagnostics.types import OperationResult
from pipeline.engine import states
from pipeline.eri.models import Process, State

logger = logging.getLogger(__name__)

KIND_EXECUTE = "execute"
KIND_POLL = "poll"
KIND_CALLBACK = "callback"
FENCED_KINDS = (KIND_EXECUTE, KIND_POLL)

MODE_DRY_RUN = DiagnosticOperationAudit.MODE_DRY_RUN
MODE_APPLY = DiagnosticOperationAudit.MODE_APPLY

BLOCKER_CASE_NOT_FOUND = "case not found"
BLOCKER_NOT_OPEN = "case is not open"
BLOCKER_NOT_REPLAYABLE = "stuck type is not replayable"
BLOCKER_SHAPE_GONE = "shape no longer holds"
BLOCKER_SUCCESSOR = "successor node is not unique"
BLOCKER_CALLBACK_SCHEDULING = "callback schedule is running"
BLOCKER_MULTIPLE_CALLBACKS = "more than one callback was lost on this node"
BLOCKER_ENFORCE_OFF = "fence enforce is off"
BLOCKER_EMIT_OFF = "fence emit is off"
BLOCKER_RISK = "fence emit is off, confirm the risk to replay"
BLOCKER_SKIP_ORIGIN = "message came from a skip and carries no fence token"
BLOCKER_SKIP_RISK = "message came from a skip and carries no fence token, confirm the risk to replay"
BLOCKER_IN_FLIGHT = "a replay is waiting to settle"
BLOCKER_APPLY_DISABLED = "apply disabled"
BLOCKER_DISPATCH_FAILED = "dispatch failed"
RISK_BLOCKERS = (BLOCKER_RISK, BLOCKER_SKIP_RISK)

SETTLE_STATUSES = (
    DiagnosticRecovery.STATUS_DISPATCHED,
    DiagnosticRecovery.STATUS_PREVIEWED,
    DiagnosticRecovery.STATUS_BLOCKED,
)

ReplayPlan = namedtuple("ReplayPlan", ["case", "fingerprint", "message", "blockers"])


def _runtime():
    from pipeline.eri.runtime import BambooDjangoRuntime

    return BambooDjangoRuntime()


def _execute_message(process_id, node_id, from_node, from_version):
    info = _runtime().get_process_info(process_id)
    return {
        "kind": KIND_EXECUTE,
        "process_id": process_id,
        "node_id": node_id,
        "root_pipeline_id": info.root_pipeline_id,
        "parent_pipeline_id": info.top_pipeline_id,
        "fence": ExecuteFence(from_node, from_version).to_dict(),
    }


def _signature_message(case):
    hit = matching_hit(case)
    if hit is None:
        return "", None, [BLOCKER_SHAPE_GONE]
    related, evidence = hit.related_objects, hit.evidence
    process_id, node_id = related["process_id"], related["node_id"]
    version = evidence.get("state_version", "")
    fingerprint = "{}:{}:{}:{}".format(case.stuck_type, process_id, node_id, version)
    if case.stuck_type == EXECUTE_DISPATCH_LOST:
        targets = related.get("next_node_ids") or []
        if len(targets) != 1:
            return fingerprint, None, [BLOCKER_SUCCESSOR]
        return fingerprint, _execute_message(process_id, targets[0], node_id, version), []
    if case.stuck_type == PARENT_WAKEUP_LOST:
        return fingerprint, _execute_message(process_id, related["converge_gateway_id"], node_id, version), []
    if case.stuck_type == CHILD_START_LOST:
        # 分支首节点还没有状态时，引擎派发的令牌版本是 None
        return fingerprint, _execute_message(process_id, node_id, node_id, version or None), []
    times = evidence["schedule_times"]
    message = {
        "kind": KIND_POLL,
        "process_id": process_id,
        "node_id": node_id,
        "schedule_id": evidence["schedule_id"],
        "fence": ScheduleFence(times).to_dict(),
    }
    return "{}:{}".format(fingerprint, times), message, []


def _callback_message(case):
    outcome, callback, schedule = case_callback(case)
    if outcome not in (OUTCOME_PENDING, OUTCOME_SCHEDULING):
        return "", None, [BLOCKER_SHAPE_GONE]
    fingerprint = "{}:{}:{}:{}".format(case.stuck_type, schedule.process_id, callback.node_id, callback.version)
    if outcome == OUTCOME_SCHEDULING:
        return fingerprint, None, [BLOCKER_CALLBACK_SCHEDULING]
    # CallbackData.node_id 没有索引，不按节点反查回调条数；案例命中过多次说明同一节点确认丢失过多条回调
    if case.hit_count > 1:
        return fingerprint, None, [BLOCKER_MULTIPLE_CALLBACKS]
    message = {
        "kind": KIND_CALLBACK,
        "process_id": schedule.process_id,
        "node_id": callback.node_id,
        "schedule_id": schedule.id,
        "callback_data_id": callback.id,
        "fence": None,
    }
    return fingerprint, message, []


def _safety_blockers(message, trigger, confirm_risk):
    if message["kind"] not in FENCED_KINDS:
        return []
    if not fence.enforce_enabled():
        return [BLOCKER_ENFORCE_OFF]
    manual = trigger == DiagnosticRecovery.TRIGGER_MANUAL
    if fence.emit_enabled() or (manual and confirm_risk):
        return []
    return [BLOCKER_RISK if manual else BLOCKER_EMIT_OFF]


def _skip_origin(case):
    """跳过节点、跳过条件并行网关派发的消息不带令牌，原消息晚到时会绕过门禁再执行一次。"""
    if case.stuck_type == EXECUTE_DISPATCH_LOST:
        version = (case.evidence or {}).get("state_version", "")
        return State.objects.filter(node_id=case.node_id, version=version, skip=True).exists()
    if case.stuck_type == CHILD_START_LOST:
        parent_id = (case.related_objects or {}).get("parent_process_id")
        gateway_id = Process.objects.filter(id=parent_id).values_list("current_node_id", flat=True).first()
        return bool(gateway_id) and State.objects.filter(node_id=gateway_id, skip=True).exists()
    return False


def _in_flight(case, fingerprint, now):
    return DiagnosticRecovery.objects.filter(
        case=case,
        fingerprint=fingerprint,
        status=DiagnosticRecovery.STATUS_DISPATCHED,
        created_at__gt=now - timedelta(seconds=conf.recovery_settle_seconds()),
    ).exists()


def plan_replay(case, trigger=DiagnosticRecovery.TRIGGER_MANUAL, confirm_risk=False, now=None):
    """重新判定形态并推导重放消息；形态不成立时 fingerprint 为空，blockers 非空时不能派发。"""
    if case.status != DiagnosticCase.STATUS_OPEN:
        return ReplayPlan(case, "", None, [BLOCKER_NOT_OPEN])
    if case.stuck_type not in REPLAYABLE_CASE_TYPES:
        return ReplayPlan(case, "", None, [BLOCKER_NOT_REPLAYABLE])
    build = _callback_message if case.stuck_type == CALLBACK_DISPATCH_LOST else _signature_message
    fingerprint, message, blockers = build(case)
    if message is not None:
        blockers = _safety_blockers(message, trigger, confirm_risk)
        if _skip_origin(case):
            if trigger != DiagnosticRecovery.TRIGGER_MANUAL:
                blockers.append(BLOCKER_SKIP_ORIGIN)
            elif not confirm_risk:
                blockers.append(BLOCKER_SKIP_RISK)
        if _in_flight(case, fingerprint, now or timezone.now()):
            blockers.append(BLOCKER_IN_FLIGHT)
    return ReplayPlan(case, fingerprint, message, blockers)


def dispatch(message):
    headers = {} if message.get("fence") is None else {fence.FENCE_HEADER: dict(message["fence"])}
    runtime = _runtime()
    if message["kind"] == KIND_EXECUTE:
        runtime.execute(
            process_id=message["process_id"],
            node_id=message["node_id"],
            root_pipeline_id=message["root_pipeline_id"],
            parent_pipeline_id=message["parent_pipeline_id"],
            headers=headers,
        )
        return
    runtime.schedule(
        process_id=message["process_id"],
        node_id=message["node_id"],
        schedule_id=message["schedule_id"],
        callback_data_id=message.get("callback_data_id"),
        headers=headers,
    )


def record(plan, trigger, mode, status, operator="", detail=None):
    case = plan.case
    return DiagnosticRecovery.objects.create(
        case=case,
        root_pipeline_id=case.root_pipeline_id,
        node_id=case.node_id,
        stuck_type=case.stuck_type,
        process_id=(case.related_objects or {}).get("process_id"),
        fingerprint=plan.fingerprint,
        message=plan.message or {},
        trigger=trigger,
        mode=mode,
        status=status,
        operator=operator,
        detail=detail or {},
    )


def apply_plan(plan, trigger, operator=""):
    """派发一个没有阻断的计划并记台账，返回 (记录, 派发失败时的错误信息)。"""
    try:
        dispatch(plan.message)
    except Exception as err:
        logger.exception("[pipeline_diagnostics_recovery] dispatch failed: case=%s", plan.case.id)
        detail = {"blockers": [BLOCKER_DISPATCH_FAILED], "error": str(err)}
        recovery = record(plan, trigger, MODE_APPLY, DiagnosticRecovery.STATUS_BLOCKED, operator, detail)
        record_recovery(plan.case.stuck_type, trigger, DiagnosticRecovery.STATUS_BLOCKED)
        return recovery, str(err) or err.__class__.__name__
    recovery = record(plan, trigger, MODE_APPLY, DiagnosticRecovery.STATUS_DISPATCHED, operator)
    record_recovery(plan.case.stuck_type, trigger, DiagnosticRecovery.STATUS_DISPATCHED)
    return recovery, ""


def _audit(case, operator, mode, plan, blockers, result, confirm_risk):
    fenced = (plan.message or {}).get("kind") in FENCED_KINDS
    DiagnosticOperationAudit.objects.create(
        case=case,
        operation_type=DiagnosticOperationAudit.OPERATION_TYPE_REPLAY_CASE,
        target_object={"case_id": case.id, "fingerprint": plan.fingerprint},
        operator=operator,
        mode=mode,
        precheck_result={"blockers": blockers},
        result=result._asdict(),
        risk_level=DiagnosticOperationAudit.RISK_LEVEL_HIGH if fenced else DiagnosticOperationAudit.RISK_LEVEL_MEDIUM,
        payload={"message": plan.message, "confirm_risk": confirm_risk},
    )


def replay_case(case_id, operator, mode=MODE_DRY_RUN, confirm_risk=False):
    """人工预览重放（dry_run）或重放（apply），两种模式都写操作审计。"""
    case = DiagnosticCase.objects.filter(id=case_id).first()
    if case is None:
        return OperationResult(False, BLOCKER_CASE_NOT_FOUND, {}, [BLOCKER_CASE_NOT_FOUND])
    plan = plan_replay(case, confirm_risk=confirm_risk)
    blockers = list(plan.blockers)
    if mode == MODE_APPLY and not conf.apply_enabled():
        blockers.append(BLOCKER_APPLY_DISABLED)
    data = {
        "case_id": case.id,
        "fingerprint": plan.fingerprint,
        "message": plan.message,
        "requires_risk_confirm": any(blocker in blockers for blocker in RISK_BLOCKERS),
    }
    if blockers:
        result = OperationResult(False, "; ".join(blockers), data, blockers)
    elif mode != MODE_APPLY:
        result = OperationResult(True, "replay preview", data, [])
    else:
        recovery, error = apply_plan(plan, DiagnosticRecovery.TRIGGER_MANUAL, operator)
        data["recovery_id"] = recovery.id
        if error:
            message = "{}: {}".format(BLOCKER_DISPATCH_FAILED, error)
            result = OperationResult(False, message, data, [BLOCKER_DISPATCH_FAILED])
        else:
            result = OperationResult(True, "replay dispatched", data, [])
    _audit(case, operator, mode, plan, blockers, result, confirm_risk)
    return result


def _still_stuck(recovery):
    case = recovery.case
    if case is None:
        return None
    if recovery.stuck_type == CALLBACK_DISPATCH_LOST:
        return case_callback(case)[0] in WATCHED
    hit = matching_hit(case)
    if hit is None:
        return False
    message = recovery.message or {}
    if message.get("kind") == KIND_POLL:
        return hit.evidence.get("schedule_times") == (message.get("fence") or {}).get("schedule_times")
    return True


def settle_recoveries(now=None, batch=None):
    """复核超过收敛窗口的记录：已派发的定出结果，预演和阻断的只记形态是否仍成立。返回结果计数。"""
    now = now or timezone.now()
    batch = conf.recovery_batch() if batch is None else batch
    cutoff = now - timedelta(seconds=conf.recovery_settle_seconds())
    rows = list(
        DiagnosticRecovery.objects.select_related("case")
        .filter(status__in=SETTLE_STATUSES, settled_at__isnull=True, created_at__lte=cutoff)
        .order_by("id")[:batch]
    )
    roots = root_states({row.root_pipeline_id for row in rows})
    outcomes = Counter()
    for row in rows:
        try:
            holds = _still_stuck(row)
            detail = dict(row.detail or {})
            if holds is not None:
                detail["settled_holds"] = holds
            fields = {"detail": detail, "settled_at": now}
            if row.status == DiagnosticRecovery.STATUS_DISPATCHED:
                if holds is None:
                    status = DiagnosticRecovery.STATUS_OBSOLETE
                elif holds:
                    status = DiagnosticRecovery.STATUS_INEFFECTIVE
                elif roots.get(row.root_pipeline_id) == states.RUNNING:
                    status = DiagnosticRecovery.STATUS_APPLIED
                else:
                    status = DiagnosticRecovery.STATUS_OBSOLETE
                fields["status"] = status
                DiagnosticRecovery.objects.filter(id=row.id).update(**fields)
                record_recovery(row.stuck_type, row.trigger, status)
                outcomes[status] += 1
            else:
                DiagnosticRecovery.objects.filter(id=row.id).update(**fields)
                if holds is None:
                    outcomes["preview_gone"] += 1
                else:
                    outcomes["preview_holds" if holds else "preview_healed"] += 1
        except Exception:
            logger.exception("[pipeline_diagnostics_recovery] settle failed: recovery=%s", row.id)
            outcomes["error"] += 1
    return outcomes
