# -*- coding: utf-8 -*-
import typing

import pytest
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine

from ..utils import *  # noqa


def test_execution():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="hook_debug_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)

    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act_1.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {
                    "_inner_loop": 1,
                    "_loop": 1,
                    "_result": True,
                    "hook_call_order": ["node_enter", "execute", "schedule", "node_finish"],
                    "execute": 1,
                    "node_enter": 1,
                    "node_finish": 1,
                    "schedule": 1,
                },
            },
        }
    )
    assert_schedule_finish(act_1.id, times=1)


@pytest.mark.parametrize(
    "execute_raise,schedule_raise,error_ignorable,hook_call_order",
    [
        pytest.param(
            True,
            False,
            False,
            ["node_enter", "execute", "node_execute_exception", "node_execute_fail"],
            id="execute raise and not ignore",
        ),
        pytest.param(
            True,
            False,
            True,
            ["node_enter", "execute", "node_execute_exception", "node_finish"],
            id="execute raise and ignore",
        ),
        pytest.param(
            False,
            True,
            False,
            ["node_enter", "execute", "schedule", "node_schedule_exception", "node_schedule_fail"],
            id="schedule raise and not ignore",
        ),
        pytest.param(
            False,
            True,
            True,
            ["node_enter", "execute", "schedule", "node_schedule_exception", "node_finish"],
            id="schedule raise and ignore",
        ),
    ],
)
def test_node_fail(execute_raise: bool, schedule_raise: bool, error_ignorable: bool, hook_call_order: typing.List[str]):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="hook_interrupt_raise_test", error_ignorable=error_ignorable)
    act.component.inputs.execute_raise = Var(type=Var.PLAIN, value=execute_raise)
    act.component.inputs.schedule_raise = Var(type=Var.PLAIN, value=schedule_raise)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    if not error_ignorable:
        assert_all_failed([act.id])
    else:
        assert_all_finish([start.id, act.id, end.id])

    execution_data = runtime.get_execution_data(act.id)
    assert execution_data.outputs["hook_call_order"] == hook_call_order
