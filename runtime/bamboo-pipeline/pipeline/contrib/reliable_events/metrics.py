# -*- coding: utf-8 -*-
import logging

from django.db.models import Count

from pipeline.contrib.reliable_events.constants import EventStatus
from pipeline.contrib.reliable_events.models import EngineEventInbox

logger = logging.getLogger(__name__)


def shadow_stats(since=None):
    qs = EngineEventInbox.objects.all()
    if since is not None:
        qs = qs.filter(accepted_at__gte=since)
    by_status = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("id"))}
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "applied": by_status.get(EventStatus.APPLIED, 0),
        "obsolete": by_status.get(EventStatus.OBSOLETE, 0),
        "mismatch": by_status.get(EventStatus.SHADOW_MISMATCH, 0),
        "pending": by_status.get(EventStatus.PENDING, 0),
    }


def mode_status_stats(since=None):
    qs = EngineEventInbox.objects.all()
    if since is not None:
        qs = qs.filter(accepted_at__gte=since)
    result = {}
    for row in qs.values("mode", "status").annotate(c=Count("id")):
        result.setdefault(row["mode"], {})[row["status"]] = row["c"]
    return result


def emit_shadow_report(stats):
    logger.warning(
        "[reliable_events_shadow_report] total=%s applied=%s obsolete=%s mismatch=%s pending=%s by_status=%s",
        stats.get("total"), stats.get("applied"), stats.get("obsolete"),
        stats.get("mismatch"), stats.get("pending"), stats.get("by_status"),
    )
