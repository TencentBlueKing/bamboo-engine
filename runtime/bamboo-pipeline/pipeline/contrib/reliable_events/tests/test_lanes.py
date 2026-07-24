# -*- coding: utf-8 -*-
from datetime import timedelta

from django.utils import timezone

from pipeline.contrib.reliable_events import lanes
from pipeline.contrib.reliable_events.models import EngineEventLane
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase


class LaneTest(ReliableEventsTestCase):
    def test_acquire_on_fresh_key_creates_and_returns_generation(self):
        gen = lanes.acquire_lease("node-1:v1", "worker-a")
        self.assertEqual(gen, 1)
        lane = EngineEventLane.objects.get(concurrency_key="node-1:v1")
        self.assertEqual(lane.lease_owner, "worker-a")
        self.assertEqual(lane.lease_generation, 1)

    def test_second_acquire_blocked_while_lease_valid(self):
        self.assertEqual(lanes.acquire_lease("node-1:v1", "worker-a"), 1)
        self.assertIsNone(lanes.acquire_lease("node-1:v1", "worker-b"))

    def test_acquire_reclaims_expired_lease_and_bumps_generation(self):
        self.assertEqual(lanes.acquire_lease("node-1:v1", "worker-a"), 1)
        past = timezone.now() - timedelta(seconds=1)
        EngineEventLane.objects.filter(concurrency_key="node-1:v1").update(lease_until=past)
        self.assertEqual(lanes.acquire_lease("node-1:v1", "worker-b"), 2)
        lane = EngineEventLane.objects.get(concurrency_key="node-1:v1")
        self.assertEqual(lane.lease_owner, "worker-b")

    def test_renew_only_for_matching_owner_generation(self):
        gen = lanes.acquire_lease("node-1:v1", "worker-a")
        self.assertTrue(lanes.renew_lease("node-1:v1", "worker-a", gen))
        self.assertFalse(lanes.renew_lease("node-1:v1", "worker-b", gen))
        self.assertFalse(lanes.renew_lease("node-1:v1", "worker-a", gen + 5))

    def test_release_only_for_holder(self):
        gen = lanes.acquire_lease("node-1:v1", "worker-a")
        self.assertFalse(lanes.release_lease("node-1:v1", "worker-b", gen))
        self.assertTrue(lanes.release_lease("node-1:v1", "worker-a", gen))
        self.assertEqual(lanes.acquire_lease("node-1:v1", "worker-b"), gen + 1)
