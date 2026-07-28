# -*- coding: utf-8 -*-

import mock
from django.test import SimpleTestCase
from django.test import override_settings
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine import engine as engine_module
from bamboo_engine.engine import Engine
from bamboo_engine.eri import ProcessInfo, Schedule, ScheduleType, State
from bamboo_engine.eri.models.interrupt import ScheduleInterruptPoint
from bamboo_engine.interrupt import ScheduleInterrupter
from pipeline.eri.celery import tasks as celery_tasks


def _state(node_id="node-1", version="v1"):
    return State(
        node_id=node_id,
        root_id="root-1",
        parent_id="root-1",
        name=states.RUNNING,
        version=version,
        loop=1,
        inner_loop=1,
        retry=0,
        skip=False,
        error_ignored=False,
        created_time=None,
        started_time=None,
        archived_time=None,
    )


def _process_info():
    return ProcessInfo(
        process_id=101,
        destination_id="",
        root_pipeline_id="root-1",
        pipeline_stack=["root-1"],
        parent_id="root-1",
    )


def _schedule(schedule_type=ScheduleType.MULTIPLE_CALLBACK):
    return Schedule(
        id=202,
        type=schedule_type,
        process_id=101,
        node_id="node-1",
        finished=False,
        expired=False,
        version="v1",
        times=0,
    )


def _interrupter(headers=None):
    return ScheduleInterrupter(
        runtime=MagicMock(),
        process_id=101,
        current_node_id="node-1",
        schedule_id=202,
        callback_data_id=303,
        check_point=ScheduleInterruptPoint(name="entry"),
        recover_point=None,
        headers=headers or {},
    )


class DiagnosticEventIntegrationTestCase(SimpleTestCase):
    @override_settings(PIPELINE_DIAGNOSTICS_ALERT_ENABLED=True)
    def test_emit_alert_log_writes_structured_warning(self):
        from pipeline.contrib.diagnostics.metrics import emit_alert_log

        with mock.patch("pipeline.contrib.diagnostics.metrics.logger") as logger:
            emit_alert_log(
                alert_type="schedule_lock_conflict",
                root_pipeline_id="root-1",
                node_id="node-1",
                payload={"schedule_id": 202},
            )

        logger.warning.assert_called_once()
        args = logger.warning.call_args[0]
        self.assertIn("[pipeline_diagnostics_alert]", args[0])
        self.assertIn("schedule_lock_conflict", args)
        self.assertIn("root-1", args)
        self.assertIn("node-1", args)

    @override_settings(PIPELINE_DIAGNOSTICS_ALERT_ENABLED=False)
    def test_emit_alert_log_respects_switch(self):
        from pipeline.contrib.diagnostics.metrics import emit_alert_log

        with mock.patch("pipeline.contrib.diagnostics.metrics.logger") as logger:
            emit_alert_log(alert_type="schedule_lock_conflict", root_pipeline_id="root-1", node_id="node-1")

        logger.warning.assert_not_called()

    def test_celery_schedule_emits_received_event_before_engine_schedule(self):
        with mock.patch("pipeline.eri.celery.tasks.emit_event") as emit_event:
            with mock.patch("pipeline.eri.celery.tasks.Engine") as engine:
                celery_tasks.schedule.run(
                    process_id=101,
                    node_id="node-1",
                    schedule_id=202,
                    callback_data_id=303,
                    headers={"timestamp": 1, "route_info": {"queue": "default"}},
                )

        emit_event.assert_called_once_with(
            event_type="schedule_received",
            root_pipeline_id="",
            node_id="node-1",
            result="received",
            process_id=101,
            schedule_id=202,
            callback_data_id=303,
            payload={"headers": {"timestamp": 1, "route_info": {"queue": "default"}}},
        )
        engine.return_value.schedule.assert_called_once()

    def test_engine_schedule_lock_conflict_emits_diagnostic_event(self):
        runtime = MagicMock()
        runtime.get_process_info = MagicMock(return_value=_process_info())
        runtime.apply_schedule_lock = MagicMock(return_value=False)
        runtime.get_state = MagicMock(return_value=_state())
        runtime.get_schedule = MagicMock(return_value=_schedule())

        with mock.patch("bamboo_engine.engine.random.randint", return_value=5):
            with mock.patch("bamboo_engine.engine.emit_diagnostic_event") as emit_event:
                Engine(runtime=runtime).schedule(
                    process_id=101,
                    node_id="node-1",
                    schedule_id=202,
                    interrupter=_interrupter(),
                    callback_data_id=303,
                    headers={"route_info": {"queue": "default"}},
                )

        emit_event.assert_called_once_with(
            event_type="schedule_lock_conflict",
            root_pipeline_id="root-1",
            node_id="node-1",
            version="v1",
            result="failed",
            reason="lock_busy",
            process_id=101,
            schedule_id=202,
            callback_data_id=303,
            payload={
                "schedule_type": "MULTIPLE_CALLBACK",
                "headers": {"route_info": {"queue": "default"}},
            },
        )

    def test_engine_diagnostic_helpers_swallow_exception(self):
        with mock.patch("pipeline.contrib.diagnostics.events.emit_event", side_effect=Exception("db down")):
            self.assertIsNone(engine_module.emit_diagnostic_event(event_type="stuck", root_pipeline_id="root-1"))

        with mock.patch("pipeline.contrib.diagnostics.metrics.emit_alert_log", side_effect=Exception("log down")):
            self.assertIsNone(engine_module.emit_diagnostic_alert(alert_type="stuck", root_pipeline_id="root-1"))
