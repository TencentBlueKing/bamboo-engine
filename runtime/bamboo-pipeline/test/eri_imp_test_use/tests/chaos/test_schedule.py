# -*- coding: utf-8 -*-

from os import pipe
import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans, schedule_choas_plans",
    [
        pytest.param([], [{"get_process_info": {"raise_time": "pre"}}], id="get_process_info_raise"),
        pytest.param([], [{"get_state": {"raise_time": "pre"}}], id="get_state_raise"),
        pytest.param([], [{"get_schedule": {"raise_time": "pre"}}], id="get_schedule_raise"),
        pytest.param([], [{"apply_schedule_lock": {"raise_time": "pre"}}], id="apply_schedule_lock_raise"),
        pytest.param([], [{"get_node": {"raise_time": "pre"}}], id="get_node_raise"),
        pytest.param([], [{"release_schedule_lock": {"raise_time": "pre"}}], id="release_schedule_lock_raise"),
        pytest.param([], [{"finish_schedule": {"raise_time": "pre"}}], id="finish_schedule_raise"),
    ],
)
def test(execute_choas_plans, schedule_choas_plans):
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
    assert_schedule_finish(act.id, times=1)
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "schedule_count": 1, "_result": True},
            },
        }
    )


@pytest.mark.parametrize(
    "execute_choas_plans, schedule_choas_plans",
    [
        pytest.param([], [{"get_callback_data": {"raise_time": "pre"}}], id="get_callback_data_raise"),
    ],
)
def test_callback(execute_choas_plans, schedule_choas_plans):
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = ChoasBambooDjangoRuntime(
        stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=schedule_choas_plans
    )
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_running([act_1.id])
    state = runtime.get_state(act_1.id)
    engine.callback(act_1.id, state.version, {})

    assert_all_finish([start.id, act_1.id, end.id])
    assert_schedule_finish(act_1.id, times=1)