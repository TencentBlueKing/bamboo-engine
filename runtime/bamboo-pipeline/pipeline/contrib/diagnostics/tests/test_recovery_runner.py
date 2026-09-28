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

from pipeline.contrib.diagnostics import metrics
from pipeline.contrib.diagnostics.case_types import EXECUTE_DISPATCH_LOST, POLL_DISPATCH_LOST
from pipeline.contrib.diagnostics.management.commands.diagnostics_recovery_report import Command
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticRecovery
from pipeline.contrib.diagnostics.recovery import BLOCKER_EMIT_OFF, BLOCKER_ENFORCE_OFF, apply_plan, plan_replay
from pipeline.contrib.diagnostics.recovery_runner import recovery_report, run_recovery
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import ROOT, ago, poll_shape, running_root, s1_shape
from pipeline.contrib.diagnostics.tests.test_recovery import (
    RecoveryTestCase,
    open_callback_case,
    open_case,
    recovery_count,
)
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
                "auto_apply": {},
                "self_heal_ratio": 0.5,
            },
        )
        self.assertIsNone(report[POLL_DISPATCH_LOST]["self_heal_ratio"])

    def test_auto_apply_is_a_subset_of_apply(self):
        self.row(EXECUTE_DISPATCH_LOST, "apply", "applied")
        self.row(EXECUTE_DISPATCH_LOST, "apply", "manual_required")
        DiagnosticRecovery.objects.filter(status="manual_required").update(trigger="auto")
        report = recovery_report(timezone.now() - timedelta(hours=1))[EXECUTE_DISPATCH_LOST]
        self.assertEqual(report["apply"], {"applied": 1, "manual_required": 1})
        self.assertEqual(report["auto_apply"], {"manual_required": 1})

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


SCOPE = "pipeline.contrib.diagnostics.tests.test_recovery_runner."


def allow_root(root_pipeline_id):
    return root_pipeline_id == ROOT


def deny_root(root_pipeline_id):
    return False


def broken_scope(root_pipeline_id):
    raise Exception("scope down")


def breaker_count():
    return metrics.DIAGNOSTICS_RECOVERY_BREAKER_OPEN.labels(hostname=metrics.HOST_NAME)._value.get()


@override_settings(
    PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED=True,
    PIPELINE_DIAGNOSTICS_RECOVERY_MODE="apply",
    PIPELINE_DIAGNOSTICS_AUTO_REPLAY_TYPES="execute_dispatch_lost,callback_dispatch_lost",
    PIPELINE_DIAGNOSTICS_RECOVERY_SCOPE_RESOLVER=SCOPE + "allow_root",
)
class AutoReplayTest(RecoveryTestCase):
    def test_dispatches_case_in_scope_once(self):
        case = open_case(s1_shape())
        self.assertEqual(run_recovery().outcomes, {"auto_dispatched": 1})
        self.assertEqual(run_recovery().outcomes, {"auto_waiting": 1})
        self.runtime.execute.assert_called_once()
        kwargs = self.runtime.execute.call_args[1]
        self.assertEqual((kwargs["node_id"], kwargs["headers"]["fence"]["from_node"]), ("a-next", "a"))
        recovery = DiagnosticRecovery.objects.get()
        self.assertEqual(
            (recovery.case_id, recovery.trigger, recovery.mode, recovery.status),
            (case.id, "auto", "apply", "dispatched"),
        )

    def test_waits_for_manual_replay_in_flight(self):
        case = open_case(s1_shape())
        apply_plan(plan_replay(case), DiagnosticRecovery.TRIGGER_MANUAL, "admin")
        self.assertEqual(run_recovery().outcomes, {"auto_waiting": 1})
        self.runtime.execute.assert_called_once()

    def test_preview_mode_only_previews(self):
        open_case(s1_shape())
        with override_settings(PIPELINE_DIAGNOSTICS_RECOVERY_MODE="preview"):
            self.assertEqual(run_recovery().outcomes, {"previewed": 1})
        self.runtime.execute.assert_not_called()

    def test_type_not_switched_on_only_previews(self):
        open_case(poll_shape())
        self.assertEqual(run_recovery().outcomes, {"previewed": 1})
        self.runtime.schedule.assert_not_called()

    def test_out_of_scope_or_unresolvable_only_previews(self):
        open_case(s1_shape())
        for path in (SCOPE + "deny_root", SCOPE + "broken_scope", "", "no_such_module.resolver"):
            DiagnosticRecovery.objects.all().delete()
            with override_settings(PIPELINE_DIAGNOSTICS_RECOVERY_SCOPE_RESOLVER=path):
                self.assertEqual(run_recovery().outcomes, {"previewed": 1}, path)
        self.runtime.execute.assert_not_called()

    def test_scope_setup_error_only_previews(self):
        open_case(s1_shape())
        with mock.patch("pipeline.contrib.diagnostics.recovery_runner.import_string", side_effect=RuntimeError("boom")):
            self.assertEqual(run_recovery().outcomes, {"previewed": 1})
        self.runtime.execute.assert_not_called()

    def test_emit_off_blocks_execute_replay(self):
        open_case(s1_shape())
        with mock.patch.object(Settings, "FENCE_EMIT_ENABLED", False):
            self.assertEqual(run_recovery().outcomes, {"blocked": 1})
        recovery = DiagnosticRecovery.objects.get()
        self.assertEqual((recovery.mode, recovery.detail), ("preview", {"blockers": [BLOCKER_EMIT_OFF]}))
        self.runtime.execute.assert_not_called()

    def test_callback_replays_without_fence(self):
        _case, schedule, callback = open_callback_case()
        with mock.patch.multiple(Settings, FENCE_EMIT_ENABLED=False, FENCE_ENFORCE=False):
            self.assertEqual(run_recovery().outcomes, {"auto_dispatched": 1})
        self.runtime.schedule.assert_called_once_with(
            process_id=schedule.process_id,
            node_id="cb",
            schedule_id=schedule.id,
            callback_data_id=callback.id,
            headers={},
        )

    def test_retries_each_settle_window_then_requires_manual(self):
        case = open_case(s1_shape())
        before = recovery_count(EXECUTE_DISPATCH_LOST, "auto", "manual_required")
        rounds = []
        with mock.patch("pipeline.contrib.diagnostics.recovery_runner.emit_alert_log") as alert:
            for _ in range(5):
                rounds.append(run_recovery().outcomes)
                DiagnosticRecovery.objects.update(created_at=ago(200))
        self.assertEqual(
            rounds,
            [
                {"auto_dispatched": 1},
                {"ineffective": 1, "auto_dispatched": 1},
                {"ineffective": 1, "auto_dispatched": 1},
                {"ineffective": 1, "manual_required": 1},
                {"auto_exhausted": 1},
            ],
        )
        self.assertEqual(self.runtime.execute.call_count, 3)
        statuses = sorted(DiagnosticRecovery.objects.values_list("status", flat=True))
        self.assertEqual(statuses, ["ineffective", "ineffective", "ineffective", "manual_required"])
        args, kwargs = alert.call_args
        self.assertEqual(args, ("recovery_manual_required", ROOT, "a"))
        self.assertEqual((kwargs["payload"]["case_id"], kwargs["payload"]["attempts"]), (case.id, 3))
        alert.assert_called_once()
        self.assertEqual(recovery_count(EXECUTE_DISPATCH_LOST, "auto", "manual_required") - before, 1)

    def test_failed_dispatch_waits_a_settle_window(self):
        open_case(s1_shape())
        self.runtime.execute.side_effect = Exception("mq down")
        self.assertEqual(run_recovery().outcomes, {"auto_failed": 1})
        self.assertEqual(run_recovery().outcomes, {"auto_waiting": 1})
        self.runtime.execute.side_effect = None
        DiagnosticRecovery.objects.update(created_at=ago(200))
        self.assertEqual(run_recovery().outcomes["auto_dispatched"], 1)
        self.assertEqual(self.runtime.execute.call_count, 2)

    def test_round_cap_defers_the_rest(self):
        open_case(s1_shape(node="a"))
        open_case(s1_shape(node="b"))
        with override_settings(PIPELINE_DIAGNOSTICS_RECOVERY_MAX_PER_ROUND=1):
            self.assertEqual(run_recovery().outcomes, {"auto_dispatched": 1, "auto_deferred": 1})
            self.assertEqual(run_recovery().outcomes, {"auto_waiting": 1, "auto_dispatched": 1})
        self.assertEqual(self.runtime.execute.call_count, 2)

    def test_breaker_only_previews_and_alerts(self):
        open_case(s1_shape(node="a"))
        open_case(s1_shape(node="b"))
        before = breaker_count()
        with override_settings(PIPELINE_DIAGNOSTICS_RECOVERY_BREAKER_THRESHOLD=1), mock.patch(
            "pipeline.contrib.diagnostics.recovery_runner.emit_alert_log"
        ) as alert:
            self.assertEqual(run_recovery().outcomes, {"breaker_open": 1, "previewed": 2})
        self.runtime.execute.assert_not_called()
        self.assertEqual(breaker_count() - before, 1)
        alert.assert_called_once_with(
            "recovery_breaker_open", "", payload={"cases": 2, "window_seconds": 300, "threshold": 1}
        )

    def test_breaker_counts_only_recent_cases(self):
        open_case(s1_shape(node="a"))
        open_case(s1_shape(node="b"))
        DiagnosticCase.objects.update(created_at=ago(600))
        with override_settings(PIPELINE_DIAGNOSTICS_RECOVERY_BREAKER_THRESHOLD=1):
            self.assertEqual(run_recovery().outcomes, {"auto_dispatched": 2})
