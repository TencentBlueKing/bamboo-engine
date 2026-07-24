# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from django.utils import timezone

from pipeline.contrib.reliable_events import conf
from pipeline.contrib.reliable_events.constants import EventStatus
from pipeline.contrib.reliable_events.models import EngineEventInbox

logger = logging.getLogger(__name__)

_PURGEABLE = (EventStatus.APPLIED, EventStatus.OBSOLETE)


def purge_finished_events(now=None, batch=None):
    now = now or timezone.now()
    batch = batch or conf.compensation_batch()
    cutoff = now - timedelta(days=conf.event_retention_days())
    total = 0
    while True:
        ids = list(
            EngineEventInbox.objects.filter(
                status__in=_PURGEABLE, finished_at__isnull=False, finished_at__lt=cutoff
            ).order_by("id").values_list("id", flat=True)[:batch]
        )
        if not ids:
            break
        deleted, _ = EngineEventInbox.objects.filter(id__in=ids).delete()
        total += len(ids)
        if len(ids) < batch:
            break
    return total
