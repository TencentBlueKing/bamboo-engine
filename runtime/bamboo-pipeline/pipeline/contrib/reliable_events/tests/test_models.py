# -*- coding: utf-8 -*-
from django.db import IntegrityError

from pipeline.contrib.reliable_events.models import EngineEventInbox, EngineEventLane
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase


class ModelTest(ReliableEventsTestCase):
    def test_inbox_defaults(self):
        e = EngineEventInbox.objects.create(
            event_type="NODE_CALLBACK", idempotency_key="callback:1",
            root_pipeline_id="root-1", node_id="node-1", version="v1",
            concurrency_key="node-1:v1",
        )
        self.assertEqual(e.mode, "SHADOW")
        self.assertEqual(e.status, "PENDING")
        self.assertEqual(e.attempts, 0)
        self.assertEqual(e.lease_generation, 0)
        self.assertEqual(e.result_summary, {})
        self.assertIsNotNone(e.accepted_at)

    def test_inbox_idempotency_unique(self):
        EngineEventInbox.objects.create(event_type="NODE_CALLBACK", idempotency_key="callback:1")
        with self.assertRaises(IntegrityError):
            EngineEventInbox.objects.create(event_type="NODE_CALLBACK", idempotency_key="callback:1")

    def test_result_summary_json_roundtrip(self):
        e = EngineEventInbox.objects.create(
            event_type="NODE_CALLBACK", idempotency_key="callback:2",
            result_summary={"reason": "applied", "n": 3},
        )
        loaded = EngineEventInbox.objects.get(id=e.id)
        self.assertEqual(loaded.result_summary, {"reason": "applied", "n": 3})

    def test_lane_unique_concurrency_key(self):
        EngineEventLane.objects.create(concurrency_key="node-1:v1")
        with self.assertRaises(IntegrityError):
            EngineEventLane.objects.create(concurrency_key="node-1:v1")
