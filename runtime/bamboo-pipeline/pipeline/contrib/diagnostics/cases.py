# -*- coding: utf-8 -*-

from django.db import IntegrityError, transaction
from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.models import DiagnosticCase


def _apply_hit(case, hit, now):
    case.severity = hit.severity
    case.confidence = hit.confidence
    case.last_seen_at = now
    case.hit_count += 1
    case.evidence = hit.evidence
    case.related_objects = hit.related_objects
    case.recommended_actions = hit.recommended_actions
    case.forbidden_actions = hit.forbidden_actions
    case.message = hit.message
    case.save(
        update_fields=[
            "severity",
            "confidence",
            "last_seen_at",
            "hit_count",
            "evidence",
            "related_objects",
            "recommended_actions",
            "forbidden_actions",
            "message",
            "updated_at",
        ]
    )
    return case


def _create_case(root_pipeline_id, node_id, hit, now):
    return DiagnosticCase.objects.create(
        root_pipeline_id=root_pipeline_id,
        node_id=node_id,
        stuck_type=hit.type,
        severity=hit.severity,
        confidence=hit.confidence,
        status=DiagnosticCase.STATUS_OPEN,
        first_seen_at=now,
        last_seen_at=now,
        hit_count=1,
        evidence=hit.evidence,
        related_objects=hit.related_objects,
        recommended_actions=hit.recommended_actions,
        forbidden_actions=hit.forbidden_actions,
        message=hit.message,
    )


def upsert_case(root_pipeline_id, node_id, hit):
    if not conf.case_enabled():
        return None

    root_pipeline_id = root_pipeline_id or ""
    node_id = node_id or ""
    now = timezone.now()
    lookup = {
        "root_pipeline_id": root_pipeline_id,
        "node_id": node_id,
        "stuck_type": hit.type,
        "status": DiagnosticCase.STATUS_OPEN,
    }

    try:
        with transaction.atomic():
            case = DiagnosticCase.objects.select_for_update().filter(**lookup).first()
            if case is not None:
                return _apply_hit(case, hit, now)
            return _create_case(root_pipeline_id, node_id, hit, now)
    except IntegrityError:
        with transaction.atomic():
            case = DiagnosticCase.objects.select_for_update().get(**lookup)
            return _apply_hit(case, hit, now)


def _resolve_one(case, now_dt):
    """Flip an OPEN case to RESOLVED; if a RESOLVED twin already exists
    (unique_together includes status), merge the recurrence into it and
    drop this duplicate OPEN row."""
    existing = (
        DiagnosticCase.objects.filter(
            root_pipeline_id=case.root_pipeline_id,
            node_id=case.node_id,
            stuck_type=case.stuck_type,
            status=DiagnosticCase.STATUS_RESOLVED,
        )
        .exclude(id=case.id)
        .first()
    )
    if existing is None:
        case.status = DiagnosticCase.STATUS_RESOLVED
        case.last_seen_at = now_dt
        case.save(update_fields=["status", "last_seen_at", "updated_at"])
        return

    if case.last_seen_at and case.last_seen_at > existing.last_seen_at:
        existing.last_seen_at = case.last_seen_at
    existing.hit_count += case.hit_count
    existing.severity = case.severity
    existing.confidence = case.confidence
    existing.evidence = case.evidence
    existing.related_objects = case.related_objects
    existing.recommended_actions = case.recommended_actions
    existing.forbidden_actions = case.forbidden_actions
    existing.message = case.message
    existing.save(
        update_fields=[
            "last_seen_at",
            "hit_count",
            "severity",
            "confidence",
            "evidence",
            "related_objects",
            "recommended_actions",
            "forbidden_actions",
            "message",
            "updated_at",
        ]
    )
    case.delete()


def close_stale_cases(threshold_seconds, now=None):
    """Resolve open cases whose root recovered (progressed within threshold) or has no live process."""
    from pipeline.contrib.diagnostics.progress import root_last_progress, stall_cutoff

    cutoff = stall_cutoff(threshold_seconds, now=now)
    now_dt = now or timezone.now()
    to_close = []
    for case in DiagnosticCase.objects.filter(status=DiagnosticCase.STATUS_OPEN).iterator():
        latest = root_last_progress(case.root_pipeline_id)
        if latest is None or latest >= cutoff:
            to_close.append(case)
    for case in to_close:
        _resolve_one(case, now_dt)
    return len(to_close)
