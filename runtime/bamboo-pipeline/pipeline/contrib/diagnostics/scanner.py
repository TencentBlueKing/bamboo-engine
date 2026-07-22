# -*- coding: utf-8 -*-

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.cases import upsert_case
from pipeline.contrib.diagnostics.collector import collect_runtime_snapshot
from pipeline.contrib.diagnostics.rules import diagnose_snapshot
from pipeline.eri.models import Process


def diagnose_pipeline(root_pipeline_id="", node_id="", process_id=None):
    snapshot = collect_runtime_snapshot(root_pipeline_id=root_pipeline_id, node_id=node_id, process_id=process_id)
    return diagnose_snapshot(snapshot)


def _node_id_for_hit(hit, fallback_node_id=""):
    return hit.related_objects.get("node_id") or hit.evidence.get("node_id") or fallback_node_id or ""


def scan_open_processes(limit=100):
    if not conf.scan_enabled() or limit <= 0:
        return []

    root_pipeline_ids = (
        Process.objects.filter(dead=False)
        .order_by("root_pipeline_id")
        .values_list("root_pipeline_id", flat=True)
        .distinct()[:limit]
    )

    cases = []
    for root_pipeline_id in root_pipeline_ids:
        snapshot = collect_runtime_snapshot(root_pipeline_id=root_pipeline_id)
        hits = diagnose_snapshot(snapshot)
        for hit in hits:
            node_id = _node_id_for_hit(hit, snapshot.node_id)
            case = upsert_case(root_pipeline_id, node_id, hit)
            if case is not None:
                cases.append(case)
    return cases
