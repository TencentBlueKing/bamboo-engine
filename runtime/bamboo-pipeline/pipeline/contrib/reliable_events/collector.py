# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone

from pipeline.contrib.reliable_events import conf, keys
from pipeline.contrib.reliable_events.constants import EventMode, EventStatus, EventType
from pipeline.contrib.reliable_events.models import EngineEventInbox

logger = logging.getLogger(__name__)
_INBOX_TABLE_AVAILABLE = None


def _inbox_table_available():
    global _INBOX_TABLE_AVAILABLE
    if _INBOX_TABLE_AVAILABLE is not None:
        return _INBOX_TABLE_AVAILABLE
    try:
        _INBOX_TABLE_AVAILABLE = EngineEventInbox._meta.db_table in connection.introspection.table_names()
    except Exception:
        logger.debug("check reliable event inbox table failed", exc_info=True)
        _INBOX_TABLE_AVAILABLE = False
    return _INBOX_TABLE_AVAILABLE


def _resolve_mode(node_id, version):
    resolver = conf.mode_resolver()
    raw = None
    if resolver is not None:
        try:
            raw = resolver(node_id, version)
        except Exception:  # 钩子异常绝不影响真实 callback
            logger.debug("reliable events mode resolver failed", exc_info=True)
            raw = None
    if raw == EventMode.ACTIVE and conf.active_enabled():
        return EventMode.ACTIVE
    if conf.shadow_enabled():
        return EventMode.SHADOW
    return None


def record_callback_receipt(node_id, version, callback_data_id, root_pipeline_id="", schedule_id=None, data=None):
    if not (conf.shadow_enabled() or conf.active_enabled()):
        return None
    if not _inbox_table_available():
        return None

    try:
        now = timezone.now()
        mode = _resolve_mode(node_id, version)
        if mode is None:
            return None
        if mode == EventMode.ACTIVE:
            next_attempt_at = now + timedelta(seconds=conf.active_initial_delay_seconds())
        else:
            next_attempt_at = now
        idem = keys.idempotency_key_for_callback(callback_data_id)
        defaults = {
            "event_type": EventType.NODE_CALLBACK,
            "source_type": "eri_callbackdata",
            "source_id": str(callback_data_id),
            "root_pipeline_id": root_pipeline_id or "",
            "node_id": node_id,
            "version": version,
            "schedule_id": schedule_id,
            "concurrency_key": keys.concurrency_key_for_node(node_id, version),
            "payload_ref": keys.payload_ref_for_callback(callback_data_id),
            "payload_digest": keys.payload_digest(data) if data is not None else "",
            "mode": mode,
            "status": EventStatus.PENDING,
            "next_attempt_at": next_attempt_at,
            "converge_deadline_at": now + timedelta(seconds=conf.converge_seconds()),
        }
        event, created = EngineEventInbox.objects.get_or_create(idempotency_key=idem, defaults=defaults)
        if created and conf.dispatch_enabled():
            _schedule_immediate_dispatch(event.id)
        return event
    except Exception:
        logger.exception(
            "record reliable callback receipt failed, node_id=%s, version=%s, callback_data_id=%s",
            node_id, version, callback_data_id,
        )
        return None


def _schedule_immediate_dispatch(event_id):
    def _publish():
        try:
            from pipeline.contrib.reliable_events.tasks import dispatch_event
            dispatch_event.apply_async(kwargs={"event_id": event_id})
        except Exception:
            logger.exception("publish immediate dispatch failed, event_id=%s", event_id)

    transaction.on_commit(_publish)
