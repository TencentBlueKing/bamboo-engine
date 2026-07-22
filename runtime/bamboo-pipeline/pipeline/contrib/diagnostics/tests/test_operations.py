# -*- coding: utf-8 -*-

from django.test import override_settings

from pipeline.contrib.diagnostics.models import DiagnosticOperationAudit
from pipeline.contrib.diagnostics.operations import (
    expire_stale_schedule,
    inspect_ack_converge,
    inspect_node_runtime_readiness,
    replay_callback_data,
    resend_schedule,
)
from pipeline.eri.models import CallbackData, Process, Schedule, State
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase


class DiagnosticOperationsTestCase(DiagnosticsTestCase):
    def setUp(self):
        super(DiagnosticOperationsTestCase, self).setUp()
        self.process_ids = []
        self.state_ids = []
        self.schedule_ids = []
        self.callback_data_ids = []

    def tearDown(self):
        CallbackData.objects.filter(id__in=self.callback_data_ids).delete()
        Schedule.objects.filter(id__in=self.schedule_ids).delete()
        State.objects.filter(id__in=self.state_ids).delete()
        Process.objects.filter(id__in=self.process_ids).delete()
        super(DiagnosticOperationsTestCase, self).tearDown()

    def _create_process(self, process_id, root_pipeline_id="root-op", node_id="node-op", **kwargs):
        defaults = {
            "id": process_id,
            "root_pipeline_id": root_pipeline_id,
            "current_node_id": node_id,
            "destination_id": "",
            "priority": 1,
            "queue": "diagnostics",
            "pipeline_stack": "[]",
        }
        defaults.update(kwargs)
        process = Process.objects.create(**defaults)
        self.process_ids.append(process.id)
        return process

    def _create_state(self, node_id="node-op", root_pipeline_id="root-op", version="v1", name="RUNNING"):
        state = State.objects.create(
            node_id=node_id,
            root_id=root_pipeline_id,
            parent_id="",
            name=name,
            version=version,
        )
        self.state_ids.append(state.id)
        return state

    def _create_schedule(self, schedule_id, process_id, node_id="node-op", version="v1", **kwargs):
        defaults = {
            "id": schedule_id,
            "process_id": process_id,
            "node_id": node_id,
            "version": version,
            "type": 1,
            "scheduling": True,
            "finished": False,
            "expired": False,
            "schedule_times": 1,
        }
        defaults.update(kwargs)
        schedule = Schedule.objects.create(**defaults)
        self.schedule_ids.append(schedule.id)
        return schedule

    def _create_callback_data(self, callback_data_id, node_id="node-op", version="v1", data="{}"):
        callback_data = CallbackData.objects.create(id=callback_data_id, node_id=node_id, version=version, data=data)
        self.callback_data_ids.append(callback_data.id)
        return callback_data

    def _latest_audit(self):
        return DiagnosticOperationAudit.objects.order_by("-id").first()

    def test_inspect_node_runtime_readiness_dry_run_writes_audit(self):
        process = self._create_process(301)
        state = self._create_state()
        schedule = self._create_schedule(301, process.id)
        self._create_callback_data(301)

        result = inspect_node_runtime_readiness("root-op", "node-op", operator="admin")
        audit = self._latest_audit()

        self.assertTrue(result.result)
        self.assertEqual(result.data["state"], state.name)
        self.assertEqual(result.data["processes"][0]["id"], process.id)
        self.assertEqual(result.data["schedules"][0]["id"], schedule.id)
        self.assertEqual(result.data["callback_data_count"], 1)
        self.assertEqual(audit.operation_type, "inspect_node_runtime_readiness")
        self.assertEqual(audit.operator, "admin")
        self.assertEqual(audit.mode, "dry_run")
        self.assertEqual(audit.risk_level, DiagnosticOperationAudit.RISK_LEVEL_LOW)

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=False)
    def test_apply_disabled_blocks_operation_and_writes_audit(self):
        process = self._create_process(302)
        schedule = self._create_schedule(302, process.id, expired=False)

        result = expire_stale_schedule(schedule.id, operator="admin", mode="apply")
        schedule.refresh_from_db()
        audit = self._latest_audit()

        self.assertFalse(result.result)
        self.assertIn("apply disabled", result.blockers)
        self.assertFalse(schedule.expired)
        self.assertEqual(audit.operation_type, "expire_stale_schedule")
        self.assertEqual(audit.mode, "apply")
        self.assertIn("apply disabled", audit.result["blockers"])

    def test_inspect_ack_converge_returns_ack_data(self):
        self._create_process(303, ack_num=1, need_ack=3)
        self._create_state()

        result = inspect_ack_converge("root-op", "node-op", operator="admin")
        audit = self._latest_audit()

        self.assertTrue(result.result)
        self.assertEqual(result.data["processes"][0]["ack_num"], 1)
        self.assertEqual(result.data["processes"][0]["need_ack"], 3)
        self.assertEqual(audit.operation_type, "inspect_ack_converge")

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_replay_callback_data_dry_run_and_apply(self):
        callback_data = self._create_callback_data(304)

        found = replay_callback_data(callback_data.id, operator="admin")
        missing = replay_callback_data(404304, operator="admin")
        applied = replay_callback_data(callback_data.id, operator="admin", mode="apply")

        self.assertTrue(found.result)
        self.assertEqual(found.data["callback_data_id"], callback_data.id)
        self.assertFalse(missing.result)
        self.assertIn("callback data not found", missing.blockers)
        self.assertFalse(applied.result)
        self.assertIn("requires dispatcher/runtime integration", applied.blockers)

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_resend_schedule_dry_run_and_apply(self):
        process = self._create_process(305)
        schedule = self._create_schedule(305, process.id)
        finished = self._create_schedule(306, process.id, node_id="node-op-finished", finished=True)
        expired = self._create_schedule(307, process.id, node_id="node-op-expired", expired=True)

        ok = resend_schedule(schedule.id, operator="admin")
        finished_result = resend_schedule(finished.id, operator="admin")
        expired_result = resend_schedule(expired.id, operator="admin")
        applied = resend_schedule(schedule.id, operator="admin", mode="apply")

        self.assertTrue(ok.result)
        self.assertFalse(finished_result.result)
        self.assertIn("schedule already finished", finished_result.blockers)
        self.assertFalse(expired_result.result)
        self.assertIn("schedule already expired", expired_result.blockers)
        self.assertFalse(applied.result)
        self.assertIn("requires dispatcher/runtime integration", applied.blockers)

    @override_settings(PIPELINE_DIAGNOSTICS_APPLY_ENABLED=True)
    def test_expire_stale_schedule_dry_run_and_apply(self):
        process = self._create_process(308)
        schedule = self._create_schedule(308, process.id, expired=False)
        finished = self._create_schedule(309, process.id, node_id="node-op-finished", finished=True)

        dry_run = expire_stale_schedule(schedule.id, operator="admin")
        schedule.refresh_from_db()
        self.assertTrue(dry_run.result)
        self.assertFalse(schedule.expired)

        applied = expire_stale_schedule(schedule.id, operator="admin", mode="apply")
        schedule.refresh_from_db()
        finished_result = expire_stale_schedule(finished.id, operator="admin", mode="apply")
        finished.refresh_from_db()

        self.assertTrue(applied.result)
        self.assertTrue(schedule.expired)
        self.assertFalse(finished_result.result)
        self.assertIn("schedule already finished", finished_result.blockers)
        self.assertFalse(finished.expired)
