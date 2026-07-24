# -*- coding: utf-8 -*-
from datetime import timedelta

from unittest import mock
from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.reliable_events import tasks
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase


class TasksTest(ReliableEventsTestCase):
    @override_settings(PIPELINE_RELIABLE_EVENTS_COMPENSATION_ENABLED=False)
    def test_compensation_disabled_noop(self):
        with mock.patch.object(tasks.dispatch_event, "apply_async") as m:
            tasks.compensation_scan()
            m.assert_not_called()

    @override_settings(PIPELINE_RELIABLE_EVENTS_COMPENSATION_ENABLED=True,
                       PIPELINE_RELIABLE_EVENTS_COMPENSATION_BATCH=10)
    def test_compensation_dispatches_due_pending(self):
        now = timezone.now()
        due = EngineEventInbox.objects.create(
            event_type="NODE_CALLBACK", idempotency_key="callback:1", status="PENDING",
            next_attempt_at=now - timedelta(seconds=1),
        )
        EngineEventInbox.objects.create(  # 未到期，不应分发
            event_type="NODE_CALLBACK", idempotency_key="callback:2", status="PENDING",
            next_attempt_at=now + timedelta(seconds=600),
        )
        EngineEventInbox.objects.create(  # 终态，不应分发
            event_type="NODE_CALLBACK", idempotency_key="callback:3", status="APPLIED",
        )
        with mock.patch.object(tasks.dispatch_event, "apply_async") as m:
            tasks.compensation_scan()
            m.assert_called_once_with(kwargs={"event_id": due.id})
