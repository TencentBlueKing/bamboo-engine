# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_pause_subprocess():
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

    parent_start = EmptyStartEvent()
    subproc = SubProcess(start=start)
    parent_end = EmptyEndEvent()

    parent_start.extend(subproc).extend(parent_end)

    pipeline = build_tree(parent_start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    engine.pause_pipeline(subproc.id)

    sleep(5)

    finished = [parent_start.id, start.id, pg_1.id, pg_2.id]
    finished.extend([a.id for a in sleep_group_1])
    finished.extend([a.id for a in sleep_group_2])

    state = runtime.get_state(subproc.id)
    assert state.name == states.SUSPENDED

    assert_all_finish(finished)
    assert_all_running([pipeline["id"]])

    not_execute = [cg_1.id, cg_2.id, end.id, parent_end.id]
    not_execute.extend([a.id for a in acts_group_1])
    not_execute.extend([a.id for a in acts_group_2])

    assert_not_executed(not_execute)

    engine.resume_pipeline(subproc.id)

    sleep(1)

    finished.extend(not_execute)
    finished.append(pipeline["id"])

    assert_all_finish(finished)


def test_pause_subprocess_in_parallel():
    sub_start_1 = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="sleep_timer")
    sub_act_1.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
    sub_end_1 = EmptyEndEvent()

    sub_start_1.extend(sub_act_1).extend(sub_end_1)

    sub_start_2 = EmptyStartEvent()
    sub_act_2 = ServiceActivity(component_code="sleep_timer")
    sub_act_2.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
    sub_end_2 = EmptyEndEvent()

    sub_start_2.extend(sub_act_2).extend(sub_end_2)

    start = EmptyStartEvent()
    pg = ParallelGateway()
    subproc_1 = SubProcess(start=sub_start_1)
    subproc_2 = SubProcess(start=sub_start_2)
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(subproc_1, subproc_2).converge(cg).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    engine.pause_pipeline(subproc_1.id)

    sleep(7)

    state = runtime.get_state(subproc_1.id)
    assert state.name == states.SUSPENDED

    finished = [start.id, pg.id, subproc_2.id, sub_start_2.id, sub_act_2.id, sub_end_2.id, sub_start_1.id, sub_act_1.id]

    assert_all_finish(finished)
    assert_all_running([pipeline["id"]])

    not_execute = [sub_end_1.id, cg.id, end.id]
    assert_not_executed(not_execute)

    engine.resume_pipeline(subproc_1.id)

    sleep(2)

    finished.extend(not_execute)
    finished.append(pipeline["id"])

    assert_all_finish(finished)
