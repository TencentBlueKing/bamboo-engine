# -*- coding: utf-8 -*-
from pipeline.contrib.reliable_events import metrics
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase


class ShadowReportTest(ReliableEventsTestCase):
    def _mk(self, key, status):
        EngineEventInbox.objects.create(event_type="NODE_CALLBACK", idempotency_key=key, status=status)

    def test_shadow_stats_counts(self):
        self._mk("callback:1", "APPLIED")
        self._mk("callback:2", "APPLIED")
        self._mk("callback:3", "SHADOW_MISMATCH")
        self._mk("callback:4", "OBSOLETE")
        self._mk("callback:5", "PENDING")
        stats = metrics.shadow_stats()
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["applied"], 2)
        self.assertEqual(stats["mismatch"], 1)
        self.assertEqual(stats["obsolete"], 1)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["by_status"]["APPLIED"], 2)
