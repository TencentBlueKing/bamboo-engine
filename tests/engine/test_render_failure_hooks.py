# -*- coding: utf-8 -*-
"""Renderer failures in 4.0 lifecycle hooks must survive engine recovery."""
import copy
import json
from types import SimpleNamespace

import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.engine import Engine
from bamboo_engine.eri import Data, ExecutionData, HookType, ScheduleType
from bamboo_engine.handlers.service_activity import ServiceActivityHandler  # noqa
from bamboo_engine.template import Template, template
from bamboo_engine.template.render_backend import SubprocessPoolRenderBackend
from tests.engine import test_engine_schedule as fixtures
from tests.handlers import test_service_activity as handler_fixtures


class RetryWriteError(Exception):
    pass


@pytest.fixture(params=["execute", ScheduleType.POLL, ScheduleType.CALLBACK, ScheduleType.MULTIPLE_CALLBACK])
def case(request):
    phase = request.param
    node = fixtures.node.__wrapped__()
    node.error_ignorable = True
    pi = fixtures.pi.__wrapped__()
    pi.destination_id = node.target_nodes[0]
    schedule = fixtures.schedule.__wrapped__(1, "v")
    schedule.type = phase if phase != "execute" else ScheduleType.POLL
    state = fixtures.state.__wrapped__("v")
    state.node_id = node.id
    state.name = states.READY if phase == "execute" else states.RUNNING
    runtime = MagicMock()
    stored = ExecutionData(inputs={}, outputs={})
    runtime.get_process_info.return_value = pi
    runtime.get_state.return_value = state
    runtime.get_state_or_none.side_effect = lambda *args: None if state.name == states.READY else copy.copy(state)
    runtime.batch_get_state_name.return_value = {"root": states.RUNNING}
    runtime.get_schedule.return_value = schedule
    runtime.get_node.return_value = node
    runtime.get_data.return_value = Data({}, {})
    runtime.get_data_inputs.return_value = {}
    runtime.get_data_outputs.return_value = {}
    runtime.get_context_values.return_value = []
    runtime.get_context_key_references.return_value = set()
    runtime.get_execution_data.side_effect = lambda *args: copy.deepcopy(stored)
    runtime.get_execution_data_inputs.side_effect = lambda *args: copy.deepcopy(stored.inputs)
    runtime.get_execution_data_outputs.side_effect = lambda *args: copy.deepcopy(stored.outputs)
    runtime.serialize_execution_data.side_effect = lambda value: (json.dumps(value), "json")
    runtime.deserialize_execution_data.side_effect = lambda value, serializer: json.loads(value)
    runtime.interrupt_errors.return_value = (RetryWriteError,)
    runtime.get_config.return_value = True  # rollback snapshots must also be suppressed
    runtime.child_process_finish.return_value = True
    runtime.apply_schedule_lock.return_value = True

    def set_state(node_id, to_state, version=None, **kwargs):
        assert version in (None, state.version)
        state.name = to_state
        return state.version

    def set_data(node_id, data):
        stored.inputs = copy.deepcopy(data.inputs)
        stored.outputs = copy.deepcopy(data.outputs)

    def set_outputs(node_id, outputs):
        stored.outputs = copy.deepcopy(outputs)

    runtime.set_state.side_effect = set_state
    runtime.set_execution_data.side_effect = set_data
    runtime.set_execution_data_outputs.side_effect = set_outputs
    service = runtime.get_service.return_value
    service.execute.return_value = True
    service.schedule.return_value = True
    service.need_schedule.return_value = False
    service.is_schedule_done.return_value = True
    service.schedule_type.return_value = schedule.type
    service.schedule_after.return_value = -1
    service.need_run_hook.return_value = True
    service.hook_dispatch.return_value = False

    def new_interrupter(recover_point=None):
        if phase == "execute":
            inter = handler_fixtures.interrupter.__wrapped__()
        else:
            inter = fixtures.interrupter.__wrapped__(pi, node.id, schedule.id)
        inter.runtime = runtime
        inter.recover_point = recover_point
        return inter

    def run(interrupter):
        engine = Engine(runtime)
        if phase == "execute":
            engine.execute(pi.process_id, node.id, "root", "root", interrupter, {})
        else:
            engine.schedule(pi.process_id, node.id, schedule.id, interrupter, {})

    return SimpleNamespace(
        phase=phase,
        node=node,
        state=state,
        runtime=runtime,
        service=service,
        stored=stored,
        schedule=schedule,
        new_interrupter=new_interrupter,
        run=run,
    )


def install_hook(case, monkeypatch, hook_stage, source, outcome):
    action = "execute" if case.phase == "execute" else "schedule"
    hook = HookType.NODE_FINISH if hook_stage == "finish" else HookType("node_{}_{}".format(action, hook_stage))
    if hook_stage == "exception":
        getattr(case.service, action).side_effect = ValueError("ordinary plugin failure")
    elif hook_stage == "fail":
        getattr(case.service, action).return_value = False
        case.node.error_ignorable = False

    backend = SubprocessPoolRenderBackend(pool_size=1, os_harden=False, no_network=False)
    backend.close()
    monkeypatch.setattr(template, "get_render_backend", lambda: backend)

    def fail(*args, **kwargs):
        if outcome == "infrastructure":
            return Template("${x + 1}").render({"x": 2})
        if outcome == "ordinary":
            raise ValueError("ordinary hook failure")
        return False

    if source == "runtime":
        getattr(case.runtime, hook.value).side_effect = fail
    else:
        case.service.hook_dispatch.side_effect = lambda hook, **kwargs: fail() if hook == target else False
        target = hook


def assert_failed_without_dispatch(case, inter):
    assert case.state.name == states.FAILED
    assert case.stored.outputs["_result"] is False
    assert "isolated render failed" in case.stored.outputs["ex_data"]
    assert inter.check_point.handler_data.render_infrastructure_failed is True
    case.runtime.execute.assert_not_called()
    case.runtime.set_node_snapshot.assert_not_called()
    case.runtime.start_rollback.assert_not_called()
    case.runtime.finish_schedule.assert_not_called()
    case.runtime.set_next_schedule.assert_not_called()
    if case.phase == "execute":
        case.runtime.sleep.assert_called_once()
        assert inter.check_point.execute_result.next_node_id is None
    else:
        case.runtime.release_schedule_lock.assert_called_once_with(case.schedule.id)
        assert inter.check_point.schedule_result.schedule_done is False
        assert inter.check_point.schedule_result.next_node_id is None


@pytest.mark.parametrize("source", ["plugin", "runtime"])
@pytest.mark.parametrize("hook_stage", ["exception", "fail", "finish"])
def test_hook_infrastructure_failure_stops_engine(case, monkeypatch, hook_stage, source):
    install_hook(case, monkeypatch, hook_stage, source, "infrastructure")
    inter = case.new_interrupter()
    case.run(inter)
    assert_failed_without_dispatch(case, inter)


@pytest.mark.parametrize("outcome", ["ordinary", "success"])
@pytest.mark.parametrize("hook_stage", ["exception", "fail", "finish"])
def test_ordinary_plugin_hook_behavior_is_preserved(case, monkeypatch, hook_stage, outcome):
    install_hook(case, monkeypatch, hook_stage, "plugin", outcome)
    inter = case.new_interrupter()
    case.run(inter)
    if hook_stage == "fail":
        assert case.state.name == states.FAILED
        case.runtime.execute.assert_not_called()
        case.runtime.set_node_snapshot.assert_not_called()
    else:
        assert case.state.name == states.FINISHED
        case.runtime.execute.assert_called_once()
        case.runtime.set_node_snapshot.assert_called_once()
    if case.phase != "execute":
        case.runtime.release_schedule_lock.assert_called_once_with(case.schedule.id)


@pytest.mark.parametrize("hook_stage", ["exception", "fail", "finish"])
def test_ordinary_runtime_hook_exceptions_keep_existing_completion_behavior(case, monkeypatch, hook_stage):
    install_hook(case, monkeypatch, hook_stage, "runtime", "ordinary")
    with pytest.raises(ValueError, match="ordinary hook failure"):
        case.run(case.new_interrupter())
    case.runtime.execute.assert_not_called()
    case.runtime.set_node_snapshot.assert_not_called()
    if case.phase != "execute" and hook_stage == "finish":
        case.runtime.finish_schedule.assert_called_once_with(case.schedule.id)


@pytest.mark.parametrize("write_stage", ["outputs", "before_state", "after_state"])
@pytest.mark.parametrize("hook_stage", ["exception", "fail", "finish"])
def test_recover_hook_render_failure_after_database_interruption(case, monkeypatch, hook_stage, write_stage):
    install_hook(case, monkeypatch, hook_stage, "plugin", "infrastructure")
    original_set_state = case.runtime.set_state.side_effect
    original_set_outputs = case.runtime.set_execution_data_outputs.side_effect

    def interrupt_failure_write(*args, **kwargs):
        if kwargs["to_state"] == states.FAILED:
            if write_stage == "after_state":
                original_set_state(*args, **kwargs)
            raise RetryWriteError("synthetic database disconnect")
        return original_set_state(*args, **kwargs)

    if write_stage == "outputs":
        case.runtime.set_execution_data_outputs.side_effect = RetryWriteError("synthetic database disconnect")
    else:
        case.runtime.set_state.side_effect = interrupt_failure_write
    inter = case.new_interrupter()
    for _ in range(2):
        case.run(inter)
        checkpoint = type(inter.check_point).from_json(inter.latest_recover_point.to_json())
        assert checkpoint.handler_data.render_infrastructure_failed is True
        if case.phase == "execute":
            assert checkpoint.running_node_version == "v"
        inter = case.new_interrupter(checkpoint)

    case.runtime.set_state.side_effect = original_set_state
    case.runtime.set_execution_data_outputs.side_effect = original_set_outputs
    case.runtime.reset_mock()
    # The renderer is healthy now. Recovery must still fail without replaying plugin/hook work.
    case.service.hook_dispatch.side_effect = None
    case.service.execute.side_effect = None
    case.service.schedule.side_effect = None
    recovered = case.new_interrupter(checkpoint)
    case.run(recovered)
    assert case.state.name == states.FAILED
    assert case.stored.outputs["_result"] is False
    case.service.execute.assert_not_called()
    case.service.schedule.assert_not_called()
    case.service.hook_dispatch.assert_not_called()
    case.runtime.execute.assert_not_called()
    case.runtime.set_node_snapshot.assert_not_called()
    case.runtime.finish_schedule.assert_not_called()
    case.runtime.set_next_schedule.assert_not_called()
    if case.phase != "execute":
        assert recovered.check_point.lock_released is True
