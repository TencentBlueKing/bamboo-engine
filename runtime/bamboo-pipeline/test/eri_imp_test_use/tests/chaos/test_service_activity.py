# -*- coding: utf-8 -*-

import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"get_data": {"raise_time": "pre", "raise_call_time": 2}}], id="get_data_raise"),
        pytest.param([{"get_context_key_references": {"raise_time": "pre"}}], id="get_context_key_references_raise"),
        pytest.param([{"get_context_values": {"raise_time": "pre"}}], id="get_context_values_raise"),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="set_state_raise"),
        pytest.param([{"set_execution_data": {"raise_time": "pre"}}], id="set_execution_data_raise"),
        pytest.param([{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"),
    ],
)
def test_execute(execute_choas_plans):
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
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="set_state_raise"),
        pytest.param([{"set_execution_data": {"raise_time": "pre"}}], id="set_execution_data_raise"),
        pytest.param([{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"),
    ],
)
def test_execute_failed(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_raise_test")
    act.component.inputs.execute_raise = Var(type=Var.PLAIN, value=True)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id])
    assert_all_failed([act.id])


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="set_state_raise"),
        pytest.param([{"set_execution_data": {"raise_time": "pre"}}], id="set_execution_data_raise"),
        pytest.param([{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"),
    ],
)
def test_execute_failed_error_ignore(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_raise_test", error_ignorable=True)
    act.component.inputs.execute_raise = Var(type=Var.PLAIN, value=True)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])


@pytest.mark.parametrize(
    "execute_choas_plans, schedule_choas_plans",
    [
        pytest.param([{"set_execution_data": {"raise_time": "pre"}}], [], id="execute_set_execution_data_raise"),
        pytest.param([], [{"get_data_outputs": {"raise_time": "pre"}}], id="get_data_outputs_raise"),
        pytest.param([], [{"get_execution_data": {"raise_time": "pre"}}], id="get_execution_data_raise"),
        pytest.param([], [{"add_schedule_times": {"raise_time": "pre"}}], id="add_schedule_times_raise"),
        pytest.param([], [{"set_execution_data": {"raise_time": "pre"}}], id="schedule_set_execution_data_raise"),
        pytest.param([], [{"set_state": {"raise_time": "pre"}}], id="set_state_raise"),
        pytest.param(
            [], [{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"
        ),
    ],
)
def test_schedule(execute_choas_plans, schedule_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_schedule_test")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(
            stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=schedule_choas_plans
        )
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "schedule_count": 1, "_result": True},
            },
        }
    )
    assert_schedule_finish(act.id, times=1)


@pytest.mark.parametrize(
    "schedule_choas_plans",
    [
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="set_state_raise"),
        pytest.param([{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"),
    ],
)
def test_schedule_failed(schedule_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_raise_test")
    act.component.inputs.schedule_raise = Var(type=Var.PLAIN, value=True)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=[], schedule_choas_plans=schedule_choas_plans)
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id])
    assert_all_failed([act.id])


@pytest.mark.parametrize(
    "schedule_choas_plans",
    [
        pytest.param(
            [{"add_schedule_times": {"raise_time": "pre", "raise_call_time": 4}}], id="add_schedule_times_raise"
        ),
        pytest.param([{"set_execution_data": {"raise_time": "pre"}}], id="set_execution_data_raise"),
    ],
)
def test_schedule_failed_error_ignore(schedule_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_raise_test", error_ignorable=True)
    act.component.inputs.schedule_raise = Var(type=Var.PLAIN, value=True)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=[], schedule_choas_plans=schedule_choas_plans)
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
    assert_schedule_finish(act.id, times=1)