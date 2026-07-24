# -*- coding: utf-8 -*-
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.reliable_events import consumer
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase
from pipeline.eri.models import Schedule, State


class ConsumerTest(ReliableEventsTestCase):
    def _event(self, node_id="node-1", version="v1", **kwargs):
        now = timezone.now()
        defaults = dict(
            event_type="NODE_CALLBACK", idempotency_key="callback:1", node_id=node_id, version=version,
            concurrency_key="{}:{}".format(node_id, version), status="PENDING", mode="SHADOW",
            next_attempt_at=now, converge_deadline_at=now + timedelta(seconds=600),
        )
        defaults.update(kwargs)
        return EngineEventInbox.objects.create(**defaults)

    def test_applied_when_schedule_finished(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=True)
        e = self._event()
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "APPLIED")
        self.assertEqual(EngineEventInbox.objects.get(id=e.id).status, "APPLIED")

    def test_obsolete_when_version_changed(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v2")
        e = self._event(version="v1")
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "OBSOLETE")

    def test_retry_before_deadline(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        e = self._event()
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "PENDING")
        reloaded = EngineEventInbox.objects.get(id=e.id)
        self.assertEqual(reloaded.attempts, 1)
        self.assertGreater(reloaded.next_attempt_at, timezone.now())

    def test_shadow_mismatch_after_deadline(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        past = timezone.now() - timedelta(seconds=1)
        e = self._event(converge_deadline_at=past)
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "SHADOW_MISMATCH")
        self.assertEqual(EngineEventInbox.objects.get(id=e.id).status, "SHADOW_MISMATCH")

    def test_lease_busy_keeps_pending(self):
        from pipeline.contrib.reliable_events import lanes
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        e = self._event()
        lanes.acquire_lease("node-1:v1", "other-worker")  # 占用同通道
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "PENDING")

    def test_backoff_seconds_caps_at_max(self):
        with override_settings(PIPELINE_RELIABLE_EVENTS_BACKOFF_BASE_SECONDS=5,
                               PIPELINE_RELIABLE_EVENTS_BACKOFF_MAX_SECONDS=300):
            self.assertEqual(consumer.backoff_seconds(0), 5)
            self.assertEqual(consumer.backoff_seconds(3), 40)
            self.assertEqual(consumer.backoff_seconds(20), 300)
