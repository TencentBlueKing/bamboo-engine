# -*- coding: utf-8 -*-

import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"get_context_key_references": {"raise_time": "pre"}}], id="get_context_key_references_raise"),
        pytest.param([{"get_context_values": {"raise_time": "pre"}}], id="get_context_values_raise"),
        pytest.param([{"fork": {"raise_time": "pre"}}], id="fork_raise"),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="pre_set_state_raise"),
        pytest.param([{"set_state": {"raise_time": "post", "raise_call_time": 4}}], id="post_set_state_raise"),
    ],
)
def test(execute_choas_plans):
    start = EmptyStartEvent()
    cpg = ConditionalParallelGateway(
        conditions={
            0: "'${a}' == '1_2'",
            1: "'${b}' == '1'",
            2: "'${c}' == '2'",
            3: "True == False",
            4: "True == False",
        }
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(cpg).connect(*acts).converge(cg).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.SPLICE, value="${b}_${c}")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="2")

    pipeline = build_tree(start, data=pipeline_data)
    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [pipeline["id"], start.id, cpg.id, acts[0].id, acts[1].id, acts[2].id, cg.id, end.id]
    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts[:3]
    }
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}

    assert_all_finish(node_id_list)
    assert_not_executed([acts[3].id, acts[4].id])
    assert_exec_data_equal(node_data_dict)
    for a in acts[:3]:
        assert_schedule_finish(a.id, times=1)