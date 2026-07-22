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
