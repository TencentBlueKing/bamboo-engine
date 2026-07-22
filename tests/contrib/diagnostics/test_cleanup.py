# -*- coding: utf-8 -*-

import datetime
from io import StringIO

from django.utils import timezone

from pipeline.contrib.diagnostics.management.commands.cleanup_diagnostics import Command
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticEvent, DiagnosticOperationAudit
from tests.contrib.diagnostics.base import DiagnosticsTestCase


class DiagnosticsCleanupTestCase(DiagnosticsTestCase):
    def test_cleanup_expired_diagnostics(self):
        now = timezone.now()
        old_event = DiagnosticEvent.objects.create(event_type="stuck", root_pipeline_id="root-pipeline-1")
        recent_event = DiagnosticEvent.objects.create(event_type="stuck", root_pipeline_id="root-pipeline-2")
        old_open_case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-3",
            node_id="node-3",
            stuck_type="schedule_timeout",
            status=DiagnosticCase.STATUS_OPEN,
        )
        old_resolved_case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-4",
            node_id="node-4",
            stuck_type="schedule_timeout",
            status=DiagnosticCase.STATUS_RESOLVED,
        )
        recent_audit_on_old_resolved_case = DiagnosticOperationAudit.objects.create(
            case=old_resolved_case,
            operation_type="custom",
            operator="admin",
            mode=DiagnosticOperationAudit.MODE_APPLY,
        )
        recent_ignored_case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-5",
            node_id="node-5",
            stuck_type="schedule_timeout",
            status=DiagnosticCase.STATUS_IGNORED,
        )
        old_audit_case = DiagnosticCase.objects.create(
            root_pipeline_id="root-pipeline-6",
            node_id="node-6",
            stuck_type="schedule_timeout",
            status=DiagnosticCase.STATUS_RESOLVED,
        )
        old_audit = DiagnosticOperationAudit.objects.create(
            case=old_audit_case,
            operation_type="custom",
            operator="admin",
            mode=DiagnosticOperationAudit.MODE_DRY_RUN,
        )
        recent_audit = DiagnosticOperationAudit.objects.create(
            case=old_audit_case,
            operation_type="custom",
            operator="admin",
            mode=DiagnosticOperationAudit.MODE_APPLY,
        )

        DiagnosticEvent.objects.filter(id=old_event.id).update(created_at=now - datetime.timedelta(days=31))
        DiagnosticEvent.objects.filter(id=recent_event.id).update(created_at=now - datetime.timedelta(days=1))
        DiagnosticCase.objects.filter(id=old_open_case.id).update(updated_at=now - datetime.timedelta(days=366))
        DiagnosticCase.objects.filter(id=old_resolved_case.id).update(updated_at=now - datetime.timedelta(days=366))
        DiagnosticCase.objects.filter(id=recent_ignored_case.id).update(updated_at=now - datetime.timedelta(days=1))
        DiagnosticOperationAudit.objects.filter(id=old_audit.id).update(
            created_at=now - datetime.timedelta(days=366)
        )
        DiagnosticOperationAudit.objects.filter(id=recent_audit.id).update(
            created_at=now - datetime.timedelta(days=1)
        )

        stdout = StringIO()
        Command(stdout=stdout).handle()

        self.assertFalse(DiagnosticEvent.objects.filter(id=old_event.id).exists())
        self.assertTrue(DiagnosticEvent.objects.filter(id=recent_event.id).exists())
        self.assertTrue(DiagnosticCase.objects.filter(id=old_open_case.id).exists())
        self.assertFalse(DiagnosticCase.objects.filter(id=old_resolved_case.id).exists())
        self.assertTrue(DiagnosticCase.objects.filter(id=recent_ignored_case.id).exists())
        self.assertTrue(DiagnosticOperationAudit.objects.filter(id=recent_audit_on_old_resolved_case.id).exists())
        self.assertIsNone(DiagnosticOperationAudit.objects.get(id=recent_audit_on_old_resolved_case.id).case_id)
        self.assertFalse(DiagnosticOperationAudit.objects.filter(id=old_audit.id).exists())
        self.assertTrue(DiagnosticOperationAudit.objects.filter(id=recent_audit.id).exists())
        self.assertIn("DiagnosticEvent deleted: 1", stdout.getvalue())
        self.assertIn("DiagnosticCase deleted: 1", stdout.getvalue())
        self.assertIn("DiagnosticOperationAudit deleted: 1", stdout.getvalue())
