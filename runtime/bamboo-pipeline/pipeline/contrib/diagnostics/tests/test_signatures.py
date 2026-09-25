# -*- coding: utf-8 -*-

from django.test import override_settings

from pipeline.contrib.diagnostics.case_types import EXECUTE_DISPATCH_LOST, POLL_DISPATCH_LOST
from pipeline.contrib.diagnostics.cases import close_stale_cases
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.signatures import (
    build_context,
    detect_execute_dispatch_lost,
    detect_poll_dispatch_lost,
    evaluate,
)
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import (
    ROOT,
    ago,
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
