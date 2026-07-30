# -*- coding: utf-8 -*-
import logging

from celery import current_app
from celery.schedules import crontab
from django.utils import timezone

from pipeline.contrib.celery_tools.periodic import periodic_task
from pipeline.contrib.reliable_events import conf, consumer
from pipeline.contrib.reliable_events import purge as purge_mod
from pipeline.contrib.reliable_events.constants import EventStatus
from pipeline.contrib.reliable_events.models import EngineEventInbox

logger = logging.getLogger(__name__)


@current_app.task(ignore_result=True)
def dispatch_event(event_id):
    try:
        consumer.process_event(event_id)
    except Exception:
        logger.exception("dispatch reliable event failed, event_id=%s", event_id)


@periodic_task(run_every=crontab(minute="*"), ignore_result=True)
def compensation_scan():
    if not conf.compensation_enabled():
        return
    now = timezone.now()
    batch = conf.compensation_batch()
    due_ids = list(
        EngineEventInbox.objects.filter(
            status=EventStatus.PENDING, next_attempt_at__lte=now
        ).order_by("next_attempt_at").values_list("id", flat=True)[:batch]
    )
    for event_id in due_ids:
        dispatch_event.apply_async(kwargs={"event_id": event_id})


@periodic_task(run_every=crontab(minute=17, hour="*/6"), ignore_result=True)
def purge_scan():
    if not conf.compensation_enabled():
        return
    try:
        deleted = purge_mod.purge_finished_events()
        if deleted:
            logger.info("reliable events purge removed %s finished events", deleted)
    except Exception:
        logger.exception("reliable events purge failed")
