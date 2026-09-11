# -*- coding: utf-8 -*-
"""Real handler/render paths must stop the engine before dispatching business work."""
import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.engine import Engine
from bamboo_engine.eri import (
    Condition,
    ConditionalParallelGateway,
    ContextValue,
    ContextValueType,
    Data,
    DataInput,
    EmptyEndEvent,
    ExclusiveGateway,
    NodeType,
    ProcessInfo,
    ServiceActivity,
    SubProcess,
)
from bamboo_engine.handlers import empty_end_event  # noqa
from bamboo_engine.handlers import conditional_parallel_gateway, exclusive_gateway, service_activity, subprocess  # noqa
from bamboo_engine.interrupt import ExecuteInterrupter, ExecuteInterruptPoint
from bamboo_engine.template import template
from tests.template.test_render_backend_failures import pool


@pytest.mark.parametrize(
    "node_kind", ["service", "service_body", "subprocess", "exclusive", "conditional", "splice", "end", "end_sub"]
)
def test_render_failure_stops_node_before_business_dispatch(monkeypatch, node_kind):
    fields = dict(
        id="node",
        target_flows=["flow"],
        target_nodes=["next"],
        targets={"flow": "next"},
        root_pipeline_id="root",
        parent_pipeline_id="root",
    )
    if node_kind in ("service", "service_body", "splice"):
        node = ServiceActivity(
            type=NodeType.ServiceActivity, code="test", version="legacy", error_ignorable=True, **fields
        )
    elif node_kind == "subprocess":
        node = SubProcess(type=NodeType.SubProcess, start_event_id="child", **fields)
    elif node_kind in ("end", "end_sub"):
        node = EmptyEndEvent(type=NodeType.EmptyEndEvent, **fields)
    else:
        if node_kind == "conditional":
            fields["converge_gateway_id"] = "converge"
        gateway, kind = (
            (ExclusiveGateway, NodeType.ExclusiveGateway)
            if node_kind == "exclusive"
            else (ConditionalParallelGateway, NodeType.ConditionalParallelGateway)
        )
        node = gateway(
            type=kind,
            conditions=[Condition(name="branch", evaluation="${x + 1} == 3", target_id="next", flow_id="flow")],
            **fields
        )
    process = ProcessInfo(
        process_id="process",
        destination_id="end",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="",
    )
    if node_kind == "end_sub":
        process.pipeline_stack.append("child")
    initial_stack = list(process.pipeline_stack)
    interrupter = ExecuteInterrupter(
        runtime=MagicMock(),
        current_node_id=node.id,
        process_id=process.process_id,
        parent_pipeline_id="root",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(name="s1"),
        recover_point=None,
        headers={},
    )
    interrupter.runtime.interrupt_errors.return_value = ()
    runtime = MagicMock()
    runtime.get_process_info.return_value = process
    runtime.batch_get_state_name.return_value = {key: states.RUNNING for key in initial_stack}
    runtime.get_node.return_value = node
    runtime.get_state_or_none.return_value = None
    runtime.set_state.return_value = "version"
    runtime.get_data_inputs.return_value = {}
    runtime.get_execution_data_outputs.return_value = {}
    runtime.serialize_execution_data.return_value = ("{}", "json")
    runtime.get_service.side_effect = lambda **kwargs: pytest.fail("plugin resolved despite failed rendering")
    runtime.upsert_plain_context_values.side_effect = lambda *args, **kwargs: pytest.fail(
        "child context written after failed render"
    )
    runtime.get_context_key_references.return_value = set()
    values = [ContextValue(key="${x}", type=ContextValueType.PLAIN, value=2)]
    value = "prefix ${x + 1}"
    if node_kind == "splice":
        values.append(ContextValue(key="${computed}", type=ContextValueType.SPLICE, value="${x + 1}"))
        value = "${computed}"
    runtime.get_context_values.return_value = values
    if node_kind == "service_body":
        value = "plain input"
        runtime.get_service.side_effect = None
        runtime.get_service.return_value.execute.side_effect = lambda **kwargs: template.Template("${x + 1}").render(
            {"x": 2}
        )
        runtime.serialize_execution_data.return_value = ("{}", "json")
    if node_kind in ("end", "end_sub"):
        runtime.get_context_outputs.return_value = ["${computed}"]
        runtime.get_context_values.side_effect = [
            [ContextValue(key="${computed}", type=ContextValueType.SPLICE, value="${x + 1}")],
            values,
        ]
    runtime.get_data.return_value = Data({"value": DataInput(need_render=True, value=value)}, {})
    backend = pool(fallback_inprocess=True)

    def fail_start():
        raise OSError("synthetic process quota")

    monkeypatch.setattr(backend, "_spawn_worker", fail_start)
    monkeypatch.setattr(template, "get_render_backend", lambda: backend)
    try:
        Engine(runtime).execute(process.process_id, node.id, "root", "root", interrupter, {})
    finally:
        backend.close()

    assert runtime.set_state.call_args.kwargs["to_state"] == states.FAILED
    assert runtime.set_state.call_args.kwargs["version"] == "version"
    if node_kind == "service_body":
        runtime.get_service.return_value.execute.assert_called_once()
    else:
        runtime.get_service.assert_not_called()
    runtime.upsert_plain_context_values.assert_not_called()
    runtime.set_pipeline_stack.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.sleep.assert_called_once_with(process.process_id)
    assert process.pipeline_stack == initial_stack
    if node_kind in ("splice", "service_body"):
        outputs = runtime.set_execution_data.call_args.kwargs["data"].outputs
    else:
        outputs = runtime.set_execution_data_outputs.call_args.args[1]
    assert "isolated render failed" in outputs["ex_data"]
    assert outputs["_result"] is False
    if node_kind == "service_body":
        assert ExecuteInterruptPoint.from_json(
            interrupter.check_point.to_json()
        ).handler_data.render_infrastructure_failed
