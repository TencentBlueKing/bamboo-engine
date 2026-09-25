# -*- coding: utf-8 -*-

from io import StringIO

from django.core.management.base import CommandError

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

    def test_callback_dry_run_requires_backfill_range(self):
        with self.assertRaises(CommandError):
            self.run_scan(scanner="callback", dry_run=True)

    def test_callback_backfill_dry_run(self):
        _process, _schedule, callback = callback_shape()
        output = self.run_scan(scanner="callback", dry_run=True, confirm=0, from_callback_id=callback.id)
        self.assertIn("HIT callback_dispatch_lost", output)
        self.assertFalse(DiagnosticCase.objects.exists())


class PollProfileCommandTest(DiagnosticsTestCase):
    def test_profile_groups_by_code(self):
        poll_shape(node="p1", beat=600, times=2, code="demo_poll")
        poll_shape(node="p2", beat=300, times=0, code="demo_poll")
        out = StringIO()
        ProfileCommand(stdout=out).handle(days=7, limit=50)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0].split(), ["code", "count", "silent_p50", "silent_p90", "silent_max", "avg_interval"])
        self.assertEqual(lines[1].split()[:2], ["demo_poll", "1"])
