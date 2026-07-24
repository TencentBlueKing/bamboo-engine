# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from django.utils import timezone

from pipeline.contrib.reliable_events import conf, lanes
from pipeline.contrib.reliable_events.constants import EventMode, EventStatus, ErrorCode
from pipeline.contrib.reliable_events.handlers.base import get_handler
from pipeline.contrib.reliable_events.models import EngineEventInbox

logger = logging.getLogger(__name__)


def backoff_seconds(attempts):
    base = conf.backoff_base_seconds()
    cap = conf.backoff_max_seconds()
    return min(base * (2 ** attempts), cap)


def _finalize(event, status, reason, now):
    event.status = status
    event.finished_at = now
    summary = event.result_summary if isinstance(event.result_summary, dict) else {}
    summary["reason"] = reason
    event.result_summary = summary
    event.save(update_fields=["status", "finished_at", "result_summary"])
    return status


def _retry(event, now, error_code=""):
    event.attempts = event.attempts + 1
    event.next_attempt_at = now + timedelta(seconds=backoff_seconds(event.attempts))
    event.status = EventStatus.PENDING
    if error_code:
        event.last_error_code = error_code
        event.last_error_at = now
    event.save(update_fields=["attempts", "next_attempt_at", "status", "last_error_code", "last_error_at"])
    return EventStatus.PENDING


def process_event(event_id, owner=None, now=None):
    now = now or timezone.now()
    owner = owner or "worker"

    event = EngineEventInbox.objects.filter(id=event_id).first()
    if event is None or event.status not in (EventStatus.PENDING, EventStatus.PROCESSING):
        return event.status if event else "MISSING"

    handler = get_handler(event.event_type)
    if handler is None:
        return _finalize(event, EventStatus.MANUAL_REQUIRED, "no_handler", now)

    generation = lanes.acquire_lease(event.concurrency_key, owner, now=now)
    if generation is None:
        return _retry(event, now, error_code=ErrorCode.LEASE_BUSY)

    try:
        if handler.is_obsolete(event):
            return _finalize(event, EventStatus.OBSOLETE, "obsolete", now)
        if handler.is_applied(event):
            return _finalize(event, EventStatus.APPLIED, "applied", now)

        expired = event.converge_deadline_at is not None and now >= event.converge_deadline_at
        if expired or event.attempts >= conf.max_attempts():
            if event.mode == EventMode.SHADOW:
                return _finalize(event, EventStatus.SHADOW_MISMATCH, "expected_applied_but_not", now)
            return _finalize(event, EventStatus.MANUAL_REQUIRED, "converge_deadline_exceeded", now)

        return _retry(event, now, error_code=ErrorCode.TEMP_ERROR)
    finally:
        lanes.release_lease(event.concurrency_key, owner, generation, now=now)
