# -*- coding: utf-8 -*-

import inspect
import re
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from pipeline.contrib.diagnostics import cases, rules
from pipeline.contrib.diagnostics.case_types import ROOT_RULE_CASE_TYPES
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.eri.models import Process
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import make_state


class CloseStaleCasesTest(DiagnosticsTestCase):
    def setUp(self):
        super(CloseStaleCasesTest, self).setUp()
        self.process_ids = []

    def tearDown(self):
        Process.objects.filter(id__in=self.process_ids).delete()
        super(CloseStaleCasesTest, self).tearDown()

    def _proc(self, root, beat_delta):
        p = Process.objects.create(
            root_pipeline_id=root,
            current_node_id="n1",
            destination_id="",
            priority=1,
            queue="diagnostics",
            pipeline_stack="[]",
        )
        self.process_ids.append(p.id)
        Process.objects.filter(id=p.id).update(last_heartbeat=timezone.now() - timedelta(seconds=beat_delta))
        return p

    def _open_case(self, root):
        return DiagnosticCase.objects.create(
            root_pipeline_id=root,
            node_id="n1",
            stuck_type="stalled_no_progress",
            status=DiagnosticCase.STATUS_OPEN,
        )

    def test_resolve_when_root_recovered(self):
        self._proc("root-recovered", beat_delta=5)
        self._open_case("root-recovered")
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 1)
        self.assertEqual(
            DiagnosticCase.objects.get(root_pipeline_id="root-recovered").status,
            DiagnosticCase.STATUS_RESOLVED,
        )

    def test_resolve_when_root_has_no_live_process(self):
        self._open_case("root-finished")
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 1)
        self.assertEqual(
            DiagnosticCase.objects.get(root_pipeline_id="root-finished").status,
            DiagnosticCase.STATUS_RESOLVED,
        )

    def test_keep_when_root_still_stalled(self):
        self._proc("root-stuck", beat_delta=3600)
        self._open_case("root-stuck")
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 0)
        self.assertEqual(
            DiagnosticCase.objects.get(root_pipeline_id="root-stuck").status,
            DiagnosticCase.STATUS_OPEN,
        )

    def test_external_case_types_are_left_to_their_owner(self):
        DiagnosticCase.objects.create(
            root_pipeline_id="root-ext",
            node_id="n1",
            stuck_type="running_task_without_live_process",
            status=DiagnosticCase.STATUS_OPEN,
        )
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 0)
        self.assertEqual(
            DiagnosticCase.objects.get(root_pipeline_id="root-ext").status,
            DiagnosticCase.STATUS_OPEN,
        )

    def test_resolve_when_root_revoked_or_finished_with_live_process(self):
        for root, name in (("root-revoked", "REVOKED"), ("root-done", "FINISHED")):
            self._proc(root, beat_delta=3600)
            make_state(root, name=name, version="rv", root=root)
            self._open_case(root)
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 2)
        self.assertEqual(
            set(DiagnosticCase.objects.values_list("status", flat=True)),
            {DiagnosticCase.STATUS_RESOLVED},
        )

    def test_already_resolved_not_recounted(self):
        DiagnosticCase.objects.create(
            root_pipeline_id="root-x",
            node_id="n1",
            stuck_type="x",
            status=DiagnosticCase.STATUS_RESOLVED,
        )
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 0)

    def test_reclose_after_recurrence_does_not_raise(self):
        # 1) 首次停滞并立案
        self._proc("root-recur", beat_delta=3600)
        self._open_case("root-recur")
        # 2) 恢复 -> resolve
        Process.objects.filter(root_pipeline_id="root-recur").update(last_heartbeat=timezone.now())
        self.assertEqual(cases.close_stale_cases(threshold_seconds=1800), 1)
        # 3) 同 root/node/type 再次停滞 -> 新 open 行
        Process.objects.filter(root_pipeline_id="root-recur").update(
            last_heartbeat=timezone.now() - timedelta(seconds=3600)
        )
        self._open_case("root-recur")
        # 4) 再次恢复 -> 必须能关闭且不抛 IntegrityError
        Process.objects.filter(root_pipeline_id="root-recur").update(last_heartbeat=timezone.now())
        closed = cases.close_stale_cases(threshold_seconds=1800)
        self.assertEqual(closed, 1)
        self.assertEqual(
            DiagnosticCase.objects.filter(root_pipeline_id="root-recur", status=DiagnosticCase.STATUS_RESOLVED).count(),
            1,
        )
        self.assertEqual(
            DiagnosticCase.objects.filter(root_pipeline_id="root-recur", status=DiagnosticCase.STATUS_OPEN).count(),
            0,
        )


class RootRuleCaseTypesTest(SimpleTestCase):
    def test_matches_rule_hit_types(self):
        # 规则新增类型却没登记时，它的案例永远不会被按 root 关闭
        found = set(re.findall(r'_hit\(\s*"(\w+)"', inspect.getsource(rules)))
        self.assertEqual(found, set(ROOT_RULE_CASE_TYPES))
