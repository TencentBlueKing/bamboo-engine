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
        pytest.param(
            [{"reset_children_state_inner_loop": {"raise_time": "pre"}}], id="reset_children_state_inner_loop_raise"
        ),
        pytest.param([{"get_context_key_references": {"raise_time": "pre"}}], id="get_context_key_references_raise"),
        pytest.param([{"get_context_values": {"raise_time": "pre"}}], id="get_context_values_raise"),
        pytest.param([{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"),
        pytest.param([{"set_pipeline_stack": {"raise_time": "pre"}}], id="set_pipeline_stack_raise"),
    ],
)
def test(execute_choas_plans):
    subproc_start = EmptyStartEvent()
    subproc_act = ServiceActivity(component_code="interrupt_test")
    subproc_act.component.inputs.param_1 = Var(type=Var.SPLICE, value="${sub_constant_1}")
    subproc_end = EmptyEndEvent()
    subproc_start.extend(subproc_act).extend(subproc_end)

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${sub_constant_1}"] = DataInput(type=Var.PLAIN, value="default_value")

    start = EmptyStartEvent()
    params = Params({"${sub_constant_1}": Var(type=Var.SPLICE, value="${constant_1}")})
    subproc = SubProcess(start=subproc_start, data=sub_pipeline_data, params=params)
    end = EmptyEndEvent()

    start.extend(subproc).extend(end)
    pipeline_data = Data()
    pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

    pipeline = build_tree(start, data=pipeline_data)
    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [pipeline["id"], subproc_start.id, subproc_act.id, subproc_end.id, start.id, subproc.id, end.id]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        subproc_act.id: {
            "inputs": {"param_1": "value_1", "_loop": 1, "_inner_loop": 1},
            "outputs": {"param_1": "value_1", "_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
        },
        subproc.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
    }

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)