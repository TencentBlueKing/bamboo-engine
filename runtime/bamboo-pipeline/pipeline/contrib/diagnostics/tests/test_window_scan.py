# -*- coding: utf-8 -*-

from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.diagnostics.cursor import load_cursor
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import ago, make_process, make_state
from pipeline.contrib.diagnostics.window_scan import cursor_name, scan_silence_window, scan_silence_windows


def _roots(report):
    return {root_id for root_id, _node_id, _hit in report.hits}


class SilenceWindowScanTest(DiagnosticsTestCase):
    def test_root_crossing_threshold_becomes_case(self):
        make_process(root="stuck", node="n1", beat=ago(4000))
        make_process(root="fresh", node="n2", beat=ago(60))
        report = scan_silence_window(3600, confirm_seconds=0)
        self.assertEqual(_roots(report), {"stuck"})
        self.assertTrue(DiagnosticCase.objects.filter(root_pipeline_id="stuck").exists())
        self.assertFalse(DiagnosticCase.objects.filter(root_pipeline_id="fresh").exists())

    def test_every_crossing_root_is_seen_without_batch_truncation(self):
        for index in range(30):
            make_process(root="stuck-%d" % index, beat=ago(4000))
        self.assertEqual(len(_roots(scan_silence_window(3600, confirm_seconds=0))), 30)

    def test_recent_dead_child_keeps_root_out_of_window(self):
        parent = make_process(root="par", node="pg", beat=ago(5000))
        make_process(root="par", node="cg", beat=ago(1000), dead=True, parent_id=parent.id)
        self.assertEqual(scan_silence_window(3600, confirm_seconds=0).hits, [])

    def test_root_without_live_process_is_ignored(self):
        make_process(root="done", beat=ago(4000), dead=True)
        self.assertEqual(scan_silence_window(3600, confirm_seconds=0).hits, [])

    def test_revoked_root_is_ignored(self):
        make_process(root="revoked", beat=ago(4000))
        make_state("revoked", name="REVOKED", version="rv", root="revoked")
        self.assertEqual(scan_silence_window(3600, confirm_seconds=0).hits, [])

    def test_cursor_advances_and_rows_are_not_rescanned(self):
        make_process(root="stuck", beat=ago(4000))
        now = timezone.now()
        scan_silence_window(3600, now=now, confirm_seconds=0)
        self.assertEqual(load_cursor(cursor_name(3600)).position, now - timedelta(seconds=3600))
        self.assertEqual(scan_silence_window(3600, now=now + timedelta(seconds=60), confirm_seconds=0).rows, 0)

    def test_capped_run_resumes_from_last_row(self):
        for index in range(3):
            make_process(root="stuck-%d" % index, beat=ago(4000 + index))
        first = scan_silence_window(3600, confirm_seconds=0, max_rows=2)
        self.assertTrue(first.capped)
        self.assertEqual(scan_silence_window(3600, confirm_seconds=0, max_rows=2).rows, 1)

    def test_dry_run_writes_nothing(self):
        make_process(root="stuck", beat=ago(4000))
        report = scan_silence_window(3600, confirm_seconds=0, dry_run=True)
        self.assertEqual(_roots(report), {"stuck"})
        self.assertEqual(DiagnosticCase.objects.count(), 0)
        self.assertIsNone(load_cursor(cursor_name(3600)))

    def test_start_override_opens_case_without_moving_cursor(self):
        make_process(root="stuck", beat=ago(4000))
        report = scan_silence_window(3600, confirm_seconds=0, start_override=ago(86400))
        self.assertEqual(_roots(report), {"stuck"})
        self.assertTrue(DiagnosticCase.objects.filter(root_pipeline_id="stuck").exists())
        self.assertIsNone(load_cursor(cursor_name(3600)))

    def test_disabled_by_default(self):
        make_process(root="stuck", beat=ago(4000))
        self.assertEqual(scan_silence_windows(), [])

    @override_settings(
        PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED=True,
        PIPELINE_DIAGNOSTICS_WINDOW_TIERS=(3600, 86400),
        PIPELINE_DIAGNOSTICS_SECOND_CONFIRM_SECONDS=0,
    )
    def test_long_tier_does_not_close_short_tier_cases(self):
        make_process(root="stuck", beat=ago(4000))
        reports = scan_silence_windows()
        self.assertEqual([report.scanner for report in reports], ["silence_window_3600", "silence_window_86400"])
        self.assertTrue(
            DiagnosticCase.objects.filter(root_pipeline_id="stuck", status=DiagnosticCase.STATUS_OPEN).exists()
        )
