# -*- coding: utf-8 -*-

import time

from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.cases import close_stale_cases, upsert_case
from pipeline.contrib.diagnostics.collector import collect_runtime_snapshot
from pipeline.contrib.diagnostics.progress import root_last_progress, stalled_root_candidates
from pipeline.contrib.diagnostics.rules import diagnose_snapshot


def diagnose_pipeline(root_pipeline_id="", node_id="", process_id=None):
    snapshot = collect_runtime_snapshot(root_pipeline_id=root_pipeline_id, node_id=node_id, process_id=process_id)
    return diagnose_snapshot(snapshot)


def _node_id_for_hit(hit, fallback_node_id=""):
    return hit.related_objects.get("node_id") or hit.evidence.get("node_id") or fallback_node_id or ""


def scan_stalled_roots(threshold_seconds=None, batch=None, confirm_seconds=None, now=None):
    if not conf.scan_enabled():
        return []

    threshold_seconds = threshold_seconds if threshold_seconds is not None else conf.stall_threshold_seconds()
    batch = batch if batch is not None else conf.scan_batch()
    confirm_seconds = confirm_seconds if confirm_seconds is not None else conf.second_confirm_seconds()

    candidates = stalled_root_candidates(threshold_seconds, batch, now=now)
    if confirm_seconds and candidates:
        time.sleep(confirm_seconds)  # 一次性等待后统一二次确认，剔除刚恢复的 root

    confirmed = []
    for root_pipeline_id, latest in candidates:
        latest_now = root_last_progress(root_pipeline_id)
        if latest_now is not None and latest_now == latest:
            confirmed.append((root_pipeline_id, latest))

    now_dt = now or timezone.now()
    cases = []
    for root_pipeline_id, latest in confirmed:
        stall_seconds = int((now_dt - latest).total_seconds())
        snapshot = collect_runtime_snapshot(root_pipeline_id=root_pipeline_id)
        for hit in diagnose_snapshot(snapshot, stall_seconds=stall_seconds):
            node_id = _node_id_for_hit(hit, snapshot.node_id)
            case = upsert_case(root_pipeline_id, node_id, hit)
            if case is not None:
                cases.append(case)

    close_stale_cases(threshold_seconds, now=now)
    return cases
