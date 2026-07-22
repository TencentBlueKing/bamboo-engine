# -*- coding: utf-8 -*-

from django.test import override_settings

from pipeline.contrib.diagnostics.cases import upsert_case
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.types import DiagnosticHit
from tests.contrib.diagnostics.base import DiagnosticsTestCase


class DiagnosticCaseUpsertTestCase(DiagnosticsTestCase):
    def _hit(self, stuck_type="schedule_lock_stuck", message="schedule lock"):
        return DiagnosticHit(
            type=stuck_type,
            severity="critical",
            confidence=0.95,
            evidence={"node_id": "node-case", "schedule_id": 1},
            related_objects={"node_id": "node-case", "schedule_id": 1},
            recommended_actions=["inspect_schedule_lock"],
            forbidden_actions=["replay_callback_data"],
            message=message,
        )

    def test_upsert_merges_same_open_case(self):
        first = upsert_case("root-case", "node-case", self._hit(message="first"))
        first_seen_at = first.first_seen_at

        second = upsert_case("root-case", "node-case", self._hit(message="second"))
        loaded = DiagnosticCase.objects.get(id=first.id)

        self.assertEqual(second.id, first.id)
        self.assertEqual(loaded.hit_count, 2)
        self.assertEqual(loaded.first_seen_at, first_seen_at)
        self.assertGreaterEqual(loaded.last_seen_at, first_seen_at)
        self.assertEqual(loaded.message, "second")
        self.assertEqual(loaded.evidence, {"node_id": "node-case", "schedule_id": 1})

    def test_upsert_normalizes_empty_root_and_node(self):
        case = upsert_case(None, None, self._hit())

        self.assertEqual(case.root_pipeline_id, "")
        self.assertEqual(case.node_id, "")

    def test_resolved_or_ignored_case_does_not_block_new_open_case(self):
        resolved = upsert_case("root-case", "node-case", self._hit())
        DiagnosticCase.objects.filter(id=resolved.id).update(status=DiagnosticCase.STATUS_RESOLVED)
        ignored = upsert_case("root-case", "node-other", self._hit())
        DiagnosticCase.objects.filter(id=ignored.id).update(status=DiagnosticCase.STATUS_IGNORED)

        open_from_resolved = upsert_case("root-case", "node-case", self._hit(message="new open"))
        open_from_ignored = upsert_case("root-case", "node-other", self._hit(message="new open ignored"))

        self.assertNotEqual(open_from_resolved.id, resolved.id)
        self.assertNotEqual(open_from_ignored.id, ignored.id)
        self.assertEqual(
            DiagnosticCase.objects.filter(root_pipeline_id="root-case", status=DiagnosticCase.STATUS_OPEN).count(),
            2,
        )

    @override_settings(PIPELINE_DIAGNOSTICS_CASE_ENABLED=False)
    def test_upsert_case_disabled_does_not_write_case(self):
        case = upsert_case("root-case", "node-case", self._hit())

        self.assertIsNone(case)
        self.assertEqual(DiagnosticCase.objects.count(), 0)
