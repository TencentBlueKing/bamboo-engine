# -*- coding: utf-8 -*-

from collections import defaultdict

from pipeline.contrib.diagnostics.types import DiagnosticHit
from pipeline.engine import states


TERMINAL_STATES = frozenset([states.FINISHED, states.FAILED, states.REVOKED])


def _ids(items):
    return [item.id for item in sorted(items, key=lambda item: item.id)]


def _hit(hit_type, severity, confidence, evidence, related_objects, recommended_actions, forbidden_actions, message):
    return DiagnosticHit(
        type=hit_type,
        severity=severity,
        confidence=confidence,
        evidence=evidence,
        related_objects=related_objects,
        recommended_actions=recommended_actions,
        forbidden_actions=forbidden_actions,
        message=message,
    )


def _build_indexes(snapshot):
    processes_by_id = {process.id: process for process in snapshot.processes}
    processes_by_node = defaultdict(list)
    states_by_node = {}
    schedules_by_node = defaultdict(list)
    callbacks_by_node = defaultdict(list)

    for process in snapshot.processes:
        if process.current_node_id:
            processes_by_node[process.current_node_id].append(process)

    for state in snapshot.states:
        states_by_node[state.node_id] = state

    for schedule in snapshot.schedules:
        schedules_by_node[schedule.node_id].append(schedule)

    for callback_data in snapshot.callback_data:
        callbacks_by_node[callback_data.node_id].append(callback_data)

    return processes_by_id, processes_by_node, states_by_node, schedules_by_node, callbacks_by_node


def _callback_lock_conflicts(schedules_by_node, callbacks_by_node):
    hits = []
    for node_id in sorted(set(schedules_by_node.keys()) | set(callbacks_by_node.keys())):
        schedules = sorted(schedules_by_node.get(node_id, []), key=lambda schedule: schedule.id)
        callbacks = sorted(callbacks_by_node.get(node_id, []), key=lambda callback_data: callback_data.id)
        schedule_times = sum(schedule.schedule_times for schedule in schedules)
        if callbacks and len(callbacks) > schedule_times:
            hits.append(
                _hit(
                    "callback_lock_conflict",
                    "critical",
                    0.99,
                    {
                        "node_id": node_id,
                        "callback_data_count": len(callbacks),
                        "schedule_times": schedule_times,
                    },
                    {
                        "node_id": node_id,
                        "schedule_ids": _ids(schedules),
                        "callback_data_ids": _ids(callbacks),
                    },
                    ["inspect_callback_data", "replay_callback_data"],
                    ["resend_schedule"],
                    "Callback data count is greater than schedule execution count for node {}".format(node_id),
                )
            )
    return hits


def _schedule_lock_stuck(snapshot):
    hits = []
    for schedule in sorted(snapshot.schedules, key=lambda item: item.id):
        if schedule.scheduling and not schedule.finished and not schedule.expired:
            hits.append(
                _hit(
                    "schedule_lock_stuck",
                    "critical",
                    0.95,
                    {
                        "schedule_id": schedule.id,
                        "node_id": schedule.node_id,
                        "scheduling": schedule.scheduling,
                        "finished": schedule.finished,
                        "expired": schedule.expired,
                    },
                    {"schedule_id": schedule.id, "process_id": schedule.process_id, "node_id": schedule.node_id},
                    ["inspect_schedule_lock", "expire_stale_schedule"],
                    ["replay_callback_data"],
                    "Schedule {} is locked in scheduling state".format(schedule.id),
                )
            )
    return hits


def _missing_state_for_live_process(snapshot, states_by_node):
    hits = []
    for process in sorted(snapshot.processes, key=lambda item: item.id):
        if not process.dead and process.current_node_id and process.current_node_id not in states_by_node:
            hits.append(
                _hit(
                    "missing_state_for_live_process",
                    "critical",
                    0.98,
                    {
                        "process_id": process.id,
                        "node_id": process.current_node_id,
                        "dead": process.dead,
                    },
                    {"process_id": process.id, "node_id": process.current_node_id},
                    ["inspect_node_runtime_readiness"],
                    ["resend_schedule", "replay_callback_data"],
                    "Live process {} points to node {} without runtime state".format(
                        process.id, process.current_node_id
                    ),
                )
            )
    return hits


def _process_alive_but_terminal_state(snapshot, states_by_node):
    hits = []
    for process in sorted(snapshot.processes, key=lambda item: item.id):
        state = states_by_node.get(process.current_node_id)
        if state is not None and not process.dead and state.name in TERMINAL_STATES:
            hits.append(
                _hit(
                    "process_alive_but_terminal_state",
                    "critical",
                    0.97,
                    {"process_id": process.id, "node_id": process.current_node_id, "state": state.name},
                    {"process_id": process.id, "state_id": state.id, "node_id": process.current_node_id},
                    ["inspect_node_runtime_readiness"],
                    ["resend_schedule"],
                    "Process {} is alive while node {} is in terminal state {}".format(
                        process.id, process.current_node_id, state.name
                    ),
                )
            )
    return hits


def _parallel_ack_not_converged(snapshot):
    hits = []
    for process in sorted(snapshot.processes, key=lambda item: item.id):
        if process.need_ack > 0 and 0 <= process.ack_num < process.need_ack:
            hits.append(
                _hit(
                    "parallel_ack_not_converged",
                    "high",
                    0.94,
                    {
                        "process_id": process.id,
                        "node_id": process.current_node_id,
                        "ack_num": process.ack_num,
                        "need_ack": process.need_ack,
                    },
                    {"process_id": process.id, "node_id": process.current_node_id},
                    ["inspect_ack_converge"],
                    ["resend_schedule", "replay_callback_data"],
                    "Process {} waits for ACK convergence: {}/{}".format(
                        process.id, process.ack_num, process.need_ack
                    ),
                )
            )
    return hits


def _multiple_sleep_process_for_node(processes_by_node):
    hits = []
    for node_id in sorted(processes_by_node.keys()):
        sleeping = sorted(
            [process for process in processes_by_node[node_id] if process.asleep and not process.dead],
            key=lambda item: item.id,
        )
        if len(sleeping) > 1:
            hits.append(
                _hit(
                    "multiple_sleep_process_for_node",
                    "high",
                    0.92,
                    {"node_id": node_id, "sleep_process_count": len(sleeping)},
                    {"node_id": node_id, "process_ids": _ids(sleeping)},
                    ["inspect_node_runtime_readiness"],
                    ["resend_schedule", "replay_callback_data"],
                    "Node {} has multiple sleeping live processes".format(node_id),
                )
            )
    return hits


def _schedule_finished_but_process_not_exited(snapshot, processes_by_id):
    hits = []
    for schedule in sorted(snapshot.schedules, key=lambda item: item.id):
        process = processes_by_id.get(schedule.process_id)
        if (
            process is not None
            and schedule.finished
            and not process.dead
            and process.current_node_id == schedule.node_id
        ):
            hits.append(
                _hit(
                    "schedule_finished_but_process_not_exited",
                    "high",
                    0.93,
                    {
                        "schedule_id": schedule.id,
                        "process_id": process.id,
                        "node_id": schedule.node_id,
                        "finished": schedule.finished,
                        "process_dead": process.dead,
                    },
                    {"schedule_id": schedule.id, "process_id": process.id, "node_id": schedule.node_id},
                    ["inspect_node_runtime_readiness"],
                    ["resend_schedule", "replay_callback_data"],
                    "Schedule {} finished but process {} still stays on node {}".format(
                        schedule.id, process.id, schedule.node_id
                    ),
                )
            )
    return hits


def _stalled_no_progress_hit(snapshot, stall_seconds):
    node_id = snapshot.node_id or (
        snapshot.processes[0].current_node_id if snapshot.processes else ""
    )
    return _hit(
        "stalled_no_progress",
        "warning",
        0.80,
        {"node_id": node_id, "stall_seconds": stall_seconds},
        {"node_id": node_id, "root_pipeline_id": snapshot.root_pipeline_id},
        ["inspect_node_runtime_readiness"],
        [],
        "Root {} has not progressed for {}s".format(snapshot.root_pipeline_id, stall_seconds),
    )


def diagnose_snapshot(snapshot, stall_seconds=None):
    processes_by_id, processes_by_node, states_by_node, schedules_by_node, callbacks_by_node = _build_indexes(snapshot)

    hits = []
    hits.extend(_callback_lock_conflicts(schedules_by_node, callbacks_by_node))
    hits.extend(_missing_state_for_live_process(snapshot, states_by_node))
    hits.extend(_process_alive_but_terminal_state(snapshot, states_by_node))
    hits.extend(_schedule_lock_stuck(snapshot))
    hits.extend(_parallel_ack_not_converged(snapshot))
    hits.extend(_schedule_finished_but_process_not_exited(snapshot, processes_by_id))
    hits.extend(_multiple_sleep_process_for_node(processes_by_node))

    if not hits and stall_seconds is not None:
        hits = [_stalled_no_progress_hit(snapshot, stall_seconds)]

    if stall_seconds is not None:
        hits = [
            hit._replace(evidence=dict(hit.evidence, stall_seconds=stall_seconds))
            for hit in hits
        ]

    return hits
