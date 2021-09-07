# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_pause_activity_in_plain():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="sleep_timer")
    act_0.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
    act_1 = ServiceActivity(component_code="debug_node")
    end = EmptyEndEvent()

    start.extend(act_0).extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    engine.pause_node_appoint(act_1.id)

    sleep(6)

    assert_all_running([pipeline["id"]])
    assert_all_finish([start.id, act_0.id])

    state = runtime.get_state(act_1.id)
    assert state.name == states.SUSPENDED

    engine.resume_node_appoint(act_1.id)

    sleep(1)

    assert_all_finish([pipeline["id"], start.id, act_0.id, act_1.id, end.id])


def test_pause_activity_in_plain_early_resume():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="sleep_timer")
    act_0.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
    act_1 = ServiceActivity(component_code="debug_node")
    end = EmptyEndEvent()

    start.extend(act_0).extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    engine.pause_node_appoint(act_1.id)

    sleep(1)

    assert_all_running([pipeline["id"], act_0.id])
    assert_all_finish([start.id])

    state = runtime.get_state(act_1.id)
    assert state.name == states.SUSPENDED

    engine.resume_node_appoint(act_1.id)

    sleep(5)

    assert_all_finish([pipeline["id"], start.id, act_0.id, act_1.id, end.id])


def test_pause_activity_in_parallel():
    parallel_count = 5
    start = EmptyStartEvent()
    pg_1 = ParallelGateway()
    pg_2 = ParallelGateway()
    sleep_group_1 = []

    for _ in range(parallel_count):
        act = ServiceActivity(component_code="sleep_timer")
        act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
        sleep_group_1.append(act)

    sleep_group_2 = []
    for _ in range(parallel_count):
        act = ServiceActivity(component_code="sleep_timer")
        act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
        sleep_group_2.append(act)

    acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(parallel_count)]
    acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(parallel_count)]
    cg_1 = ConvergeGateway()
    cg_2 = ConvergeGateway()
    end = EmptyEndEvent()

    for i in range(parallel_count):
        sleep_group_1[i].connect(acts_group_1[i])
        sleep_group_2[i].connect(acts_group_2[i])

    start.extend(pg_1).connect(pg_2, *sleep_group_1).to(pg_2).connect(*sleep_group_2).converge(cg_1).to(pg_1).converge(
        cg_2
    ).extend(end)

    pause_act = [acts_group_1[0], acts_group_1[1], acts_group_2[0], acts_group_2[1]]

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    for act in pause_act:
        engine.pause_node_appoint(act.id)

    sleep(5)

    for a in pause_act:
        state = runtime.get_state(a.id)
        assert state.name == states.SUSPENDED

    assert_all_running([pipeline["id"]])

    finish_nodes = [
        start.id,
        pg_1.id,
        pg_2.id,
        acts_group_1[2].id,
        acts_group_1[3].id,
        acts_group_1[4].id,
        acts_group_2[2].id,
        acts_group_2[3].id,
        acts_group_2[4].id,
    ]
    finish_nodes.extend([a.id for a in sleep_group_1])
    finish_nodes.extend([a.id for a in sleep_group_2])
    assert_all_finish(finish_nodes)
    assert_not_executed([cg_1.id, cg_2.id, end.id])

    for a in pause_act:
        engine.resume_node_appoint(a.id)

    sleep(2)
    finish_nodes.extend([cg_1.id, cg_2.id, end.id, pipeline["id"]])
    assert_all_finish(finish_nodes)


def test_pause_activity_in_subprocess():
    sub_1_start = EmptyStartEvent()
    sub_1_act_1 = ServiceActivity(component_code="sleep_timer")
    sub_1_act_1.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
    sub_1_act_2 = ServiceActivity(component_code="debug_node")
    sub_1_end = EmptyEndEvent()

    sub_1_start.extend(sub_1_act_1).extend(sub_1_act_2).extend(sub_1_end)

    sub_2_start = EmptyStartEvent()
    sub_2_act_1 = ServiceActivity(component_code="debug_node")
    sub_2_end = EmptyEndEvent()

    sub_2_start.extend(sub_2_act_1).extend(sub_2_end)

    sub_3_start = EmptyStartEvent()
    sub_3_pg = ParallelGateway()
    sub_3_subproc_1 = SubProcess(start=sub_1_start)
    sub_3_subproc_2 = SubProcess(start=sub_2_start)
    sub_3_cg = ConvergeGateway()
    sub_3_end = EmptyEndEvent()

    sub_3_start.extend(sub_3_pg).connect(sub_3_subproc_1, sub_3_subproc_2).converge(sub_3_cg).extend(sub_3_end)

    start = EmptyStartEvent()
    subproc = SubProcess(start=sub_3_start)
    end = EmptyEndEvent()

    start.extend(subproc).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    engine.pause_node_appoint(sub_1_act_2.id)

    sleep(5)

    state = runtime.get_state(sub_1_act_2.id)
    assert state.name == states.SUSPENDED

    assert_all_running([pipeline["id"], subproc.id, sub_3_subproc_1.id])
    assert_all_finish(
        [start.id, sub_3_start.id, sub_3_pg.id, sub_3_subproc_2.id, sub_2_start.id, sub_2_act_1.id, sub_2_end.id]
    )
    assert_not_executed([sub_3_cg.id, sub_3_end.id, end.id])

    engine.resume_node_appoint(sub_1_act_2.id)

    sleep(2)

    assert_all_finish(
        [
            start.id,
            sub_3_start.id,
            sub_3_pg.id,
            sub_3_subproc_2.id,
            sub_2_start.id,
            sub_2_act_1.id,
            sub_2_end.id,
            pipeline["id"],
            subproc.id,
            sub_3_subproc_1.id,
            sub_1_act_2.id,
            sub_3_cg.id,
            sub_3_end.id,
            end.id,
        ]
    )
