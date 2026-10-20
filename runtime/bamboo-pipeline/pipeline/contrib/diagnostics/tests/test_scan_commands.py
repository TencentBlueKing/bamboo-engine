# -*- coding: utf-8 -*-

from datetime import timedelta
from io import StringIO

from django.core.management.base import CommandError
from django.utils import timezone

from pipeline.contrib.diagnostics.management.commands.diagnostics_poll_profile import Command as ProfileCommand
from pipeline.contrib.diagnostics.management.commands.diagnostics_scan import Command as ScanCommand
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticScanCursor
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import (
    ago,
    callback_shape,
    make_process,
    poll_shape,
    running_root,
    s1_shape,
)
from pipeline.eri.models import Process, State


class ScanCommandTest(DiagnosticsTestCase):
    def setUp(self):
        super(ScanCommandTest, self).setUp()
        running_root()

    def run_scan(self, **options):
        out = StringIO()
        ScanCommand(stdout=out).handle(**options)
        return out.getvalue()

    def test_signature_dry_run_prints_hits_without_writing(self):
        s1_shape()
        output = self.run_scan(scanner="signature", dry_run=True, confirm=0)
        self.assertIn("HIT execute_dispatch_lost", output)
        self.assertFalse(DiagnosticCase.objects.exists())
        self.assertFalse(DiagnosticScanCursor.objects.exists())

    def test_signature_tier_option(self):
        s1_shape()
        output = self.run_scan(scanner="signature", dry_run=True, confirm=0, tier="slow")
        self.assertIn("scanner=signature_slow", output)
        self.assertNotIn("scanner=signature_fast", output)

    def test_invalid_signature_tier(self):
        with self.assertRaises(CommandError):
            self.run_scan(scanner="signature", dry_run=True, tier="medium")

    def test_window_dry_run_with_start_seconds(self):
        make_process(root="stuck", beat=ago(4000))
        output = self.run_scan(scanner="window", dry_run=True, confirm=0, tier="3600", start_seconds=86400)
        self.assertIn("root=stuck", output)
        self.assertFalse(DiagnosticCase.objects.exists())
        self.assertFalse(DiagnosticScanCursor.objects.exists())

    def test_start_seconds_opens_case_without_moving_cursor(self):
        make_process(root="stuck", beat=ago(4000))
        self.run_scan(scanner="window", confirm=0, tier="3600", start_seconds=86400)
        self.assertTrue(DiagnosticCase.objects.filter(root_pipeline_id="stuck").exists())
        self.assertFalse(DiagnosticScanCursor.objects.exists())

    def test_invalid_window_tier(self):
        for tier in ("fast", "1800"):
            with self.assertRaises(CommandError):
                self.run_scan(scanner="window", dry_run=True, tier=tier)

    def test_non_positive_limits_are_rejected(self):
        for options in ({"max_rows": 0}, {"start_seconds": 0}, {"confirm": -1}):
            with self.assertRaises(CommandError):
                self.run_scan(scanner="signature", dry_run=True, **options)

    def test_periodic_callback_scan_ignores_switch(self):
        output = self.run_scan(scanner="callback")
        self.assertIn("scanner=callback_watermark", output)
        self.assertTrue(DiagnosticScanCursor.objects.filter(name="callback_watermark").exists())

    def test_callback_dry_run_requires_backfill_range(self):
        with self.assertRaises(CommandError):
            self.run_scan(scanner="callback", dry_run=True)

    def test_callback_backfill_dry_run(self):
        _process, _schedule, callback = callback_shape()
        output = self.run_scan(scanner="callback", dry_run=True, confirm=0, from_callback_id=callback.id)
        self.assertIn("HIT callback_dispatch_lost", output)
        self.assertFalse(DiagnosticCase.objects.exists())


class PollProfileCommandTest(DiagnosticsTestCase):
    def run_profile(self, **options):
        out, err = StringIO(), StringIO()
        ProfileCommand(stdout=out, stderr=err).handle(**dict({"days": 7, "limit": 50}, **options))
        return out.getvalue().splitlines(), err.getvalue()

    def test_profile_groups_by_code(self):
        poll_shape(node="p1", beat=600, times=2, code="demo_poll")
        poll_shape(node="p2", beat=300, times=0, code="demo_poll")
        lines, err = self.run_profile()
        self.assertEqual(lines[0], "rows=2 capped=False")
        self.assertEqual(lines[1].split(), ["code", "count", "silent_p50", "silent_p90", "silent_max", "interval_p50"])
        self.assertEqual(lines[2].split()[:2], ["demo_poll", "1"])
        self.assertEqual(err, "")

    def test_interval_excludes_current_silence(self):
        now = timezone.now()
        for node, started, beat in [("p1", 660, 600), ("p2", 720, 600), ("p3", 86460, 86400)]:
            process = poll_shape(node=node, beat=beat, times=1, code="demo_poll")
            Process.objects.filter(id=process.id).update(last_heartbeat=now - timedelta(seconds=beat))
            State.objects.filter(node_id=node).update(started_time=now - timedelta(seconds=started))
        lines, _err = self.run_profile()
        self.assertEqual(lines[2].split(), ["demo_poll", "3", "600", "86400", "86400", "60"])

    def test_cap_keeps_longest_silent_and_warns(self):
        poll_shape(node="old", beat=5000, times=1, code="slow_poll")
        poll_shape(node="new", beat=60, times=1, code="fast_poll")
        lines, err = self.run_profile(max_rows=1)
        self.assertEqual(lines[0], "rows=1 capped=True")
        self.assertEqual([line.split()[0] for line in lines[2:]], ["slow_poll"])
        self.assertIn("--max-rows", err)
