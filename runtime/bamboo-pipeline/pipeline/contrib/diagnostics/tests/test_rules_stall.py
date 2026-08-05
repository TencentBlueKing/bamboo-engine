# -*- coding: utf-8 -*-

import types

from bamboo_engine.eri import ScheduleType

from pipeline.contrib.diagnostics.rules import diagnose_snapshot
from pipeline.contrib.diagnostics.types import RuntimeSnapshot
from pipeline.engine import states as engine_states


def _empty_snapshot(root="root-1", node="n1"):
    return RuntimeSnapshot(
        root_pipeline_id=root,
        node_id=node,
        process_id=None,
        processes=[],
        states=[],
        schedules=[],
        callback_data=[],
    )


def _snapshot_with_locked_schedule(root="root-1", node="n1"):
    schedule = types.SimpleNamespace(
        id=1,
        node_id=node,
        process_id=1,
        scheduling=True,
        finished=False,
        expired=False,
        schedule_times=1,
    )
    return RuntimeSnapshot(
        root_pipeline_id=root,
        node_id=node,
        process_id=None,
        processes=[],
        states=[],
        schedules=[schedule],
        callback_data=[],
    )


def _waiting_snapshot(schedule_type, node="n1", finished=False, expired=False, with_schedule=True):
    """一个存活进程沉睡在 RUNNING 节点上，按调度类型决定它在等什么。"""
    process = types.SimpleNamespace(id=1, current_node_id=node, dead=False, asleep=True, need_ack=-1, ack_num=0)
    state = types.SimpleNamespace(id=1, node_id=node, name=engine_states.RUNNING, version="v1")
    schedules = []
    if with_schedule:
        schedules.append(
            types.SimpleNamespace(
                id=1,
                node_id=node,
                process_id=1,
                type=schedule_type,
                version="v1",
                scheduling=False,
                finished=finished,
                expired=expired,
                schedule_times=0,
            )
        )
    return RuntimeSnapshot(
        root_pipeline_id="root-1",
        node_id="",
        process_id=None,
        processes=[process],
        states=[state],
        schedules=schedules,
        callback_data=[],
    )


def test_no_fallback_when_waiting_external_callback():
    """等回调期间进程沉睡不 beat，心跳静默是设计必然，不该判为停滞。"""
    assert diagnose_snapshot(_waiting_snapshot(ScheduleType.CALLBACK), stall_seconds=7200) == []


def test_no_fallback_when_waiting_multiple_callback():
    # DB 里 type 存的是 int，规则要能同时吃 int 和枚举
    snapshot = _waiting_snapshot(ScheduleType.MULTIPLE_CALLBACK.value)
    assert diagnose_snapshot(snapshot, stall_seconds=7200) == []


def test_fallback_hit_for_poll_schedule():
    """POLL 每次轮询都会 beat，静默说明轮询已经停了，要报。"""
    hits = diagnose_snapshot(_waiting_snapshot(ScheduleType.POLL), stall_seconds=7200)
    assert [hit.type for hit in hits] == ["stalled_no_progress"]


def test_fallback_hit_when_callback_schedule_expired():
    snapshot = _waiting_snapshot(ScheduleType.CALLBACK, expired=True)
    assert [hit.type for hit in diagnose_snapshot(snapshot, stall_seconds=7200)] == ["stalled_no_progress"]


def test_fallback_hit_when_running_node_has_no_schedule():
    """RUNNING 但没有调度记录：没有任何机制会再唤醒它，必须保留。"""
    snapshot = _waiting_snapshot(ScheduleType.CALLBACK, with_schedule=False)
    assert [hit.type for hit in diagnose_snapshot(snapshot, stall_seconds=7200)] == ["stalled_no_progress"]


def test_fallback_stalled_hit_when_no_specific_rule():
    hits = diagnose_snapshot(_empty_snapshot(), stall_seconds=3600)
    assert len(hits) == 1
    assert hits[0].type == "stalled_no_progress"
    assert hits[0].evidence["stall_seconds"] == 3600
    assert hits[0].related_objects["root_pipeline_id"] == "root-1"


def test_no_fallback_and_no_injection_when_stall_seconds_none():
    # on-demand 健康快照：不兜底、不注入，保持向后兼容
    assert diagnose_snapshot(_empty_snapshot()) == []


def test_stall_seconds_injected_into_specific_hits():
    hits = diagnose_snapshot(_snapshot_with_locked_schedule(), stall_seconds=1200)
    assert any(h.type == "schedule_lock_stuck" for h in hits)
    for h in hits:
        assert h.evidence["stall_seconds"] == 1200
