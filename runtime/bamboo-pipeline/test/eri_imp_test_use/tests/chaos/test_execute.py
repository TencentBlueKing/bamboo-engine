# -*- coding: utf-8 -*-

from os import pipe
import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"get_process_info": {"raise_time": "pre"}}], id="get_process_info_raise"),
        pytest.param([{"wake_up": {"raise_time": "pre"}}], id="pre_wake_up_raise"),
        pytest.param([{"wake_up": {"raise_time": "post"}}], id="post_wake_up_raise"),
        pytest.param([{"beat": {"raise_time": "pre"}}], id="beat_raise"),
        pytest.param([{"set_current_node": {"raise_time": "pre"}}], id="pre_set_current_node_raise"),
        pytest.param([{"set_current_node": {"raise_time": "post"}}], id="post_set_current_node_raise"),
        pytest.param([{"batch_get_state_name": {"raise_time": "pre"}}], id="batch_get_state_name_raise"),
        pytest.param([{"get_node": {"raise_time": "pre"}}], id="get_node_raise"),
        pytest.param([{"get_state_or_none": {"raise_time": "pre"}}], id="get_state_or_none_raise"),
        pytest.param([{"set_state": {"raise_time": "pre"}}], id="pre_set_state_raise"),
        pytest.param([{"set_state": {"raise_time": "post"}}], id="post_set_state_raise"),
    ],
)
def test(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_test")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{}, {"child_process_finish": {"raise_time": "pre"}}], id="pre_child_process_finish_raise"),
    ],
)
def test_child_process_finish(execute_choas_plans):
    start = EmptyStartEvent()
    pg = ParallelGateway()
    act_1 = ServiceActivity(component_code="interrupt_test")
    act_2 = ServiceActivity(component_code="interrupt_test")
    act_3 = ServiceActivity(component_code="interrupt_test")
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(act_1, act_2, act_3).converge(cg).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, pg.id, act_1.id, act_2.id, act_3.id, cg.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
            act_3.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"die": {"raise_time": "pre"}}], id="pre_die_raise"),
        pytest.param([{"die": {"raise_time": "post"}}], id="post_die_raise"),
    ],
)
def test_revoke_die(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_dummy_exec_node")
    act.component.inputs.time = Var(type=Var.PLAIN, value=5)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})
    sleep(1)

    engine.revoke_pipeline(pipeline["id"])

    assert_all_revoked([pipeline["id"]])
    assert_all_finish([start.id, act.id])
    assert_not_executed([end.id])
    assert_exec_data_equal(
        {
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "time": 5},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"suspend": {"raise_time": "pre"}}], id="pre_suspend_raise"),
        pytest.param([{"suspend": {"raise_time": "post"}}], id="post_suspend_raise"),
    ],
)
def test_pipeline_suspended(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_dummy_exec_node")
    act.component.inputs.time = Var(type=Var.PLAIN, value=5)
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})
    sleep(1)

    engine.pause_pipeline((pipeline["id"]))

    assert_all_suspended([pipeline["id"]])
    assert_all_finish([start.id, act.id])
    assert_not_executed([end.id])
    assert_exec_data_equal(
        {
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "time": 5},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"node_rerun_limit": {"raise_time": "pre"}}], id="pre_node_rerun_limit_raise"),
        pytest.param([{"node_rerun_limit": {"raise_time": "post"}}], id="post_node_rerun_limit_raise"),
    ],
)
def test_node_rerun_limit(execute_choas_plans):
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="interrupt_test")
    act_2 = ServiceActivity(component_code="interrupt_test")
    eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
    end = EmptyEndEvent()

    act_2.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

    start.extend(act_1).extend(act_2).extend(eg).connect(act_1, end)

    pipeline_data = Data()
    pipeline_data.inputs["${a_i}"] = NodeOutput(type=Var.SPLICE, source_act=act_2.id, source_key="_loop", value="")
    pipeline_data.inputs["${input_a}"] = Var(type=Var.SPLICE, value='${l.split(",")[a_i]}')
    pipeline_data.inputs["${l}"] = Var(type=Var.PLAIN, value="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="4")

    pipeline = build_tree(start, data=pipeline_data)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([start.id, act_1.id, act_2.id, eg.id, end.id, pipeline["id"]])

    state = runtime.get_state(act_1.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(eg.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(act_2.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 4, "_inner_loop": 4},
                "outputs": {"_loop": 4, "_inner_loop": 4, "execute_count": 1, "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 4, "_inner_loop": 4, "input_a": "e"},
                "outputs": {
                    "_loop": 4,
                    "_inner_loop": 4,
                    "input_a": "e",
                    "execute_count": 1,
                    "_result": True,
                },
            },
        }
    )

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 3
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "execute_count": 1, "_result": True}
    assert histories[1].loop == 2
    assert histories[2].inputs == {"_loop": 3, "_inner_loop": 3}
    assert histories[2].outputs == {"_loop": 3, "_inner_loop": 3, "execute_count": 1, "_result": True}
    assert histories[2].loop == 3

    histories = runtime.get_histories(act_2.id)
    assert len(histories) == 3
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b"}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "input_a": "b", "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2, "input_a": "c"}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "execute_count": 1, "input_a": "c", "_result": True}
    assert histories[1].loop == 2
    assert histories[2].inputs == {"_loop": 3, "_inner_loop": 3, "input_a": "d"}
    assert histories[2].outputs == {"_loop": 3, "_inner_loop": 3, "execute_count": 1, "input_a": "d", "_result": True}
    assert histories[2].loop == 3


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"sleep": {"raise_time": "pre"}}], id="pre_after_execute_sleep_raise"),
        pytest.param([{"sleep": {"raise_time": "post"}}], id="post_after_execute_sleep_raise"),
        pytest.param([{"set_schedule": {"raise_time": "pre"}}], id="pre_after_execute_set_schedule_raise"),
        pytest.param([{"set_schedule": {"raise_time": "post"}}], id="post_after_execute_set_schedule_raise"),
    ],
)
def test_schedule_prepare(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_schedule_test")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
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
    "execute_choas_plans",
    [
        pytest.param([{"die": {"raise_time": "pre"}}], id="pre_finish_die_raise"),
        pytest.param([{"die": {"raise_time": "post"}}], id="post_finish_die_raise"),
    ],
)
def test_finish_die(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_test")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"join": {"raise_time": "pre"}}], id="pre_join_raise"),
        pytest.param([{"join": {"raise_time": "post"}}], id="post_join_raise"),
    ],
)
def test_join(execute_choas_plans):
    start = EmptyStartEvent()
    pg = ParallelGateway()
    act_1 = ServiceActivity(component_code="interrupt_test")
    act_2 = ServiceActivity(component_code="interrupt_test")
    act_3 = ServiceActivity(component_code="interrupt_test")
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(act_1, act_2, act_3).converge(cg).extend(end)

    pipeline = build_tree(start)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, pg.id, act_1.id, act_2.id, act_3.id, cg.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
            act_3.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "execute_count": 1, "_result": True},
            },
        }
    )