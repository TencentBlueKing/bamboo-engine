# -*- coding: utf-8 -*-

import os

from django.test import RequestFactory, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticOperationAudit
from pipeline.contrib.diagnostics.views import case_detail, case_list, update_case_status
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase


urlpatterns = [
    path("", include("pipeline.contrib.diagnostics.urls", namespace="pipeline_diagnostics")),
]


class UserStub(object):
    def __init__(self, is_superuser=True):
        self.is_authenticated = True
        self.is_superuser = is_superuser


DIAGNOSTICS_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "runtime",
    "bamboo-pipeline",
    "pipeline",
    "contrib",
    "diagnostics",
    "templates",
)

TEST_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [DIAGNOSTICS_TEMPLATE_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
            ]
        },
    }
]


@override_settings(ROOT_URLCONF=__name__, TEMPLATES=TEST_TEMPLATES)
class DiagnosticViewsTestCase(DiagnosticsTestCase):
    def setUp(self):
        super(DiagnosticViewsTestCase, self).setUp()
        self.factory = RequestFactory()

    def _case(self, **kwargs):
        defaults = {
            "root_pipeline_id": "root-view",
            "node_id": "node-view",
            "stuck_type": "callback_lock_conflict",
            "severity": DiagnosticCase.SEVERITY_CRITICAL,
            "confidence": 0.99,
            "status": DiagnosticCase.STATUS_OPEN,
            "first_seen_at": timezone.now(),
            "last_seen_at": timezone.now(),
            "hit_count": 1,
            "evidence": {"callback_data_count": 2},
            "related_objects": {"node_id": "node-view"},
            "recommended_actions": ["replay_callback_data"],
            "forbidden_actions": ["force_wake_parent_process"],
            "message": "callback conflict",
        }
        defaults.update(kwargs)
        return DiagnosticCase.objects.create(**defaults)

    def _request(self, method, path, data=None, is_superuser=True):
        request = getattr(self.factory, method)(path, data=data or {})
        request.user = UserStub(is_superuser=is_superuser)
        return request

    def test_case_list_renders_and_filters(self):
        self._case()
        self._case(root_pipeline_id="root-other", node_id="node-other", stuck_type="schedule_lock_stuck")
        request = self._request("get", reverse("pipeline_diagnostics:case_list"), {"root_pipeline_id": "root-view"})

        response = case_list(request)
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("callback_lock_conflict", content)
        self.assertNotIn("schedule_lock_stuck", content)

    def test_case_detail_renders_audit(self):
        diagnostic_case = self._case()
        DiagnosticOperationAudit.objects.create(
            case=diagnostic_case,
            operation_type=DiagnosticOperationAudit.OPERATION_TYPE_INSPECT_NODE_RUNTIME_READINESS,
            target_object={"node_id": diagnostic_case.node_id},
            operator="admin",
            mode=DiagnosticOperationAudit.MODE_DRY_RUN,
            precheck_result={"result": True},
            result={"result": True},
            risk_level=DiagnosticOperationAudit.RISK_LEVEL_LOW,
        )
        request = self._request("get", reverse("pipeline_diagnostics:case_detail", args=[diagnostic_case.id]))

        response = case_detail(request, case_id=diagnostic_case.id)
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("callback conflict", content)
        self.assertIn("inspect_node_runtime_readiness", content)

    def test_update_case_status(self):
        diagnostic_case = self._case()
        request = self._request(
            "post",
            reverse("pipeline_diagnostics:update_case_status", args=[diagnostic_case.id]),
            {"status": DiagnosticCase.STATUS_RESOLVED},
        )

        response = update_case_status(request, case_id=diagnostic_case.id)
        diagnostic_case.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(diagnostic_case.status, DiagnosticCase.STATUS_RESOLVED)

    def test_superuser_required(self):
        request = self._request("get", reverse("pipeline_diagnostics:case_list"), is_superuser=False)

        response = case_list(request)

        self.assertEqual(response.status_code, 403)
