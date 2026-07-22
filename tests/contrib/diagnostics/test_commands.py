# -*- coding: utf-8 -*-

import json
from datetime import timedelta
from io import StringIO

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.diagnostics.management.commands.diagnose_pipeline import Command as DiagnoseCommand
from pipeline.contrib.diagnostics.management.commands.scan_stuck_cases import Command as ScanCommand
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.scanner import diagnose_pipeline
from pipeline.eri.models import Process, Schedule, State
from tests.contrib.diagnostics.base import DiagnosticsTestCase


class DiagnosticsCommandTestCase(DiagnosticsTestCase):
    def setUp(self):
        super(DiagnosticsCommandTestCase, self).setUp()
        self.process_ids = []
        self.state_ids = []
        self.schedule_ids = []

    def tearDown(self):
        Schedule.objects.filter(id__in=self.schedule_ids).delete()
        State.objects.filter(id__in=self.state_ids).delete()
        Process.objects.filter(id__in=self.process_ids).delete()
        super(DiagnosticsCommandTestCase, self).tearDown()

    def _create_process(self, process_id, root_pipeline_id="root-command", node_id="node-command", **kwargs):
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

    def _create_state(self, node_id, root_pipeline_id="root-command", version="v1", name="RUNNING"):
        state = State.objects.create(
            node_id=node_id,
            root_id=root_pipeline_id,
            parent_id="",
            name=name,
            version=version,
        )
        self.state_ids.append(state.id)
        return state

    def _create_schedule(self, schedule_id, process_id, node_id, version="v1", **kwargs):
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

    def test_diagnose_pipeline_command_outputs_json(self):
        process = self._create_process(201)
        self._create_state("node-command")
        self._create_schedule(201, process.id, "node-command")

        stdout = StringIO()
        DiagnoseCommand(stdout=stdout).handle(root_pipeline_id="root-command", node_id="", process_id=None)
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload[0]["type"], "schedule_lock_stuck")
        self.assertEqual(payload[0]["related_objects"]["node_id"], "node-command")

    def test_scanner_diagnose_pipeline_supports_process_id_only(self):
        process = self._create_process(205, root_pipeline_id="root-process-only", node_id="node-process-only")
        self._create_state("node-process-only", root_pipeline_id="root-process-only")
        self._create_schedule(205, process.id, "node-process-only")

        hits = diagnose_pipeline(process_id=process.id)

        self.assertEqual([hit.type for hit in hits], ["schedule_lock_stuck"])
        self.assertEqual(hits[0].related_objects["node_id"], "node-process-only")

    def test_diagnose_pipeline_command_supports_process_id_only(self):
        process = self._create_process(206, root_pipeline_id="root-command-process", node_id="node-command-process")
        self._create_state("node-command-process", root_pipeline_id="root-command-process")
        self._create_schedule(206, process.id, "node-command-process")

        stdout = StringIO()
        DiagnoseCommand(stdout=stdout).handle(root_pipeline_id="", node_id="", process_id=process.id)
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload[0]["type"], "schedule_lock_stuck")
        self.assertEqual(payload[0]["related_objects"]["node_id"], "node-command-process")

    def test_scan_stuck_cases_upserts_stalled_case(self):
        process = self._create_process(202, root_pipeline_id="root-scan", node_id="node-scan")
        self._create_state("node-scan", root_pipeline_id="root-scan")
        self._create_schedule(202, process.id, "node-scan")
        Process.objects.filter(id=process.id).update(
            last_heartbeat=timezone.now() - timedelta(seconds=3600)
        )

        stdout = StringIO()
        ScanCommand(stdout=stdout).handle(threshold=1800, batch=100, confirm=0)

        self.assertEqual(DiagnosticCase.objects.count(), 1)
        case = DiagnosticCase.objects.get()
        self.assertEqual(case.root_pipeline_id, "root-scan")
        self.assertEqual(case.node_id, "node-scan")
        self.assertEqual(case.stuck_type, "schedule_lock_stuck")
        self.assertIn("upserted cases: 1", stdout.getvalue())

    @override_settings(PIPELINE_DIAGNOSTICS_SCAN_ENABLED=False)
    def test_scan_stuck_cases_disabled_does_not_upsert(self):
        process = self._create_process(203, root_pipeline_id="root-scan-disabled", node_id="node-scan-disabled")
        self._create_state("node-scan-disabled", root_pipeline_id="root-scan-disabled")
        self._create_schedule(203, process.id, "node-scan-disabled")
        Process.objects.filter(id=process.id).update(
            last_heartbeat=timezone.now() - timedelta(seconds=3600)
        )

        stdout = StringIO()
        ScanCommand(stdout=stdout).handle(threshold=1800, batch=100, confirm=0)

        self.assertEqual(DiagnosticCase.objects.count(), 0)
        self.assertIn("upserted cases: 0", stdout.getvalue())

    def test_scan_stuck_cases_batch_zero_does_not_upsert(self):
        process = self._create_process(204, root_pipeline_id="root-scan-zero", node_id="node-scan-zero")
        self._create_state("node-scan-zero", root_pipeline_id="root-scan-zero")
        self._create_schedule(204, process.id, "node-scan-zero")
        Process.objects.filter(id=process.id).update(
            last_heartbeat=timezone.now() - timedelta(seconds=3600)
        )

        stdout = StringIO()
        ScanCommand(stdout=stdout).handle(threshold=1800, batch=0, confirm=0)

        self.assertEqual(DiagnosticCase.objects.count(), 0)
        self.assertIn("upserted cases: 0", stdout.getvalue())
