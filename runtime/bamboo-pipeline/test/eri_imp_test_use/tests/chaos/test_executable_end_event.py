# -*- coding: utf-8 -*-

import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"set_execution_data_outputs": {"raise_time": "pre"}}], id="set_execution_data_outputs_raise"),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 6}}], id="set_state_raise"),
    ],
)
def test(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_test")
    end = ExecutableEndEvent(type="MyRaiseEndEvent")

    start.extend(act).extend(end)

    pipeline = build_tree(start)
    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id])
    assert_all_failed([end.id])