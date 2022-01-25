# -*- coding: utf-8 -*-

import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"get_context_outputs": {"raise_time": "pre"}}], id="get_context_outputs_raise"),
        pytest.param(
            [{"get_context_values": {"raise_time": "pre", "raise_call_time": 2}}], id="get_context_values_raise"
        ),
        pytest.param([{"set_execution_data_outputs": {"raise_time": "pre"}}], id="set_execution_data_outputs_raise"),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 6}}], id="set_end_event_state_raise"),
        pytest.param(
            [{"get_state_or_none": {"raise_time": "pre", "raise_call_time": 10}}], id="get_state_or_none_raise"
        ),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 7}}], id="set_pipeline_state_raise"),
    ],
)
def test_root_pipeline_finish(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_test")
    act.component.inputs.param_1 = Var(type=Var.SPLICE, value="${a}_3")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.SPLICE, value="${b}_${c}")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="2")
    pipeline_data.inputs["${act_output}"] = NodeOutput(
        source_act=act.id, source_key="param_1", type=Var.SPLICE, value=""
    )
    pipeline_data.outputs = ["${a}", "${act_output}"]

    pipeline = build_tree(start, data=pipeline_data)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "1_2_3"},
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "1_2_3",
                    "execute_count": 1,
                    "_result": True,
                },
            },
            pipeline["id"]: {
                "inputs": {},
                "outputs": {"${a}": "1_2", "${act_output}": "1_2_3"},
            },
        }
    )
    context = get_context_dict(pipeline["id"])
    assert context.get("${a}").value == "${b}_${c}"
    assert context.get("${b}").value == "1"
    assert context.get("${c}").value == "2"
    assert context.get("${act_output}").value == "1_2_3"


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"get_node": {"raise_time": "pre", "raise_call_time": 6}}], id="get_state_raise"),
        pytest.param([{"get_data_outputs": {"raise_time": "pre"}}], id="get_data_outputs_raise"),
        pytest.param(
            [{"upsert_plain_context_values": {"raise_time": "pre", "raise_call_time": 3}}],
            id="upsert_plain_context_values_raise",
        ),
        pytest.param(
            [{"set_pipeline_stack": {"raise_time": "pre", "raise_call_time": 2}}], id="set_pipeline_stack_raise"
        ),
    ],
)
def test_not_root_pipeline_finish(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_test")
    act.component.inputs.param_1 = Var(type=Var.SPLICE, value="${a}_3")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.SPLICE, value="${b}_${c}")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="2")
    pipeline_data.inputs["${act_output}"] = NodeOutput(
        source_act=act.id, source_key="param_1", type=Var.SPLICE, value=""
    )
    pipeline_data.outputs = ["${a}", "${act_output}"]

    parent_start = EmptyStartEvent()
    subproc = SubProcess(start=start, data=pipeline_data)
    parent_act = ServiceActivity(component_code="interrupt_test")
    parent_act.component.inputs.param2 = Var(type=Var.SPLICE, value="${sub_proc_output}")
    parent_end = EmptyEndEvent()

    parent_start.extend(subproc).extend(parent_act).extend(parent_end)

    parent_pipeline_data = Data()
    parent_pipeline_data.inputs["${sub_proc_output}"] = NodeOutput(
        source_act=subproc.id, source_key="${act_output}", type=Var.SPLICE, value=""
    )

    pipeline = build_tree(parent_start, data=parent_pipeline_data)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish(
        [parent_start.id, subproc.id, start.id, act.id, end.id, parent_act.id, parent_end.id, pipeline["id"]]
    )
    assert_exec_data_equal(
        {
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "1_2_3"},
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "1_2_3",
                    "execute_count": 1,
                    "_result": True,
                },
            },
            subproc.id: {
                "inputs": {},
                "outputs": {"${a}": "1_2", "${act_output}": "1_2_3", "_loop": 1, "_inner_loop": 1},
            },
            parent_act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param2": "1_2_3"},
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param2": "1_2_3",
                    "execute_count": 1,
                    "_result": True,
                },
            },
        }
    )
