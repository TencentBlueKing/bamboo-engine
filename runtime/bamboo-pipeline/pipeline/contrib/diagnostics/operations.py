# -*- coding: utf-8 -*-

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.collector import collect_runtime_snapshot
from pipeline.contrib.diagnostics.models import DiagnosticOperationAudit
from pipeline.contrib.diagnostics.types import OperationResult
from pipeline.eri.models import CallbackData, Schedule


MODE_DRY_RUN = DiagnosticOperationAudit.MODE_DRY_RUN
MODE_APPLY = DiagnosticOperationAudit.MODE_APPLY


def _audit(operation_type, target_object, operator, mode, precheck_result, operation_result, risk_level, payload=None):
    DiagnosticOperationAudit.objects.create(
        operation_type=operation_type,
        target_object=target_object,
        operator=operator,
        mode=mode,
        precheck_result=precheck_result,
        result=operation_result._asdict(),
        risk_level=risk_level,
        payload=payload or {},
    )


def _blocked_apply(operation_type, target_object, operator, mode, risk_level, data=None, precheck_result=None):
    result = OperationResult(
        result=False,
        message="Apply operation is disabled.",
        data=data or {},
        blockers=["apply disabled"],
    )
    _audit(operation_type, target_object, operator, mode, precheck_result or {}, result, risk_level)
    return result


def _ensure_apply_enabled(operation_type, target_object, operator, mode, risk_level, data=None, precheck_result=None):
    if mode == MODE_APPLY and not conf.apply_enabled():
        return _blocked_apply(operation_type, target_object, operator, mode, risk_level, data, precheck_result)
    return None


def _process_data(process):
    return {
        "id": process.id,
        "root_pipeline_id": process.root_pipeline_id,
        "current_node_id": process.current_node_id,
        "ack_num": process.ack_num,
        "need_ack": process.need_ack,
        "asleep": process.asleep,
        "dead": process.dead,
        "suspended": process.suspended,
        "frozen": process.frozen,
    }


def _schedule_data(schedule):
    return {
        "id": schedule.id,
        "process_id": schedule.process_id,
        "node_id": schedule.node_id,
        "version": schedule.version,
        "scheduling": schedule.scheduling,
        "finished": schedule.finished,
        "expired": schedule.expired,
        "schedule_times": schedule.schedule_times,
    }


def _callback_data(callback_data):
    return {
        "id": callback_data.id,
        "node_id": callback_data.node_id,
        "version": callback_data.version,
    }


def _state_data(state):
    if state is None:
        return None
    return {
        "id": state.id,
        "node_id": state.node_id,
        "root_id": state.root_id,
        "name": state.name,
        "version": state.version,
    }


def _runtime_readiness_data(root_pipeline_id, node_id):
    snapshot = collect_runtime_snapshot(root_pipeline_id=root_pipeline_id, node_id=node_id)
    state = snapshot.states[0] if snapshot.states else None
    return {
        "root_pipeline_id": snapshot.root_pipeline_id,
        "node_id": snapshot.node_id,
        "state": state.name if state else "",
        "state_detail": _state_data(state),
        "processes": [_process_data(process) for process in snapshot.processes],
        "schedules": [_schedule_data(schedule) for schedule in snapshot.schedules],
        "callback_data_count": len(snapshot.callback_data),
        "callback_data": [_callback_data(callback_data) for callback_data in snapshot.callback_data],
    }


def inspect_node_runtime_readiness(root_pipeline_id, node_id, operator="", mode=MODE_DRY_RUN):
    operation_type = DiagnosticOperationAudit.OPERATION_TYPE_INSPECT_NODE_RUNTIME_READINESS
    target_object = {"root_pipeline_id": root_pipeline_id, "node_id": node_id}
    risk_level = DiagnosticOperationAudit.RISK_LEVEL_LOW
    data = _runtime_readiness_data(root_pipeline_id, node_id)
    blocked = _ensure_apply_enabled(operation_type, target_object, operator, mode, risk_level, data, data)
    if blocked is not None:
        return blocked

    result = OperationResult(True, "Runtime readiness inspected.", data, [])
    _audit(operation_type, target_object, operator, mode, data, result, risk_level)
    return result


def inspect_ack_converge(root_pipeline_id, node_id, operator="", mode=MODE_DRY_RUN):
    operation_type = DiagnosticOperationAudit.OPERATION_TYPE_INSPECT_ACK_CONVERGE
    target_object = {"root_pipeline_id": root_pipeline_id, "node_id": node_id}
    risk_level = DiagnosticOperationAudit.RISK_LEVEL_LOW
    data = _runtime_readiness_data(root_pipeline_id, node_id)
    data["processes"] = [
        {
            "id": process["id"],
            "root_pipeline_id": process["root_pipeline_id"],
            "current_node_id": process["current_node_id"],
            "ack_num": process["ack_num"],
            "need_ack": process["need_ack"],
        }
        for process in data["processes"]
    ]
    blocked = _ensure_apply_enabled(operation_type, target_object, operator, mode, risk_level, data, data)
    if blocked is not None:
        return blocked

    result = OperationResult(True, "ACK convergence inspected.", data, [])
    _audit(operation_type, target_object, operator, mode, data, result, risk_level)
    return result


def replay_callback_data(callback_data_id, operator="", mode=MODE_DRY_RUN):
    operation_type = DiagnosticOperationAudit.OPERATION_TYPE_REPLAY_CALLBACK_DATA
    target_object = {"callback_data_id": callback_data_id}
    risk_level = DiagnosticOperationAudit.RISK_LEVEL_MEDIUM
    callback_data = CallbackData.objects.filter(id=callback_data_id).first()
    data = {"callback_data_id": callback_data_id, "exists": callback_data is not None}
    if callback_data is not None:
        data.update(_callback_data(callback_data))
    blocked = _ensure_apply_enabled(operation_type, target_object, operator, mode, risk_level, data, data)
    if blocked is not None:
        return blocked

    blockers = []
    if callback_data is None:
        blockers.append("callback data not found")
    if mode == MODE_APPLY:
        blockers.append("requires dispatcher/runtime integration")

    result = OperationResult(
        result=not blockers,
        message="Callback data replay precheck finished." if mode == MODE_DRY_RUN else "Callback data replay apply is not integrated.",
        data=data,
        blockers=blockers,
    )
    _audit(operation_type, target_object, operator, mode, data, result, risk_level)
    return result


def _schedule_precheck(schedule_id):
    schedule = Schedule.objects.filter(id=schedule_id).first()
    data = {"schedule_id": schedule_id, "exists": schedule is not None}
    blockers = []
    if schedule is None:
        blockers.append("schedule not found")
    else:
        data.update(_schedule_data(schedule))
        if schedule.finished:
            blockers.append("schedule already finished")
        if schedule.expired:
            blockers.append("schedule already expired")
    return schedule, data, blockers


def resend_schedule(schedule_id, operator="", mode=MODE_DRY_RUN):
    operation_type = DiagnosticOperationAudit.OPERATION_TYPE_RESEND_SCHEDULE
    target_object = {"schedule_id": schedule_id}
    risk_level = DiagnosticOperationAudit.RISK_LEVEL_MEDIUM
    schedule, data, blockers = _schedule_precheck(schedule_id)
    blocked = _ensure_apply_enabled(operation_type, target_object, operator, mode, risk_level, data, data)
    if blocked is not None:
        return blocked

    blockers = list(blockers)
    if mode == MODE_APPLY:
        blockers.append("requires dispatcher/runtime integration")

    result = OperationResult(
        result=not blockers,
        message="Schedule resend precheck finished." if mode == MODE_DRY_RUN else "Schedule resend apply is not integrated.",
        data=data,
        blockers=blockers,
    )
    _audit(operation_type, target_object, operator, mode, data, result, risk_level)
    return result


def expire_stale_schedule(schedule_id, operator="", mode=MODE_DRY_RUN):
    operation_type = DiagnosticOperationAudit.OPERATION_TYPE_EXPIRE_STALE_SCHEDULE
    target_object = {"schedule_id": schedule_id}
    risk_level = DiagnosticOperationAudit.RISK_LEVEL_MEDIUM
    schedule, data, blockers = _schedule_precheck(schedule_id)
    blocked = _ensure_apply_enabled(operation_type, target_object, operator, mode, risk_level, data, data)
    if blocked is not None:
        return blocked

    if mode == MODE_APPLY and schedule is not None and not blockers:
        schedule.expired = True
        schedule.save(update_fields=["expired"])
        data["expired"] = True

    result = OperationResult(
        result=not blockers,
        message="Schedule expire precheck finished." if mode == MODE_DRY_RUN else "Schedule expired." if not blockers else "Schedule expire blocked.",
        data=data,
        blockers=blockers,
    )
    _audit(operation_type, target_object, operator, mode, data, result, risk_level)
    return result
