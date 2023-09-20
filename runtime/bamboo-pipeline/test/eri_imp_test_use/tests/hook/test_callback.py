# -*- coding: utf-8 -*-

from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine

from ..utils import *  # noqa


def test_callback_node_success():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="hook_callback_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    assert_all_running([act_1.id])
    state = runtime.get_state(act_1.id)
    engine.callback(act_1.id, state.version, {})

    sleep(2)

    assert_all_finish([start.id, act_1.id, end.id])
    assert_schedule_finish(act_1.id, times=1)
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {
                    "_inner_loop": 1,
                    "_loop": 1,
                    "_result": True,
                    "hook_call_order": ["node_enter", "execute", "schedule"],
                    "execute": 1,
                    "node_enter": 1,
                    "schedule": 1,
                },
            }
        }
    )


def test_multi_callback_node_success():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="hook_multi_callback_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    assert_all_running([act_1.id])
    state = runtime.get_state(act_1.id)
    for schedule_time in range(3):
        engine.callback(act_1.id, state.version, {"bit": 1, "schedule_time": schedule_time})

    sleep(14)

    assert_schedule_not_finish(act_1.id, times=3, scheduling=False)

    for schedule_time in [3, 4]:
        engine.callback(act_1.id, state.version, {"bit": 1, "schedule_time": schedule_time})

    sleep(10)

    assert_all_finish([start.id, act_1.id, end.id])
    assert_schedule_finish(act_1.id, times=5)
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {
                    "_inner_loop": 1,
                    "_loop": 1,
                    "_result": True,
                    "hook_call_order": [
                        "node_enter",
                        "execute",
                        "schedule",
                        "schedule",
                        "schedule",
                        "schedule",
                        "schedule",
                    ],
                    "execute": 1,
                    "node_enter": 1,
                    "schedule": 5,
                    "_scheduled_times": 5,
                },
            }
        }
    )


def test_callback_node_fail_and_skip():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="hook_callback_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    assert_all_running([act_1.id])
    state = runtime.get_state(act_1.id)
    engine.callback(act_1.id, state.version, {"bit": 0})

    sleep(2)

    engine.skip_node(act_1.id)

    sleep(2)

    assert_all_finish([start.id, act_1.id, end.id])
    assert_schedule_not_finish(act_1.id, times=1)
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {
                    "node_enter": 1,
                    "hook_call_order": [
                        "node_enter",
                        "execute",
                        "schedule",
                        "node_schedule_fail",
                    ],
                    "execute": 1,
                    "_result": False,
                    "_loop": 1,
                    "_inner_loop": 1,
                    "schedule": 1,
                    "node_schedule_fail": 1,
                },
            }
        }
    )
