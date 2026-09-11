# -*- coding: utf-8 -*-

from collections import defaultdict

from bamboo_engine.eri import ScheduleType

from pipeline.contrib.diagnostics.types import DiagnosticHit
from pipeline.engine import states


TERMINAL_STATES = frozenset([states.FINISHED, states.FAILED, states.REVOKED])
CALLBACK_SCHEDULE_TYPES = frozenset([ScheduleType.CALLBACK.value, ScheduleType.MULTIPLE_CALLBACK.value])


def _ids(items):
    return [item.id for item in sorted(items, key=lambda item: item.id)]


def _parked_by_user(process):
    """暂停/冻结的进程按设计停在原地等人工恢复，不是卡住。

    pause_pipeline / pause_node / freeze 只把 suspended | frozen 置位，进程既没死也不再往前推进，
    此时它指向的下一个节点自然还没有 State，各类"进程活着但状态不对"的判据都会误判。
    """
    return bool(getattr(process, "suspended", False) or getattr(process, "frozen", False))


def _schedule_type_value(schedule):
    return getattr(schedule.type, "value", schedule.type)


def _waiting_ack_convergence(process):
    """并行网关把自己置为 FINISHED 后让父进程沉睡等子进程收敛，守在终态节点上是设计内行为。"""
    return process.need_ack > 0 and 0 <= process.ack_num < process.need_ack


def _live_children_count(snapshot):
    counts = defaultdict(int)
    for process in snapshot.processes:
        parent_id = getattr(process, "parent_id", -1)
        if not process.dead and parent_id not in (None, -1):
            counts[parent_id] += 1
    return counts


def _has_full_process_view(snapshot):
    """快照是否按 root 全量收集：只有此时子进程才在其中，才能判断收敛是否真的丢了。"""
    return not snapshot.node_id and snapshot.process_id is None


def _all_live_processes_parked(snapshot, states_by_node):
    """整条流程的存活进程都停在人工停车点（用户暂停 / 节点失败等重试）。

    停车期间不推进是设计内行为，心跳必然停摆，兜底判据不能把它当成停滞。

    等 ACK 收敛的父进程在这里算中性：它自己没有停车，但也不代表流程还在推进——
    能不能往下走完全取决于子进程，而子进程会各自被判定。典型形态是并行网关下几个分支
    失败停车，父进程因此永远收不齐 ACK，整条流程实际上是在等人工处理那几个失败分支。
    子进程若真的卡了（RUNNING 无调度）或全死却未收敛，都有各自的判据接住，不会被这里放过。
    """
    live = [process for process in snapshot.processes if not process.dead]
    if not live:
        return False
    parked_seen = False
    for process in live:
        if _waiting_ack_convergence(process):
            continue
        if _parked_by_user(process):
            parked_seen = True
            continue
        state = states_by_node.get(process.current_node_id)
        if state is not None and _parked_at_failed_node(process, state):
            parked_seen = True
            continue
        return False
    # 全是等 ACK 的父进程、一个停车的都没有时不算停车，交回兜底判断
    return parked_seen


def _waiting_external_callback(snapshot, states_by_node, schedules_by_node):
    """引擎正沉睡等待外部回调。

    runtime.beat() 只在执行推进循环和 schedule() 内部调用，等回调期间进程两者都不执行，
    心跳因此冻结在入睡那一刻。也就是说"心跳静默"是回调型节点的设计必然结果，
    而不是停滞的证据——等人的暂停节点、审批节点更是没有任何合理的时长上界。
    """
    for process in snapshot.processes:
        if process.dead or not process.current_node_id:
            continue
        state = states_by_node.get(process.current_node_id)
        if state is None or state.name != states.RUNNING:
            continue
        for schedule in schedules_by_node.get(process.current_node_id, []):
            if schedule.version != state.version or schedule.finished or schedule.expired:
                continue
            if _schedule_type_value(schedule) in CALLBACK_SCHEDULE_TYPES:
                return True
    return False


def _parked_at_failed_node(process, state):
    """节点失败后引擎会 sleep 进程并停在该 FAILED 节点，等待人工重试或跳过，不是卡住。"""
    return state.name == states.FAILED and bool(getattr(process, "asleep", False))


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


def _callback_lock_conflicts(schedules_by_node, callbacks_by_node, states_by_node):
    """回调数据多于调度次数，说明有回调没被消费掉，节点会一直等在那里。

    只在节点还没到终态、且只统计当前 version 的数据时才成立：

    - 终态节点上多出来的回调数据是迟到回调留下的残留。callback() 只校验"有沉睡进程 + version 一致 +
      schedule 未完成"，而节点失败后进程恰好是沉睡在该节点上、version 也不变，迟到的回调因此能写进
      CallbackData，随后调度任务发现节点已不是 RUNNING 就直接 expire 返回，schedule_times 不会自增。
    - Schedule 是按 (node_id, version) 唯一的，跨 version 求和会让重试前残留的回调把总数顶起来，
      而历史 version 的回调按定义挡不住当前 version 的调度。
    """
    hits = []
    for node_id in sorted(set(schedules_by_node.keys()) | set(callbacks_by_node.keys())):
        state = states_by_node.get(node_id)
        if state is not None and state.name in TERMINAL_STATES:
            continue
        version = state.version if state is not None else None
        schedules = sorted(
            [item for item in schedules_by_node.get(node_id, []) if version is None or item.version == version],
            key=lambda schedule: schedule.id,
        )
        callbacks = sorted(
            [item for item in callbacks_by_node.get(node_id, []) if version is None or item.version == version],
            key=lambda callback_data: callback_data.id,
        )
        schedule_times = sum(schedule.schedule_times for schedule in schedules)
        if callbacks and len(callbacks) > schedule_times:
            hits.append(
                _hit(
                    "callback_lock_conflict",
                    "critical",
                    0.99,
                    {
                        "node_id": node_id,
                        "version": version or "",
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
        if _parked_by_user(process):
            continue
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
        if state is None or process.dead:
            continue
        if _parked_by_user(process) or _parked_at_failed_node(process, state):
            continue
        if _waiting_ack_convergence(process):
            # 收敛是否真的丢了由 parallel_ack_not_converged 判断，这里不重复报同一个根因
            continue
        if state.name in TERMINAL_STATES:
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
    """父进程等不到子进程的 ACK。

    子进程还活着时未收敛是并行流程的正常形态，问题（如果有）在子进程身上，会被它自己的签名抓到，
    报父进程只会把诊断指向错误的位置。只有子进程全都没了却仍未收敛，才是真的收敛丢失。
    """
    if not _has_full_process_view(snapshot):
        return []

    live_children = _live_children_count(snapshot)
    hits = []
    for process in sorted(snapshot.processes, key=lambda item: item.id):
        if _parked_by_user(process) or not _waiting_ack_convergence(process):
            continue
        if live_children.get(process.id, 0) > 0:
            continue
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
                    "live_children": 0,
                },
                {"process_id": process.id, "node_id": process.current_node_id},
                ["inspect_ack_converge"],
                ["resend_schedule", "replay_callback_data"],
                "Process {} waits for ACK convergence: {}/{} while no child process is alive".format(
                    process.id, process.ack_num, process.need_ack
                ),
            )
        )
    return hits


def _schedule_missing_for_running_node(snapshot, states_by_node, schedules_by_node):
    """节点还在 RUNNING、有存活进程守着，却没有对应 version 的调度记录。

    沉睡的进程只能由调度或回调唤醒，没有调度记录就是确定性地不可唤醒；未沉睡的多数是
    celery worker 在 execute 途中被杀（OOM / 发布 / 驱逐），状态停在 RUNNING、调度还没写。
    两者都不会再自行往前走，但后者与"execute 仍在执行"签名重合，因此本判据只在已确认静默时生效。
    """
    hits = []
    for process in sorted(snapshot.processes, key=lambda item: item.id):
        if process.dead or not process.current_node_id or _parked_by_user(process):
            continue
        state = states_by_node.get(process.current_node_id)
        if state is None or state.name != states.RUNNING:
            continue
        versions = {schedule.version for schedule in schedules_by_node.get(process.current_node_id, [])}
        if state.version in versions:
            continue
        asleep = bool(getattr(process, "asleep", False))
        hits.append(
            _hit(
                "schedule_missing_for_running_node",
                "critical",
                0.90,
                {
                    "process_id": process.id,
                    "node_id": process.current_node_id,
                    "version": state.version,
                    "process_asleep": asleep,
                },
                {"process_id": process.id, "node_id": process.current_node_id},
                ["inspect_node_runtime_readiness"],
                ["resend_schedule", "replay_callback_data"],
                "Node {} is running without schedule for version {} while process {} stays on it (asleep={})".format(
                    process.current_node_id, state.version, process.id, asleep
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
        if process is not None and _parked_by_user(process):
            continue
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
    hits.extend(_callback_lock_conflicts(schedules_by_node, callbacks_by_node, states_by_node))
    hits.extend(_missing_state_for_live_process(snapshot, states_by_node))
    hits.extend(_process_alive_but_terminal_state(snapshot, states_by_node))
    hits.extend(_schedule_lock_stuck(snapshot))
    hits.extend(_parallel_ack_not_converged(snapshot))
    hits.extend(_schedule_finished_but_process_not_exited(snapshot, processes_by_id))
    hits.extend(_multiple_sleep_process_for_node(processes_by_node))

    if stall_seconds is not None:
        # 需要"已确认静默"作为前置，否则会把 execute 正在执行的瞬时窗口当成异常
        hits.extend(_schedule_missing_for_running_node(snapshot, states_by_node, schedules_by_node))

    if (
        not hits
        and stall_seconds is not None
        and not _waiting_external_callback(snapshot, states_by_node, schedules_by_node)
        and not _all_live_processes_parked(snapshot, states_by_node)
    ):
        hits = [_stalled_no_progress_hit(snapshot, stall_seconds)]

    if stall_seconds is not None:
        hits = [
            hit._replace(evidence=dict(hit.evidence, stall_seconds=stall_seconds))
            for hit in hits
        ]

    return hits
