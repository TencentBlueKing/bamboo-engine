import threading
from concurrent.futures import ThreadPoolExecutor

import mock
from django.db import connection, connections
from django.test import override_settings

from bamboo_engine.config import Settings
from pipeline.contrib.diagnostics.cases import upsert_case
from pipeline.contrib.diagnostics.case_types import SYNC_ADVANCE_STALLED
from pipeline.contrib.diagnostics.recovery import dispatch, plan_replay
from pipeline.contrib.diagnostics.signature_scan import _candidates
from pipeline.contrib.diagnostics.signatures import build_context, evaluate
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import ago, make_schedule, running_root, s1_shape
from pipeline.eri.models import Process, State, SyncAdvanceCheckpoint
from pipeline.eri.runtime import BambooDjangoRuntime


@override_settings(PIPELINE_DIAGNOSTICS_SYNC_ADVANCE_ENABLED=True)
class SyncAdvanceTest(DiagnosticsTestCase):
    def setUp(self):
        super(SyncAdvanceTest, self).setUp()
        running_root()
        self.runtime = BambooDjangoRuntime()
        self.p = s1_shape()
        Process.objects.filter(id=self.p.id).update(asleep=False, pipeline_stack='["root-1"]')
        self.p.refresh_from_db()
        self.switches = mock.patch.multiple(
            Settings, SYNC_ADVANCE_CHECKPOINT_ENABLED=True, FENCE_EMIT_ENABLED=True, FENCE_ENFORCE=True
        )
        self.switches.start()
        self.addCleanup(self.switches.stop)

    def prepare(self):
        self.assertTrue(self.runtime.prepare_sync_advance(self.p.id, "a", "v1", "a-next"))
        SyncAdvanceCheckpoint.objects.filter(process_id=self.p.id).update(prepared_at=ago(500))
        Process.objects.filter(id=self.p.id).update(last_heartbeat=ago(500))

    def hits(self):
        self.p.refresh_from_db()
        return [hit for _, hit in evaluate([self.p], build_context([self.p]), slow=False)]

    def case(self):
        [hit] = self.hits()
        return upsert_case(self.p.root_pipeline_id, "a", hit)

    def release(self):
        return self.runtime.release_sync_advance(self.p.id, "a", "v1", "a-next", 300)

    def test_missing_checkpoint_detected_but_cannot_replay_even_with_risk_confirmation(self):
        case = self.case()
        self.assertEqual(case.stuck_type, SYNC_ADVANCE_STALLED)
        plan = plan_replay(case, confirm_risk=True)
        self.assertIsNone(plan.message)
        self.assertIn("manual investigation", plan.blockers[0])
        self.assertFalse(self.release())
        self.assertFalse(Process.objects.get(id=self.p.id).asleep)

    def test_normal_worker_claim_wins_and_recovery_cannot_steal(self):
        self.prepare()
        self.assertTrue(self.runtime.claim_sync_advance(self.p.id, "a", "v1"))
        self.assertFalse(self.release())
        self.assertFalse(self.runtime.claim_sync_advance(self.p.id, "a", "v1"))
        self.assertFalse(self.runtime.prepare_sync_advance(self.p.id, "a", "v1", "a-next"))
        self.assertTrue(plan_replay(self.case()).blockers)

    def test_recovery_wins_and_old_worker_must_exit(self):
        self.prepare()
        self.assertTrue(self.release())
        self.assertFalse(self.runtime.claim_sync_advance(self.p.id, "a", "v1"))
        self.assertFalse(self.runtime.prepare_sync_advance(self.p.id, "a", "v1", "a-next"))
        self.assertTrue(Process.objects.get(id=self.p.id).asleep)
        self.assertEqual(SyncAdvanceCheckpoint.objects.get(process_id=self.p.id).phase, "RELEASED")
        self.assertEqual([hit.type for hit in self.hits()], [SYNC_ADVANCE_STALLED])
        self.assertTrue(self.release())  # A lost re-dispatch remains recoverable.

    def test_preview_has_no_process_or_checkpoint_writes(self):
        self.prepare()
        before = list(SyncAdvanceCheckpoint.objects.values())
        plan = plan_replay(self.case())
        self.assertEqual(plan.blockers, [])
        self.assertTrue(plan.message["sync_advance"])
        self.assertEqual(before, list(SyncAdvanceCheckpoint.objects.values()))
        self.assertFalse(Process.objects.get(id=self.p.id).asleep)

    def test_dispatch_failure_keeps_released_checkpoint_for_retry(self):
        self.prepare()
        message = plan_replay(self.case()).message
        with mock.patch.object(BambooDjangoRuntime, "execute", side_effect=RuntimeError("broker down")):
            with self.assertRaises(RuntimeError):
                dispatch(message)
        self.assertEqual(SyncAdvanceCheckpoint.objects.get(process_id=self.p.id).phase, "RELEASED")
        with mock.patch.object(BambooDjangoRuntime, "execute") as send:
            dispatch(message)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args[1]["headers"]["fence"], {"from_node": "a", "from_version": "v1"})

    def test_stale_preview_is_rechecked_under_lock(self):
        self.prepare()
        plan = plan_replay(self.case())
        State.objects.filter(node_id="a").update(version="v2")
        with mock.patch.object(BambooDjangoRuntime, "execute") as send:
            with self.assertRaises(ValueError):
                dispatch(plan.message)
            send.assert_not_called()

    def test_recent_checkpoint_is_not_a_stall_even_if_plugin_ran_for_hours(self):
        self.assertTrue(self.runtime.prepare_sync_advance(self.p.id, "a", "v1", "a-next"))
        self.assertEqual(self.hits(), [])
        self.assertFalse(self.release())

    def test_wrong_target_or_parked_process_cannot_be_taken(self):
        self.prepare()
        self.assertFalse(self.runtime.release_sync_advance(self.p.id, "a", "v1", "wrong", 300))
        for field in ("suspended", "frozen", "dead"):
            Process.objects.filter(id=self.p.id).update(**{field: True})
            self.assertFalse(self.release())
            Process.objects.filter(id=self.p.id).update(**{field: False})
        State.objects.filter(node_id=self.p.root_pipeline_id).update(name="REVOKED")
        self.assertFalse(self.release())

    def test_schedule_skip_and_ignored_errors_cannot_be_recovered(self):
        self.prepare()
        for field in ("skip", "error_ignored"):
            State.objects.filter(node_id="a").update(**{field: True})
            self.assertFalse(self.release())
            self.assertTrue(plan_replay(self.case(), confirm_risk=True).blockers)
            State.objects.filter(node_id="a").update(**{field: False})
        make_schedule(self.p, "a", finished=True)
        self.assertFalse(self.release())
        self.assertEqual(self.hits(), [])

    def test_inactive_feature_keeps_awake_process_out_of_signature_scan(self):
        with override_settings(PIPELINE_DIAGNOSTICS_SYNC_ADVANCE_ENABLED=False):
            self.assertFalse(_candidates().filter(id=self.p.id).exists())
            self.assertEqual(self.hits(), [])
        self.assertTrue(_candidates().filter(id=self.p.id).exists())

    def test_recovery_requires_both_fences_even_with_manual_risk_confirmation(self):
        self.prepare()
        case = self.case()
        for switch in ("FENCE_ENFORCE", "FENCE_EMIT_ENABLED", "SYNC_ADVANCE_CHECKPOINT_ENABLED"):
            with mock.patch.object(Settings, switch, False):
                self.assertTrue(plan_replay(case, confirm_risk=True).blockers)

    def test_release_updates_rollback_together(self):
        self.prepare()
        with mock.patch.object(Process, "save", side_effect=RuntimeError("write interrupted")):
            with self.assertRaises(RuntimeError):
                self.release()
        self.assertEqual(SyncAdvanceCheckpoint.objects.get(process_id=self.p.id).phase, "READY")
        self.assertFalse(Process.objects.get(id=self.p.id).asleep)

    def test_simultaneous_claim_and_recovery_have_exactly_one_winner(self):
        if connection.vendor != "mysql":
            self.skipTest("requires production-like row locks")
        self.prepare()
        barrier = threading.Barrier(2)

        def compete(recovery):
            try:
                barrier.wait(timeout=5)
                return self.release() if recovery else self.runtime.claim_sync_advance(self.p.id, "a", "v1")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(compete, flag) for flag in (False, True)]
            outcomes = [future.result(timeout=10) for future in futures]
        self.assertEqual(outcomes.count(True), 1)

    def test_checkpoint_is_removed_with_process(self):
        self.prepare()
        self.p.delete()
        self.assertFalse(SyncAdvanceCheckpoint.objects.exists())

    def test_late_interrupt_retry_does_not_wake_released_process(self):
        self.prepare()
        self.assertTrue(self.release())
        self.assertFalse(self.runtime.wake_sync_recovery(self.p.id, "a", "v1"))
        self.assertTrue(Process.objects.get(id=self.p.id).asleep)

    def test_old_runtime_can_delete_process_without_knowing_checkpoint_model(self):
        self.prepare()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM {} WHERE id = %s".format(connection.ops.quote_name(Process._meta.db_table)), [self.p.id]
            )
        # No database FK prevents rollback to the previous runtime. Its orphan is retained for cleanup.
        self.assertTrue(SyncAdvanceCheckpoint.objects.filter(process_id=self.p.id).exists())
