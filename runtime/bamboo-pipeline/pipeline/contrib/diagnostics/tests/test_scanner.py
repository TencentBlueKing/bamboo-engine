# -*- coding: utf-8 -*-

from datetime import timedelta

from django.utils import timezone

from pipeline.contrib.diagnostics import scanner
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.eri.models import Process
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase


class ScanStalledRootsTest(DiagnosticsTestCase):
    def setUp(self):
        super(ScanStalledRootsTest, self).setUp()
        self.process_ids = []

    def tearDown(self):
        Process.objects.filter(id__in=self.process_ids).delete()
        super(ScanStalledRootsTest, self).tearDown()

    def _proc(self, root, node="n1", beat_delta=0):
        p = Process.objects.create(
            root_pipeline_id=root,
            current_node_id=node,
            destination_id="",
            priority=1,
            queue="diagnostics",
            pipeline_stack="[]",
        )
        self.process_ids.append(p.id)
        Process.objects.filter(id=p.id).update(last_heartbeat=timezone.now() - timedelta(seconds=beat_delta))
        return p

    def test_stalled_root_produces_case_fresh_does_not(self):
        self._proc("root-stuck", beat_delta=3600)
        self._proc("root-fresh", beat_delta=5)
        cases = scanner.scan_stalled_roots(threshold_seconds=1800, batch=100, confirm_seconds=0)
        roots = {c.root_pipeline_id for c in cases}
        self.assertIn("root-stuck", roots)
        self.assertNotIn("root-fresh", roots)

    def test_auto_close_when_root_recovers(self):
        self._proc("root-stuck", beat_delta=3600)
        scanner.scan_stalled_roots(threshold_seconds=1800, batch=100, confirm_seconds=0)
        Process.objects.filter(root_pipeline_id="root-stuck").update(last_heartbeat=timezone.now())
        scanner.scan_stalled_roots(threshold_seconds=1800, batch=100, confirm_seconds=0)
        self.assertEqual(
            DiagnosticCase.objects.get(root_pipeline_id="root-stuck").status,
            DiagnosticCase.STATUS_RESOLVED,
        )

    def test_disabled_returns_empty(self):
        with self.settings(PIPELINE_DIAGNOSTICS_SCAN_ENABLED=False):
            self.assertEqual(scanner.scan_stalled_roots(), [])
