# -*- coding: utf-8 -*-

import mock
from django.test import override_settings

from pipeline.contrib.diagnostics.models import DiagnosticEvent
from pipeline.contrib.diagnostics.events import emit_event
from tests.contrib.diagnostics.base import DiagnosticsTestCase


class DiagnosticsEventTestCase(DiagnosticsTestCase):
    def test_emit_event_when_enabled(self):
        event = emit_event(
            event_type="stuck",
            root_pipeline_id="root-pipeline-1",
            node_id="node-1",
            version="v1",
            result="failed",
            reason="node schedule timeout",
            payload={"source": "doctor"},
            process_id=1,
            schedule_id=2,
            callback_data_id=3,
            duration=12.5,
            engine_version="3.24.10",
        )

        loaded = DiagnosticEvent.objects.get(id=event.id)

        self.assertEqual(loaded.event_type, "stuck")
        self.assertEqual(loaded.root_pipeline_id, "root-pipeline-1")
        self.assertEqual(loaded.node_id, "node-1")
        self.assertEqual(loaded.version, "v1")
        self.assertEqual(loaded.result, "failed")
        self.assertEqual(loaded.reason, "node schedule timeout")
        self.assertEqual(loaded.payload, {"source": "doctor"})
        self.assertEqual(loaded.process_id, 1)
        self.assertEqual(loaded.schedule_id, 2)
        self.assertEqual(loaded.callback_data_id, 3)
        self.assertEqual(loaded.duration, 12.5)
        self.assertEqual(loaded.engine_version, "3.24.10")

    @override_settings(PIPELINE_DIAGNOSTICS_EVENT_ENABLED=False)
    def test_emit_event_when_disabled(self):
        event = emit_event(event_type="stuck", root_pipeline_id="root-pipeline-1")

        self.assertIsNone(event)
        self.assertEqual(DiagnosticEvent.objects.count(), 0)

    def test_emit_event_swallow_write_exception(self):
        with mock.patch("pipeline.contrib.diagnostics.events.DiagnosticEvent.objects.create") as create:
            create.side_effect = Exception("db unavailable")
            with mock.patch("pipeline.contrib.diagnostics.events.logger") as logger:
                event = emit_event(event_type="stuck", root_pipeline_id="root-pipeline-1")

        self.assertIsNone(event)
        logger.exception.assert_called_once()

    def test_emit_event_uses_empty_payload_by_default(self):
        event = emit_event(event_type="stuck", root_pipeline_id="root-pipeline-1")

        loaded = DiagnosticEvent.objects.get(id=event.id)

        self.assertEqual(loaded.payload, {})

    def test_emit_event_preserves_falsy_payload(self):
        event = emit_event(event_type="stuck", root_pipeline_id="root-pipeline-1", payload=[])

        loaded = DiagnosticEvent.objects.get(id=event.id)

        self.assertEqual(loaded.payload, [])
