# -*- coding: utf-8 -*-
"""Recovered renderer failures must retain their category without replaying a plugin."""
import json

import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.eri import Data, ExecutionData, ScheduleType
from bamboo_engine.eri.models.interrupt import (
    ExecuteInterruptPoint,
    HandlerExecuteData,
    HandlerScheduleData,
    ScheduleInterruptPoint,
)
from bamboo_engine.handlers.service_activity import ServiceActivityHandler
from tests.handlers import test_service_activity as service_fixtures

pi = service_fixtures.pi
node = service_fixtures.node
interrupter = service_fixtures.interrupter
schedule = service_fixtures.schedule
schedule_interrupter = service_fixtures.schedule_interrupter


@pytest.mark.parametrize("phase", ["execute", ScheduleType.POLL, ScheduleType.CALLBACK, ScheduleType.MULTIPLE_CALLBACK])
@pytest.mark.parametrize("infrastructure_failed", [True, False])
def test_recovered_render_failure_is_not_auto_ignored(
    phase, infrastructure_failed, pi, node, interrupter, schedule, schedule_interrupter
):
    node.error_ignorable = True
    runtime = MagicMock()
    runtime.get_data.return_value = Data({}, {})
    runtime.get_data_inputs.return_value = {}
    runtime.get_data_outputs.return_value = {}
    runtime.get_context_values.return_value = []
    runtime.get_context_key_references.return_value = set()
    runtime.get_execution_data.return_value = ExecutionData(inputs={}, outputs={})
    runtime.deserialize_execution_data.return_value = {
        "ex_data": "isolated render failed (worker_failure)" if infrastructure_failed else "ordinary business failure"
    }
    runtime.serialize_execution_data.return_value = ("{}", "json")
    if phase == "execute":
        point_type = ExecuteInterruptPoint
        point = point_type(
            "service_done", handler_data=HandlerExecuteData(service_executed=True, service_execute_fail=True)
        )
    else:
        point_type = ScheduleInterruptPoint
        point = point_type(
            "service_done", handler_data=HandlerScheduleData(service_scheduled=True, service_schedule_fail=True)
        )
        schedule.type = phase
        runtime.get_service.return_value.schedule_type.return_value = phase
        interrupter = schedule_interrupter
    payload = json.loads(point.to_json())
    if infrastructure_failed:
        payload["handler_data"]["render_infrastructure_failed"] = True
    else:
        # Old checkpoints have no field; their ordinary ignorable errors must keep working.
        payload["handler_data"].pop("render_infrastructure_failed", None)
    recovered = point_type.from_json(json.dumps(payload))
    handler = ServiceActivityHandler(node, runtime, interrupter)
    if phase == "execute":
        result = handler.execute(pi, 1, 1, "v1", recovered)
    else:
        result = handler.schedule(pi, 1, 1, schedule, recover_point=recovered)

    expected_state = states.FAILED if infrastructure_failed else states.FINISHED
    assert runtime.set_state.call_args.kwargs["to_state"] == expected_state
    runtime.get_service.return_value.execute.assert_not_called()
    runtime.get_service.return_value.schedule.assert_not_called()
    assert runtime.set_execution_data.call_args.kwargs["data"].outputs._result is False
    if infrastructure_failed:
        assert result.next_node_id is None
        if phase != "execute":
            assert result.has_next_schedule is False
            assert result.schedule_done is False
        runtime.upsert_plain_context_values.assert_not_called()
