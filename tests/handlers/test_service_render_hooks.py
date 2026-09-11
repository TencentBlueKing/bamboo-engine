# -*- coding: utf-8 -*-
"""4.0 hook failures must preserve the renderer failure category."""
import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.eri import Data, ExecutionData, HookType, ScheduleType
from bamboo_engine.exceptions import RenderInfrastructureError
from bamboo_engine.handlers.service_activity import ServiceActivityHandler
from tests.handlers import test_service_activity as service_fixtures

pi = service_fixtures.pi
node = service_fixtures.node
interrupter = service_fixtures.interrupter
schedule = service_fixtures.schedule
schedule_interrupter = service_fixtures.schedule_interrupter


@pytest.mark.parametrize("phase", ["execute", ScheduleType.POLL, ScheduleType.CALLBACK, ScheduleType.MULTIPLE_CALLBACK])
@pytest.mark.parametrize("source", ["runtime", "plugin_hook"])
@pytest.mark.parametrize("infrastructure_failed", [True, False])
def test_post_hook_render_failure_does_not_reuse_successful_service_result(
    phase, source, infrastructure_failed, pi, node, interrupter, schedule, schedule_interrupter
):
    node.error_ignorable = True
    runtime = MagicMock()
    runtime.get_data.return_value = Data({}, {})
    runtime.get_data_inputs.return_value = {}
    runtime.get_data_outputs.return_value = {}
    runtime.get_context_values.return_value = []
    runtime.get_context_key_references.return_value = set()
    runtime.get_execution_data.return_value = ExecutionData(inputs={}, outputs={})
    runtime.serialize_execution_data.return_value = ("{}", "json")
    service = runtime.get_service.return_value
    service.execute.return_value = True
    service.schedule.return_value = True
    service.need_schedule.return_value = False
    service.is_schedule_done.return_value = True
    service.need_run_hook.return_value = source == "plugin_hook"
    post_hook = HookType.POST_EXECUTE if phase == "execute" else HookType.POST_SCHEDULE
    error = RenderInfrastructureError("worker_failure") if infrastructure_failed else ValueError("business hook error")

    if source == "runtime":
        getattr(runtime, "post_execute" if phase == "execute" else "post_schedule").side_effect = error
    else:

        def dispatch(hook, **kwargs):
            if hook == post_hook:
                raise error
            return False

        service.hook_dispatch.side_effect = dispatch

    if phase == "execute":
        handler = ServiceActivityHandler(node, runtime, interrupter)
        result = handler.execute(pi, 1, 1, "v1")
    else:
        schedule.type = phase
        service.schedule_type.return_value = phase
        handler = ServiceActivityHandler(node, runtime, schedule_interrupter)
        result = handler.schedule(pi, 1, 1, schedule)

    outputs = runtime.set_execution_data.call_args.kwargs["data"].outputs
    assert outputs._result is (not infrastructure_failed)
    if infrastructure_failed:
        assert runtime.set_state.call_args.kwargs["to_state"] == states.FAILED
        assert result.next_node_id is None
        runtime.upsert_plain_context_values.assert_not_called()
        if phase != "execute":
            assert result.has_next_schedule is False
            assert result.schedule_done is False
    else:
        assert not any(call.kwargs.get("to_state") == states.FAILED for call in runtime.set_state.call_args_list)
