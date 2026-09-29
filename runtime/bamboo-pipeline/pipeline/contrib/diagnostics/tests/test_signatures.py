# -*- coding: utf-8 -*-

from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.diagnostics.case_types import (
    CHILD_START_LOST,
    EXECUTE_DISPATCH_LOST,
    PARENT_WAKEUP_LOST,
    POLL_DISPATCH_LOST,
)
from pipeline.contrib.diagnostics.cases import close_stale_cases, upsert_case
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.signatures import (
    build_context,
    close_resolved_signature_cases,
    detect_child_start_lost,
    detect_execute_dispatch_lost,
    detect_parent_wakeup_lost,
    detect_poll_dispatch_lost,
    evaluate,
    matching_hit,
    still_holds,
)
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import (
    ROOT,
    ago,
    fork_parent,
    make_node,
    make_process,
    make_state,
    poll_shape,
    running_root,
    s1_shape,
)
from pipeline.eri.models import Process, Schedule, State


class SignatureTestCase(DiagnosticsTestCase):
    def setUp(self):
        super(SignatureTestCase, self).setUp()
        running_root()

    def detect(self, detector, process, **kwargs):
        return detector(process, build_context([process]), **kwargs)


class ExecuteDispatchLostTest(SignatureTestCase):
    def test_finished_node_with_sleeping_process(self):
        hit = self.detect(detect_execute_dispatch_lost, s1_shape())
        self.assertEqual(hit.type, EXECUTE_DISPATCH_LOST)
        self.assertEqual(hit.evidence["signature"], "S1")
        self.assertEqual(hit.related_objects["next_node_ids"], ["a-next"])
        self.assertIn("execute(process_id=", hit.evidence["derived_message"])

    def test_finished_state_left_by_previous_loop_is_not_s1(self):
        self.assertIsNone(self.detect(detect_execute_dispatch_lost, s1_shape(beat=600, archived=900)))

    def test_recently_finished_node_waits_for_threshold(self):
        self.assertIsNone(self.detect(detect_execute_dispatch_lost, s1_shape(beat=900, archived=60)))

    def test_parent_waiting_on_fork_gateway_is_not_s1(self):
        process = make_process(node="pg", beat=ago(900), need_ack=2)
        make_node("pg", node_type="ParallelGateway", converge_gateway_id="cg")
        make_state("pg", name="FINISHED", version="v1", archived=ago(600))
        self.assertIsNone(self.detect(detect_execute_dispatch_lost, process))

    def test_parked_process_is_ignored(self):
        process = s1_shape()
        Process.objects.filter(id=process.id).update(suspended=True)
        process.refresh_from_db()
        self.assertIsNone(self.detect(detect_execute_dispatch_lost, process))


class PollDispatchLostTest(SignatureTestCase):
    def test_first_poll_never_consumed(self):
        hit = self.detect(detect_poll_dispatch_lost, poll_shape(), continuation=False)
        self.assertEqual((hit.type, hit.evidence["signature"]), (POLL_DISPATCH_LOST, "S2"))
        self.assertIn("schedule(process_id=", hit.evidence["derived_message"])

    def test_first_poll_already_consumed(self):
        self.assertIsNone(self.detect(detect_poll_dispatch_lost, poll_shape(times=1), continuation=False))

    def test_continuation_lost_after_slow_threshold(self):
        hit = self.detect(detect_poll_dispatch_lost, poll_shape(beat=2000, times=3), continuation=True)
        self.assertEqual(hit.evidence["signature"], "S3")

    def test_continuation_within_slow_threshold(self):
        self.assertIsNone(self.detect(detect_poll_dispatch_lost, poll_shape(beat=900, times=3), continuation=True))

    @override_settings(PIPELINE_DIAGNOSTICS_POLL_EXCLUDE_CODES="sleep_timer")
    def test_excluded_code_only_skips_continuation(self):
        slow = poll_shape(node="t1", beat=2000, times=3, code="sleep_timer")
        first = poll_shape(node="t2", code="sleep_timer")
        self.assertIsNone(self.detect(detect_poll_dispatch_lost, slow, continuation=True))
        self.assertIsNotNone(self.detect(detect_poll_dispatch_lost, first, continuation=False))

    def test_schedule_in_progress_is_ignored(self):
        process = poll_shape()
        Schedule.objects.filter(node_id="p").update(scheduling=True)
        self.assertIsNone(self.detect(detect_poll_dispatch_lost, process, continuation=False))


class EvaluateTest(SignatureTestCase):
    def test_fast_tier_skips_continuation(self):
        process = poll_shape(beat=2000, times=3)
        self.assertEqual(evaluate([process], build_context([process]), slow=False), [])
        self.assertEqual(len(evaluate([process], build_context([process]), slow=True)), 1)

    def test_inactive_root_is_skipped(self):
        State.objects.filter(node_id=ROOT).update(name="REVOKED")
        process = s1_shape()
        self.assertEqual(evaluate([process], build_context([process]), slow=True), [])


class StaleCaseCloseTest(DiagnosticsTestCase):
    def test_root_progress_does_not_close_signature_cases(self):
        make_process(root="busy", beat=ago(10))
        DiagnosticCase.objects.create(root_pipeline_id="busy", node_id="n", stuck_type=EXECUTE_DISPATCH_LOST)
        DiagnosticCase.objects.create(root_pipeline_id="busy", node_id="n", stuck_type="stalled_no_progress")
        self.assertEqual(close_stale_cases(1800), 1)
        self.assertEqual(
            DiagnosticCase.objects.get(stuck_type=EXECUTE_DISPATCH_LOST).status, DiagnosticCase.STATUS_OPEN
        )


class ParentWakeupLostTest(SignatureTestCase):
    def _dead_child(self, parent, beat):
        return make_process(
            node="cg", beat=ago(beat), dead=True, asleep=False, parent_id=parent.id, destination_id="cg"
        )

    def test_all_children_dead_and_parent_not_woken(self):
        parent = fork_parent(need_ack=-1)
        self._dead_child(parent, 700)
        hit = self.detect(detect_parent_wakeup_lost, self._dead_child(parent, 600))
        self.assertEqual(hit.type, PARENT_WAKEUP_LOST)
        self.assertEqual((hit.related_objects["process_id"], hit.related_objects["node_id"]), (parent.id, "pg"))
        self.assertIn("node_id=cg", hit.evidence["derived_message"])

    def test_live_sibling_means_not_converged_yet(self):
        parent = fork_parent(need_ack=-1)
        make_process(node="b2", beat=ago(900), parent_id=parent.id, destination_id="cg")
        self.assertIsNone(self.detect(detect_parent_wakeup_lost, self._dead_child(parent, 600)))

    def test_recent_finish_waits_for_threshold(self):
        parent = fork_parent(need_ack=-1)
        self.assertIsNone(self.detect(detect_parent_wakeup_lost, self._dead_child(parent, 60)))

    def test_child_from_earlier_loop_round_is_ignored(self):
        parent = fork_parent(need_ack=-1)
        self.assertIsNone(self.detect(detect_parent_wakeup_lost, self._dead_child(parent, 1500)))
        self.assertIsNotNone(self.detect(detect_parent_wakeup_lost, self._dead_child(parent, 600)))


class ChildStartLostTest(SignatureTestCase):
    def _child(self, parent, node="b1"):
        make_node(node)
        return make_process(node=node, beat=ago(600), parent_id=parent.id, destination_id="cg")

    def test_child_never_started(self):
        parent = fork_parent(need_ack=2)
        hit = self.detect(detect_child_start_lost, self._child(parent))
        self.assertEqual((hit.type, hit.related_objects["parent_process_id"]), (CHILD_START_LOST, parent.id))

    def test_state_left_by_previous_loop_is_s6_not_s1(self):
        parent = fork_parent(need_ack=2)
        child = self._child(parent)
        make_state("b1", name="FINISHED", version="old", archived=ago(3000))
        self.assertIsNotNone(self.detect(detect_child_start_lost, child))
        self.assertIsNone(self.detect(detect_execute_dispatch_lost, child))

    def test_started_child_is_not_s6(self):
        parent = fork_parent(need_ack=2)
        child = self._child(parent)
        make_state("b1", name="RUNNING", version="v1", started=ago(590))
        self.assertIsNone(self.detect(detect_child_start_lost, child))


class SignatureCloseTest(SignatureTestCase):
    def test_case_closes_after_process_moves_on(self):
        process = s1_shape()
        [(_process, hit)] = evaluate([process], build_context([process]), slow=False)
        case = upsert_case(ROOT, hit.related_objects["node_id"], hit)
        self.assertTrue(still_holds(case))
        Process.objects.filter(id=process.id).update(
            current_node_id="a-next", asleep=False, last_heartbeat=timezone.now()
        )
        self.assertFalse(still_holds(case))
        self.assertEqual(close_resolved_signature_cases([EXECUTE_DISPATCH_LOST]), 1)
        self.assertEqual(DiagnosticCase.objects.get(id=case.id).status, DiagnosticCase.STATUS_RESOLVED)

    def test_parent_wakeup_case_is_rechecked_through_child(self):
        parent = fork_parent(need_ack=-1)
        child = make_process(
            node="cg", beat=ago(600), dead=True, asleep=False, parent_id=parent.id, destination_id="cg"
        )
        [(_process, hit)] = evaluate([child], build_context([child]), slow=False)
        case = upsert_case(ROOT, hit.related_objects["node_id"], hit)
        self.assertTrue(still_holds(case))
        Process.objects.filter(id=parent.id).update(current_node_id="cg", asleep=False)
        self.assertFalse(still_holds(case))

    def test_matching_hit_reads_current_state(self):
        process = poll_shape(beat=2000, times=3)
        [(_process, hit)] = evaluate([process], build_context([process]), slow=True)
        case = upsert_case(ROOT, hit.related_objects["node_id"], hit)
        Schedule.objects.filter(node_id="p").update(schedule_times=5)
        self.assertEqual(matching_hit(case).evidence["schedule_times"], 5)
        State.objects.filter(node_id="p").update(version="v2")
        self.assertIsNone(matching_hit(case))

    def test_holding_cases_rotate_by_updated_at(self):
        first = DiagnosticCase.objects.create(root_pipeline_id=ROOT, node_id="x1", stuck_type=EXECUTE_DISPATCH_LOST)
        second = DiagnosticCase.objects.create(root_pipeline_id=ROOT, node_id="x2", stuck_type=EXECUTE_DISPATCH_LOST)
        seen = []

        def holds(case):
            seen.append(case.id)
            return True

        now = timezone.now()
        close_resolved_signature_cases([EXECUTE_DISPATCH_LOST], holds=holds, now=now, batch=1)
        close_resolved_signature_cases([EXECUTE_DISPATCH_LOST], holds=holds, now=now + timedelta(seconds=1), batch=1)
        self.assertEqual(seen, [first.id, second.id])
