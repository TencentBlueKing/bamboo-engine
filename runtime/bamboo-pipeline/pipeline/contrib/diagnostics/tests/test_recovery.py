# -*- coding: utf-8 -*-

from types import SimpleNamespace
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from bamboo_engine.config import Settings

from pipeline.contrib.diagnostics import metrics
from pipeline.contrib.diagnostics.callback_scan import backfill_callbacks
from pipeline.contrib.diagnostics.case_types import CALLBACK_DISPATCH_LOST, EXECUTE_DISPATCH_LOST
from pipeline.contrib.diagnostics.cases import upsert_case
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticOperationAudit, DiagnosticRecovery
from pipeline.contrib.diagnostics.recovery import (
    BLOCKER_APPLY_DISABLED,
    BLOCKER_CALLBACK_SCHEDULING,
    BLOCKER_DISPATCH_FAILED,
    BLOCKER_EMIT_OFF,
    BLOCKER_ENFORCE_OFF,
    BLOCKER_IN_FLIGHT,
    BLOCKER_MULTIPLE_CALLBACKS,
    BLOCKER_NOT_OPEN,
    BLOCKER_NOT_REPLAYABLE,
    BLOCKER_RISK,
    BLOCKER_SHAPE_GONE,
    BLOCKER_SUCCESSOR,
    apply_plan,
    plan_replay,
    replay_case,
    settle_recoveries,
)
from pipeline.contrib.diagnostics.signatures import build_context, evaluate
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import (
    ROOT,
    ago,
    callback_shape,
    fork_parent,
    make_node,
    make_process,
    make_state,
    poll_shape,
    running_root,
    s1_shape,
)
from pipeline.eri.models import Process, Schedule, State


def open_case(process):
    [(_process, hit)] = evaluate([process], build_context([process]), slow=True)
    return upsert_case(ROOT, hit.related_objects["node_id"], hit)


def open_callback_case():
    _process, schedule, callback = callback_shape()
    backfill_callbacks(callback.id, dry_run=False, confirm_seconds=0)
    return DiagnosticCase.objects.get(stuck_type=CALLBACK_DISPATCH_LOST), schedule, callback


def dead_child(parent, beat=600):
    return make_process(node="cg", beat=ago(beat), dead=True, asleep=False, parent_id=parent.id, destination_id="cg")


def new_child(parent, node="b1"):
    make_node(node)
    return make_process(node=node, beat=ago(600), parent_id=parent.id, destination_id="cg")


def recovery_count(stuck_type, trigger, result):
    labels = {"stuck_type": stuck_type, "trigger": trigger, "result": result, "hostname": metrics.HOST_NAME}
    return metrics.DIAGNOSTICS_RECOVERY.labels(**labels)._value.get()


class RecoveryTestCase(DiagnosticsTestCase):
    def setUp(self):
        super(RecoveryTestCase, self).setUp()
        running_root()
        runtime_patcher = mock.patch("pipeline.contrib.diagnostics.recovery._runtime")
        self.runtime = runtime_patcher.start().return_value
        self.addCleanup(runtime_patcher.stop)
        self.runtime.get_process_info.return_value = SimpleNamespace(root_pipeline_id=ROOT, top_pipeline_id=ROOT)
        fence_patcher = mock.patch.multiple(Settings, FENCE_EMIT_ENABLED=True, FENCE_ENFORCE=True)
        fence_patcher.start()
        self.addCleanup(fence_patcher.stop)


class ReplayPlanTest(RecoveryTestCase):
    def test_s1_replays_execute_to_unique_successor(self):
        process = s1_shape()
        plan = plan_replay(open_case(process))
        self.assertEqual(plan.blockers, [])
        self.assertEqual(plan.fingerprint, "execute_dispatch_lost:{}:a:v1".format(process.id))
        self.assertEqual(
            plan.message,
            {
                "kind": "execute",
                "process_id": process.id,
                "node_id": "a-next",
                "root_pipeline_id": ROOT,
                "parent_pipeline_id": ROOT,
                "fence": {"from_node": "a", "from_version": "v1"},
            },
        )

    def test_s1_with_several_successors_is_blocked(self):
        process = make_process(node="a", beat=ago(900))
        make_node("a", targets={"f1": "x", "f2": "y"})
        make_state("a", name="FINISHED", started=ago(900), archived=ago(600))
        plan = plan_replay(open_case(process))
        self.assertEqual((plan.message, plan.blockers), (None, [BLOCKER_SUCCESSOR]))

    def test_s5_wakes_parent_at_converge_gateway(self):
        parent = fork_parent(need_ack=-1)
        plan = plan_replay(open_case(dead_child(parent)))
        self.assertEqual(plan.blockers, [])
        self.assertEqual((plan.message["process_id"], plan.message["node_id"]), (parent.id, "cg"))
        self.assertEqual(plan.message["fence"], {"from_node": "pg", "from_version": "v1"})

    def test_s6_starts_child_with_empty_version(self):
        child = new_child(fork_parent(need_ack=2))
        plan = plan_replay(open_case(child))
        self.assertEqual((plan.message["process_id"], plan.message["node_id"]), (child.id, "b1"))
        self.assertEqual(plan.message["fence"], {"from_node": "b1", "from_version": None})

    def test_s6_keeps_version_left_by_previous_loop(self):
        child = new_child(fork_parent(need_ack=2))
        make_state("b1", name="FINISHED", version="old", archived=ago(3000))
        plan = plan_replay(open_case(child))
        self.assertEqual(plan.message["fence"], {"from_node": "b1", "from_version": "old"})

    def test_poll_uses_current_schedule_times(self):
        process = poll_shape(beat=2000, times=3)
        case = open_case(process)
        Schedule.objects.filter(node_id="p").update(schedule_times=4)
        plan = plan_replay(case)
        schedule = Schedule.objects.get(node_id="p")
        self.assertEqual(plan.fingerprint, "poll_dispatch_lost:{}:p:v1:4".format(process.id))
        self.assertEqual(
            plan.message,
            {
                "kind": "poll",
                "process_id": process.id,
                "node_id": "p",
                "schedule_id": schedule.id,
                "fence": {"schedule_times": 4},
            },
        )

    def test_shape_gone_is_blocked(self):
        process = s1_shape()
        case = open_case(process)
        Process.objects.filter(id=process.id).update(current_node_id="a-next", asleep=False)
        plan = plan_replay(case)
        self.assertEqual((plan.fingerprint, plan.message, plan.blockers), ("", None, [BLOCKER_SHAPE_GONE]))

    def test_closed_case_is_not_replayed(self):
        case = open_case(s1_shape())
        DiagnosticCase.objects.filter(id=case.id).update(status=DiagnosticCase.STATUS_RESOLVED)
        case.refresh_from_db()
        self.assertEqual(plan_replay(case).blockers, [BLOCKER_NOT_OPEN])

    def test_rule_case_is_not_replayable(self):
        case = DiagnosticCase.objects.create(root_pipeline_id=ROOT, node_id="n1", stuck_type="stalled_no_progress")
        self.assertEqual(plan_replay(case).blockers, [BLOCKER_NOT_REPLAYABLE])

    def test_callback_replays_data_without_fence(self):
        case, schedule, callback = open_callback_case()
        with mock.patch.multiple(Settings, FENCE_EMIT_ENABLED=False, FENCE_ENFORCE=False):
            plan = plan_replay(case)
        self.assertEqual(plan.blockers, [])
        self.assertEqual(
            plan.message,
            {
                "kind": "callback",
                "process_id": schedule.process_id,
                "node_id": "cb",
                "schedule_id": schedule.id,
                "callback_data_id": callback.id,
                "fence": None,
            },
        )

    def test_callback_being_scheduled_is_blocked(self):
        case, schedule, _callback = open_callback_case()
        Schedule.objects.filter(id=schedule.id).update(scheduling=True)
        self.assertEqual(plan_replay(case).blockers, [BLOCKER_CALLBACK_SCHEDULING])

    def test_callback_case_hit_twice_is_blocked(self):
        case, _schedule, _callback = open_callback_case()
        DiagnosticCase.objects.filter(id=case.id).update(hit_count=2)
        case.refresh_from_db()
        self.assertEqual(plan_replay(case).blockers, [BLOCKER_MULTIPLE_CALLBACKS])


class ReplaySafetyTest(RecoveryTestCase):
    def test_enforce_off_blocks_execute_and_poll(self):
        s1_case = open_case(s1_shape())
        poll_case = open_case(poll_shape())
        with mock.patch.object(Settings, "FENCE_ENFORCE", False):
            self.assertEqual(plan_replay(s1_case).blockers, [BLOCKER_ENFORCE_OFF])
            self.assertEqual(plan_replay(poll_case).blockers, [BLOCKER_ENFORCE_OFF])

    def test_emit_off_needs_risk_confirmation(self):
        case = open_case(s1_shape())
        with mock.patch.object(Settings, "FENCE_EMIT_ENABLED", False):
            self.assertEqual(plan_replay(case).blockers, [BLOCKER_RISK])
            self.assertEqual(plan_replay(case, confirm_risk=True).blockers, [])
            auto = plan_replay(case, trigger=DiagnosticRecovery.TRIGGER_AUTO, confirm_risk=True)
            self.assertEqual(auto.blockers, [BLOCKER_EMIT_OFF])

    def test_unsettled_dispatch_blocks_another(self):
        case = open_case(s1_shape())
        apply_plan(plan_replay(case), DiagnosticRecovery.TRIGGER_MANUAL, "admin")
        self.assertEqual(plan_replay(case).blockers, [BLOCKER_IN_FLIGHT])
        DiagnosticRecovery.objects.update(created_at=ago(200))
        self.assertEqual(plan_replay(case).blockers, [])


class ReplayCaseTest(RecoveryTestCase):
    def test_dry_run_returns_message_and_audits(self):
        case = open_case(s1_shape())
        result = replay_case(case.id, "admin")
        self.assertTrue(result.result)
        self.assertEqual(result.data["message"]["node_id"], "a-next")
        self.assertFalse(result.data["requires_risk_confirm"])
        self.assertFalse(DiagnosticRecovery.objects.exists())
        self.runtime.execute.assert_not_called()
        audit = DiagnosticOperationAudit.objects.get()
        self.assertEqual((audit.case_id, audit.operation_type, audit.mode), (case.id, "replay_case", "dry_run"))
        self.assertEqual(audit.risk_level, DiagnosticOperationAudit.RISK_LEVEL_HIGH)

    def test_apply_requires_apply_switch(self):
        case = open_case(s1_shape())
        result = replay_case(case.id, "admin", mode="apply")
        self.assertEqual((result.result, result.blockers), (False, [BLOCKER_APPLY_DISABLED]))
        self.runtime.execute.assert_not_called()
        self.assertEqual(DiagnosticOperationAudit.objects.get().precheck_result, {"blockers": [BLOCKER_APPLY_DISABLED]})

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_apply_dispatches_execute_with_fence(self):
        process = s1_shape()
        case = open_case(process)
        before = recovery_count(EXECUTE_DISPATCH_LOST, "manual", "dispatched")
        result = replay_case(case.id, "admin", mode="apply")
        self.assertTrue(result.result)
        self.runtime.execute.assert_called_once_with(
            process_id=process.id,
            node_id="a-next",
            root_pipeline_id=ROOT,
            parent_pipeline_id=ROOT,
            headers={"fence": {"from_node": "a", "from_version": "v1"}},
        )
        recovery = DiagnosticRecovery.objects.get()
        self.assertEqual(result.data["recovery_id"], recovery.id)
        self.assertEqual(
            (recovery.case_id, recovery.trigger, recovery.mode, recovery.status, recovery.operator),
            (case.id, "manual", "apply", "dispatched", "admin"),
        )
        self.assertEqual(recovery_count(EXECUTE_DISPATCH_LOST, "manual", "dispatched") - before, 1)

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_apply_dispatches_first_poll(self):
        process = poll_shape()
        result = replay_case(open_case(process).id, "admin", mode="apply")
        self.assertTrue(result.result)
        self.runtime.schedule.assert_called_once_with(
            process_id=process.id,
            node_id="p",
            schedule_id=Schedule.objects.get(node_id="p").id,
            callback_data_id=None,
            headers={"fence": {"schedule_times": 0}},
        )

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_apply_dispatches_callback_without_headers(self):
        case, schedule, callback = open_callback_case()
        replay_case(case.id, "admin", mode="apply")
        self.runtime.schedule.assert_called_once_with(
            process_id=schedule.process_id,
            node_id="cb",
            schedule_id=schedule.id,
            callback_data_id=callback.id,
            headers={},
        )

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_dispatch_failure_is_recorded(self):
        case = open_case(s1_shape())
        self.runtime.execute.side_effect = Exception("broker down")
        result = replay_case(case.id, "admin", mode="apply")
        self.assertEqual((result.result, result.blockers), (False, [BLOCKER_DISPATCH_FAILED]))
        recovery = DiagnosticRecovery.objects.get()
        self.assertEqual(recovery.status, DiagnosticRecovery.STATUS_BLOCKED)
        self.assertEqual(recovery.detail["error"], "broker down")

    def test_risk_flag_for_console(self):
        case = open_case(s1_shape())
        with mock.patch.object(Settings, "FENCE_EMIT_ENABLED", False):
            result = replay_case(case.id, "admin")
        self.assertEqual((result.result, result.data["requires_risk_confirm"]), (False, True))

    def test_missing_case(self):
        self.assertFalse(replay_case(999999, "admin").result)
        self.assertFalse(DiagnosticOperationAudit.objects.exists())


class SettleTest(RecoveryTestCase):
    def dispatch(self, case):
        recovery, _error = apply_plan(plan_replay(case), DiagnosticRecovery.TRIGGER_MANUAL, "admin")
        DiagnosticRecovery.objects.filter(id=recovery.id).update(created_at=ago(200))
        return recovery

    def settled(self, recovery):
        recovery.refresh_from_db()
        return recovery.status, recovery.detail.get("settled_holds"), recovery.settled_at is not None

    def test_applied_when_shape_gone(self):
        process = s1_shape()
        recovery = self.dispatch(open_case(process))
        Process.objects.filter(id=process.id).update(
            current_node_id="a-next", asleep=False, last_heartbeat=timezone.now()
        )
        before = recovery_count(EXECUTE_DISPATCH_LOST, "manual", "applied")
        self.assertEqual(settle_recoveries(), {"applied": 1})
        self.assertEqual(self.settled(recovery), ("applied", False, True))
        self.assertEqual(recovery_count(EXECUTE_DISPATCH_LOST, "manual", "applied") - before, 1)

    def test_ineffective_when_shape_holds(self):
        recovery = self.dispatch(open_case(s1_shape()))
        settle_recoveries()
        self.assertEqual(self.settled(recovery), ("ineffective", True, True))

    def test_obsolete_when_root_stopped(self):
        recovery = self.dispatch(open_case(s1_shape()))
        State.objects.filter(node_id=ROOT).update(name="REVOKED")
        settle_recoveries()
        self.assertEqual(self.settled(recovery), ("obsolete", False, True))

    def test_recent_dispatch_waits_for_window(self):
        case = open_case(s1_shape())
        recovery, _error = apply_plan(plan_replay(case), DiagnosticRecovery.TRIGGER_MANUAL, "admin")
        self.assertEqual(settle_recoveries(), {})
        self.assertEqual(self.settled(recovery), ("dispatched", None, False))

    def test_poll_counts_as_applied_once_schedule_times_move(self):
        recovery = self.dispatch(open_case(poll_shape(beat=2000, times=3)))
        Schedule.objects.filter(node_id="p").update(schedule_times=4)
        settle_recoveries()
        self.assertEqual(self.settled(recovery), ("applied", False, True))

    def test_callback_applied_after_schedule_finished(self):
        case, schedule, _callback = open_callback_case()
        recovery = self.dispatch(case)
        Schedule.objects.filter(id=schedule.id).update(finished=True)
        settle_recoveries()
        self.assertEqual(self.settled(recovery)[0], "applied")

    def test_preview_rows_only_record_holds(self):
        case = open_case(s1_shape())
        preview = DiagnosticRecovery.objects.create(
            case=case,
            root_pipeline_id=ROOT,
            node_id="a",
            stuck_type=EXECUTE_DISPATCH_LOST,
            fingerprint="f",
            trigger="auto",
            mode="preview",
            status="previewed",
        )
        DiagnosticRecovery.objects.filter(id=preview.id).update(created_at=ago(200))
        self.assertEqual(settle_recoveries(), {"preview_holds": 1})
        self.assertEqual(self.settled(preview), ("previewed", True, True))

    def test_failed_row_does_not_block_the_rest(self):
        case = open_case(s1_shape())
        recovery = self.dispatch(case)
        preview = DiagnosticRecovery.objects.create(
            case=case,
            root_pipeline_id=ROOT,
            node_id="a",
            stuck_type=EXECUTE_DISPATCH_LOST,
            fingerprint="f",
            trigger="auto",
            mode="preview",
            status="previewed",
        )
        DiagnosticRecovery.objects.filter(id=preview.id).update(created_at=ago(200))
        with mock.patch("pipeline.contrib.diagnostics.recovery._still_stuck", side_effect=[RuntimeError("boom"), True]):
            self.assertEqual(settle_recoveries(), {"error": 1, "preview_holds": 1})
        self.assertEqual(self.settled(recovery), ("dispatched", None, False))
        self.assertEqual(self.settled(preview), ("previewed", True, True))

    def test_deleted_case_settles_as_obsolete(self):
        case = open_case(s1_shape())
        recovery = self.dispatch(case)
        DiagnosticCase.objects.filter(id=case.id).delete()
        self.assertEqual(settle_recoveries(), {"obsolete": 1})
        self.assertEqual(self.settled(recovery), ("obsolete", None, True))
        self.assertNotIn("settled_holds", recovery.detail)

    def test_preview_of_deleted_case_is_not_counted(self):
        case = open_case(s1_shape())
        preview = DiagnosticRecovery.objects.create(
            case=case,
            root_pipeline_id=ROOT,
            node_id="a",
            stuck_type=EXECUTE_DISPATCH_LOST,
            fingerprint="f",
            trigger="auto",
            mode="preview",
            status="previewed",
        )
        DiagnosticRecovery.objects.filter(id=preview.id).update(created_at=ago(200))
        DiagnosticCase.objects.filter(id=case.id).delete()
        self.assertEqual(settle_recoveries(), {"preview_gone": 1})
        self.assertEqual(self.settled(preview), ("previewed", None, True))
        self.assertNotIn("settled_holds", preview.detail)

    def test_callback_still_scheduling_is_ineffective(self):
        case, schedule, _callback = open_callback_case()
        recovery = self.dispatch(case)
        Schedule.objects.filter(id=schedule.id).update(scheduling=True)
        settle_recoveries()
        self.assertEqual(self.settled(recovery), ("ineffective", True, True))
