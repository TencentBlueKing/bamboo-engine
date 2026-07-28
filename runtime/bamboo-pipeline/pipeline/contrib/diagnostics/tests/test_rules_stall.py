# -*- coding: utf-8 -*-

import types

from pipeline.contrib.diagnostics.rules import diagnose_snapshot
from pipeline.contrib.diagnostics.types import RuntimeSnapshot


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
