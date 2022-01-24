# -*- coding: utf-8 -*-

import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"fork": {"raise_time": "pre"}}], id="fork_raise"),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 4}}], id="pre_set_state_raise"),
        pytest.param([{"set_state": {"raise_time": "post", "raise_call_time": 4}}], id="post_set_state_raise"),
    ],
)
def test(execute_choas_plans):
    start = EmptyStartEvent()
    pg = ParallelGateway()
    act_1 = ServiceActivity(component_code="interrupt_test")
    act_2 = ServiceActivity(component_code="interrupt_test")
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(act_1, act_2).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([pipeline["id"], start.id, pg.id, act_1.id, act_2.id, cg.id, end.id])
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )