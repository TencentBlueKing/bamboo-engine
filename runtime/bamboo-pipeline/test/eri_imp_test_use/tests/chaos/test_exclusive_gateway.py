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
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="pre_set_state_raise"),
        pytest.param([{"set_state": {"raise_time": "post", "raise_call_time": 4}}], id="post_set_state_raise"),
    ],
)
def test(execute_choas_plans):
    start = EmptyStartEvent()
    eg = ExclusiveGateway(
        conditions={
            0: "'${a}' == '1_2'",
            1: "True == False",
        }
    )
    act_1 = ServiceActivity(component_code="debug_node")
    act_2 = ServiceActivity(component_code="debug_node")
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg).connect(act_1, act_2).converge(cg).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.SPLICE, value="${b}_${c}")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="2")

    pipeline = build_tree(start, data=pipeline_data)
    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([pipeline["id"], start.id, eg.id, act_1.id, cg.id, end.id])
    assert_not_executed([act_2.id])
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
            }
        }
    )
    assert_schedule_finish(act_1.id, times=1)