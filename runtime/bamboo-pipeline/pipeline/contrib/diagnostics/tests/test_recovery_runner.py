# -*- coding: utf-8 -*-

import json
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from bamboo_engine.config import Settings

from pipeline.contrib.diagnostics.case_types import EXECUTE_DISPATCH_LOST, POLL_DISPATCH_LOST
from pipeline.contrib.diagnostics.management.commands.diagnostics_recovery_report import Command
from pipeline.contrib.diagnostics.models import DiagnosticRecovery
from pipeline.contrib.diagnostics.recovery import BLOCKER_ENFORCE_OFF, apply_plan, plan_replay
from pipeline.contrib.diagnostics.recovery_runner import recovery_report, run_recovery
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import ROOT, ago, poll_shape, running_root, s1_shape
from pipeline.contrib.diagnostics.tests.test_recovery import open_case
from pipeline.eri.models import Process, Schedule


class RunRecoveryTest(DiagnosticsTestCase):
    def setUp(self):
        super(RunRecoveryTest, self).setUp()
        running_root()
        runtime_patcher = mock.patch("pipeline.contrib.diagnostics.recovery._runtime")
        self.runtime = runtime_patcher.start().return_value
        self.addCleanup(runtime_patcher.stop)
        self.runtime.get_process_info.return_value = SimpleNamespace(root_pipeline_id=ROOT, top_pipeline_id=ROOT)
        fence_patcher = mock.patch.multiple(Settings, FENCE_EMIT_ENABLED=True, FENCE_ENFORCE=True)
        fence_patcher.start()
        self.addCleanup(fence_patcher.stop)

    def test_disabled_by_default(self):
        open_case(s1_shape())
        self.assertIsNone(run_recovery())
        self.assertFalse(DiagnosticRecovery.objects.exists())

    @override_settings(PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED=True)
    def test_previews_each_fingerprint_once_without_dispatch(self):
        case = open_case(s1_shape())
        first = run_recovery()
        second = run_recovery()
        self.assertEqual((first.cases, first.outcomes), (1, {"previewed": 1}))
        self.assertEqual(second.outcomes, {"seen": 1})
        recovery = DiagnosticRecovery.objects.get()
        self.assertEqual(
            (recovery.case_id, recovery.trigger, recovery.mode, recovery.status),
            (case.id, "auto", "preview", "previewed"),
        )
        self.assertEqual(recovery.message["node_id"], "a-next")
        self.runtime.execute.assert_not_called()

    def test_blocked_preview_keeps_blockers(self):
        open_case(s1_shape())
        with mock.patch.object(Settings, "FENCE_ENFORCE", False):
            run_recovery(force=True)
        recovery = DiagnosticRecovery.objects.get()
        self.assertEqual((recovery.status, recovery.detail), ("blocked", {"blockers": [BLOCKER_ENFORCE_OFF]}))

    def test_shape_gone_is_counted_not_recorded(self):
        process = s1_shape()
        open_case(process)
        Process.objects.filter(id=process.id).update(current_node_id="a-next", asleep=False)
        self.assertEqual(run_recovery(force=True).outcomes, {"shape_gone": 1})
        self.assertFalse(DiagnosticRecovery.objects.exists())

    def test_poll_progress_gets_new_preview(self):
        open_case(poll_shape(beat=2000, times=3))
        run_recovery(force=True)
        Schedule.objects.filter(node_id="p").update(schedule_times=4)
        run_recovery(force=True)
        fingerprints = sorted(DiagnosticRecovery.objects.values_list("fingerprint", flat=True))
        self.assertEqual([item.rsplit(":", 1)[1] for item in fingerprints], ["3", "4"])

    def test_settles_before_previewing(self):
        process = s1_shape()
        case = open_case(process)
        apply_plan(plan_replay(case), DiagnosticRecovery.TRIGGER_MANUAL, "admin")
        DiagnosticRecovery.objects.update(created_at=ago(200))
        Process.objects.filter(id=process.id).update(
            current_node_id="a-next", asleep=False, last_heartbeat=timezone.now()
        )
        self.assertEqual(run_recovery(force=True).outcomes, {"applied": 1, "shape_gone": 1})

    def test_case_error_does_not_stop_round(self):
        broken = open_case(s1_shape())
        open_case(poll_shape())

        def plan(case, **kwargs):
            if case.id == broken.id:
                raise Exception("boom")
            return plan_replay(case, **kwargs)

        with mock.patch("pipeline.contrib.diagnostics.recovery_runner.plan_replay", side_effect=plan):
            report = run_recovery(force=True)
        self.assertEqual((report.cases, report.outcomes), (2, {"error": 1, "previewed": 1}))


class RecoveryReportTest(DiagnosticsTestCase):
    def row(self, stuck_type, mode, status, message=None, **detail):
        return DiagnosticRecovery.objects.create(
            root_pipeline_id=ROOT,
            node_id="n",
            stuck_type=stuck_type,
            fingerprint="f",
            message=message or {},
            trigger="auto" if mode == "preview" else "manual",
            mode=mode,
            status=status,
            detail=detail,
        )

    def test_groups_by_type(self):
        message = {"kind": "execute"}
        self.row(EXECUTE_DISPATCH_LOST, "preview", "previewed", message, blockers=[], settled_holds=False)
        self.row(EXECUTE_DISPATCH_LOST, "preview", "previewed", message, blockers=[], settled_holds=True)
        self.row(EXECUTE_DISPATCH_LOST, "preview", "blocked", message, blockers=["fence emit is off"])
        self.row(EXECUTE_DISPATCH_LOST, "apply", "applied", message)
        self.row(POLL_DISPATCH_LOST, "preview", "previewed", {"kind": "poll"}, blockers=[])
        report = recovery_report(timezone.now() - timedelta(hours=1))
        self.assertEqual(
            report[EXECUTE_DISPATCH_LOST],
            {
                "preview": {"previewed": 2, "blocked": 1},
                "blockers": {"fence emit is off": 1},
                "settled": {"healed": 1, "holds": 1},
                "apply": {"applied": 1},
                "self_heal_ratio": 0.5,
            },
        )
        self.assertIsNone(report[POLL_DISPATCH_LOST]["self_heal_ratio"])

    def test_old_rows_are_excluded(self):
        self.row(EXECUTE_DISPATCH_LOST, "preview", "previewed")
        DiagnosticRecovery.objects.update(created_at=ago(7200))
        self.assertEqual(recovery_report(timezone.now() - timedelta(hours=1)), {})

    def test_command_prints_json(self):
        self.row(EXECUTE_DISPATCH_LOST, "apply", "dispatched")
        stdout = StringIO()
        Command(stdout=stdout).handle(hours=24)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["types"][EXECUTE_DISPATCH_LOST]["apply"], {"dispatched": 1})

    def test_command_rejects_non_positive_hours(self):
        with self.assertRaises(CommandError):
            Command(stdout=StringIO()).handle(hours=0)
