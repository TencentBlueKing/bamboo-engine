# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from django.utils import timezone

from pipeline.contrib.reliable_events import conf, lanes, state_machine
from pipeline.contrib.reliable_events.constants import EventMode, EventStatus, ErrorCode
from pipeline.contrib.reliable_events.handlers.base import get_handler
from pipeline.contrib.reliable_events.handlers.callback import NoScheduleError, NotEligibleError
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


def _to_processing(event, now):
    if not state_machine.validate_transition(event.status, EventStatus.PROCESSING, event.mode):
        return False
    event.status = EventStatus.PROCESSING
    event.save(update_fields=["status"])
    return True


def _expired_or_maxed(event, now):
    expired = event.converge_deadline_at is not None and now >= event.converge_deadline_at
    return expired or event.attempts >= conf.max_attempts()


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

        if event.mode == EventMode.ACTIVE:
            return _process_active(event, handler, now)
        return _process_shadow(event, now)
    finally:
        lanes.release_lease(event.concurrency_key, owner, generation, now=now)


def _process_shadow(event, now):
    # 单元1 语义不变:到期/超次 → SHADOW_MISMATCH,否则退避。
    if _expired_or_maxed(event, now):
        return _finalize(event, EventStatus.SHADOW_MISMATCH, "expected_applied_but_not", now)
    return _retry(event, now, error_code=ErrorCode.TEMP_ERROR)


def _process_active(event, handler, now):
    if event.next_attempt_at is not None and now < event.next_attempt_at:
        # 未到期:不重放、不加尝试次数,保持 PENDING,留待到点由 compensation 处理
        return EventStatus.PENDING

    # 到期/超次 → 转人工(停止自动修改,转平台运维)。
    if _expired_or_maxed(event, now):
        return _finalize(event, EventStatus.MANUAL_REQUIRED, "converge_deadline_exceeded", now)

    if not _to_processing(event, now):
        # 非法迁移(防御性):退避重试。
        return _retry(event, now, error_code=ErrorCode.TEMP_ERROR)

    try:
        handler.apply(event)  # 幂等重投(异步):下次重读 is_applied 收敛
    except NoScheduleError:
        return _retry(event, now, error_code=ErrorCode.NO_SCHEDULE)
    except NotEligibleError:
        return _finalize(event, EventStatus.MANUAL_REQUIRED, "not_single_callback", now)
    except Exception:
        logger.exception("reliable event active apply failed, event_id=%s", event.id)
        return _retry(event, now, error_code=ErrorCode.APPLY_FAILED)

    # 重投已发出,退避回 PENDING,等待下一轮确认 is_applied。
    return _retry(event, now)
