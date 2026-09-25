# -*- coding: utf-8 -*-

from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.diagnostics.case_types import EXECUTE_DISPATCH_LOST, POLL_DISPATCH_LOST
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticScanCursor
from pipeline.contrib.diagnostics.signature_scan import TIER_FAST, TIER_SLOW, scan_signatures
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import poll_shape, running_root, s1_shape
from pipeline.eri.models import Process


@override_settings(PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED=True)
class SignatureScanTest(DiagnosticsTestCase):
    def setUp(self):
        super(SignatureScanTest, self).setUp()
        running_root()

    def test_fast_tier_opens_case_for_lost_execute(self):
        s1_shape()
        reports = scan_signatures(confirm_seconds=0)
        self.assertEqual([report.scanner for report in reports], [TIER_FAST, TIER_SLOW])
        self.assertEqual(len(reports[0].hits), 1)
        self.assertTrue(DiagnosticCase.objects.filter(stuck_type=EXECUTE_DISPATCH_LOST).exists())

    def test_slow_tier_catches_poll_continuation(self):
        poll_shape(beat=2000, times=3)
        fast, slow = scan_signatures(confirm_seconds=0)
        self.assertEqual(fast.hits, [])
        self.assertEqual([hit.evidence["signature"] for _r, _n, hit in slow.hits], ["S3"])
        self.assertTrue(DiagnosticCase.objects.filter(stuck_type=POLL_DISPATCH_LOST).exists())

    def test_confirm_drops_process_that_moved_on(self):
        process = s1_shape()

        def wake(_seconds):
            Process.objects.filter(id=process.id).update(asleep=False, last_heartbeat=timezone.now())

        with mock.patch("pipeline.contrib.diagnostics.signature_scan.time.sleep", side_effect=wake):
            fast, _slow = scan_signatures(confirm_seconds=1)
        self.assertEqual((fast.candidates, fast.hits), (1, []))

    def test_rows_are_not_rescanned_on_next_run(self):
        s1_shape()
        now = timezone.now()
        scan_signatures(now=now, confirm_seconds=0)
        fast, _slow = scan_signatures(now=now + timedelta(seconds=60), confirm_seconds=0)
        self.assertEqual(fast.rows, 0)

    def test_resolved_case_closes_on_next_run(self):
        process = s1_shape()
        scan_signatures(confirm_seconds=0)
        Process.objects.filter(id=process.id).update(current_node_id="a-next", asleep=False)
        fast, _slow = scan_signatures(confirm_seconds=0)
        self.assertEqual(fast.outcomes["closed"], 1)
        self.assertEqual(DiagnosticCase.objects.get().status, DiagnosticCase.STATUS_RESOLVED)

    def test_dry_run_writes_nothing(self):
        s1_shape()
        fast, _slow = scan_signatures(confirm_seconds=0, dry_run=True)
        self.assertEqual(len(fast.hits), 1)
        self.assertFalse(DiagnosticCase.objects.exists())
        self.assertFalse(DiagnosticScanCursor.objects.exists())

    def test_tier_filter(self):
        s1_shape()
        reports = scan_signatures(confirm_seconds=0, dry_run=True, tiers=[TIER_SLOW])
        self.assertEqual([report.scanner for report in reports], [TIER_SLOW])

    @override_settings(PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED=False)
    def test_disabled_by_default(self):
        s1_shape()
        self.assertEqual(scan_signatures(confirm_seconds=0), [])
