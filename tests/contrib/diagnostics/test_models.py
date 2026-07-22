# -*- coding: utf-8 -*-

from django.utils import timezone

from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticEvent, DiagnosticOperationAudit
from tests.contrib.diagnostics.base import DiagnosticsTestCase


class DiagnosticsModelTestCase(DiagnosticsTestCase):
    def test_create_diagnostic_event(self):
        event = DiagnosticEvent.objects.create(
            event_type="stuck",
            root_pipeline_id="root-pipeline-1",
            node_id="node-1",
            process_id=1,
            version="v1",
            schedule_id=1,
            callback_data_id=2,
            result="failed",
            reason="node schedule timeout",
            duration=120.5,
            engine_version="3.24.10",
            payload={"doctor": "zombie"},
        )

        loaded = DiagnosticEvent.objects.get(id=event.id)

        self.assertEqual(loaded.event_type, "stuck")
        self.assertEqual(loaded.root_pipeline_id, "root-pipeline-1")
        self.assertEqual(loaded.node_id, "node-1")
        self.assertEqual(loaded.process_id, 1)
        self.assertEqual(loaded.version, "v1")
        self.assertEqual(loaded.schedule_id, 1)
        self.assertEqual(loaded.callback_data_id, 2)
        self.assertEqual(loaded.result, "failed")
        self.assertEqual(loaded.reason, "node schedule timeout")
        self.assertEqual(loaded.duration, 120.5)
        self.assertEqual(loaded.engine_version, "3.24.10")
        self.assertEqual(loaded.payload, {"doctor": "zombie"})
        self.assertEqual(DiagnosticEvent._meta.get_field("process_id").get_internal_type(), "BigIntegerField")
        self.assertEqual(DiagnosticEvent._meta.get_field("schedule_id").get_internal_type(), "BigIntegerField")
        self.assertEqual(DiagnosticEvent._meta.get_field("callback_data_id").get_internal_type(), "BigIntegerField")
        self.assertEqual(DiagnosticEvent._meta.pk.get_internal_type(), "BigAutoField")

    def test_create_diagnostic_case(self):
        first_seen_at = timezone.now()
        case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-2",
            node_id="node-2",
            stuck_type="schedule_timeout",
            status=DiagnosticCase.STATUS_OPEN,
            severity=DiagnosticCase.SEVERITY_WARNING,
            confidence=0.95,
            first_seen_at=first_seen_at,
            last_seen_at=first_seen_at,
            hit_count=2,
            evidence={"schedule_id": 11},
            related_objects={"process_id": 22},
            recommended_actions=["retry"],
            forbidden_actions=["resume"],
            message="schedule timeout detected",
        )

        loaded = DiagnosticCase.objects.get(id=case.id)

        self.assertEqual(loaded.root_pipeline_id, "root-pipeline-2")
        self.assertEqual(loaded.node_id, "node-2")
        self.assertEqual(loaded.stuck_type, "schedule_timeout")
        self.assertEqual(loaded.status, DiagnosticCase.STATUS_OPEN)
        self.assertEqual(loaded.severity, DiagnosticCase.SEVERITY_WARNING)
        self.assertEqual(loaded.confidence, 0.95)
        self.assertEqual(loaded.hit_count, 2)
        self.assertEqual(loaded.evidence, {"schedule_id": 11})
        self.assertEqual(loaded.related_objects, {"process_id": 22})
        self.assertEqual(loaded.recommended_actions, ["retry"])
        self.assertEqual(loaded.forbidden_actions, ["resume"])
        self.assertEqual(loaded.message, "schedule timeout detected")
        self.assertEqual(
            [DiagnosticCase.STATUS_OPEN, DiagnosticCase.STATUS_RESOLVED, DiagnosticCase.STATUS_IGNORED],
            ["open", "resolved", "ignored"],
        )
        self.assertEqual(DiagnosticCase._meta.pk.get_internal_type(), "BigAutoField")
        self.assertIn(
            ("root_pipeline_id", "node_id", "stuck_type", "status"),
            DiagnosticCase._meta.unique_together,
        )

    def test_create_diagnostic_operation_audit(self):
        first_seen_at = timezone.now()
        case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-3",
            node_id="node-3",
            stuck_type="callback_lost",
            status=DiagnosticCase.STATUS_RESOLVED,
            severity=DiagnosticCase.SEVERITY_CRITICAL,
            confidence=0.8,
            first_seen_at=first_seen_at,
            last_seen_at=first_seen_at,
        )
        audit = DiagnosticOperationAudit.objects.create(
            case=case,
            operation_type=DiagnosticOperationAudit.OPERATION_TYPE_REPLAY_CALLBACK_DATA,
            target_object={"process_id": 3},
            operator="admin",
            mode=DiagnosticOperationAudit.MODE_APPLY,
            precheck_result={"passed": True},
            result={"ok": True},
            risk_level=DiagnosticOperationAudit.RISK_LEVEL_HIGH,
            payload={"ticket": "bk-1"},
        )

        loaded = DiagnosticOperationAudit.objects.get(id=audit.id)

        self.assertEqual(loaded.case_id, case.id)
        self.assertEqual(loaded.operation_type, DiagnosticOperationAudit.OPERATION_TYPE_REPLAY_CALLBACK_DATA)
        self.assertEqual(loaded.target_object, {"process_id": 3})
        self.assertEqual(loaded.operator, "admin")
        self.assertEqual(loaded.mode, DiagnosticOperationAudit.MODE_APPLY)
        self.assertEqual(loaded.precheck_result, {"passed": True})
        self.assertEqual(loaded.result, {"ok": True})
        self.assertEqual(loaded.risk_level, DiagnosticOperationAudit.RISK_LEVEL_HIGH)
        self.assertEqual(loaded.payload, {"ticket": "bk-1"})
        self.assertEqual(DiagnosticOperationAudit._meta.pk.get_internal_type(), "BigAutoField")
        self.assertEqual(
            [DiagnosticOperationAudit.MODE_DRY_RUN, DiagnosticOperationAudit.MODE_APPLY],
            ["dry_run", "apply"],
        )
        self.assertEqual(
            [
                DiagnosticOperationAudit.OPERATION_TYPE_REPLAY_CALLBACK_DATA,
                DiagnosticOperationAudit.OPERATION_TYPE_RESEND_SCHEDULE,
                DiagnosticOperationAudit.OPERATION_TYPE_EXPIRE_STALE_SCHEDULE,
                DiagnosticOperationAudit.OPERATION_TYPE_INSPECT_ACK_CONVERGE,
                DiagnosticOperationAudit.OPERATION_TYPE_INSPECT_NODE_RUNTIME_READINESS,
                DiagnosticOperationAudit.OPERATION_TYPE_IGNORE,
            ],
            [
                "replay_callback_data",
                "resend_schedule",
                "expire_stale_schedule",
                "inspect_ack_converge",
                "inspect_node_runtime_readiness",
                "ignore",
            ],
        )

    def test_create_diagnostic_operation_audit_with_custom_operation_type(self):
        first_seen_at = timezone.now()
        case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-4",
            node_id="node-4",
            stuck_type="unknown",
            status=DiagnosticCase.STATUS_IGNORED,
            first_seen_at=first_seen_at,
            last_seen_at=first_seen_at,
        )
        audit = DiagnosticOperationAudit(
            case=case,
            operation_type="custom_operation_type",
            target_object={"node_id": "node-4"},
            operator="admin",
            mode=DiagnosticOperationAudit.MODE_DRY_RUN,
            precheck_result={"passed": True},
            result={"ok": True},
            payload={"reason": "manual inspection"},
        )

        audit.full_clean(exclude=["target_object", "precheck_result", "result", "payload"])
        audit.save()

        loaded = DiagnosticOperationAudit.objects.get(id=audit.id)

        self.assertEqual(loaded.operation_type, "custom_operation_type")
