# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_pause_and_resume_pipeline_with_nest_parallel():
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

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    engine.pause_pipeline(pipeline["id"])

    finished = [start.id, pg_1.id, pg_2.id]
    finished.extend([a.id for a in sleep_group_1])
    finished.extend([a.id for a in sleep_group_2])

    sleep(6)

    state = runtime.get_state(pipeline["id"])
    assert state.name == states.SUSPENDED

    assert_all_finish(finished)

    not_execute = [cg_1.id, cg_2.id, end.id]
    not_execute.extend([a.id for a in acts_group_1])
    not_execute.extend([a.id for a in acts_group_2])
    assert_not_executed(not_execute)

    engine.resume_pipeline(pipeline["id"])

    sleep(2)

    finished.extend(not_execute)
    finished.append(pipeline["id"])

    assert_all_finish(finished)


def test_pause_and_resume_pipeline_with_nest_parallel_early_resume():
    parallel_count = 5
    start = EmptyStartEvent()
    pg_1 = ParallelGateway()
    pg_2 = ParallelGateway()
    sleep_group_1 = []

    for _ in range(parallel_count):
        act = ServiceActivity(component_code="sleep_timer")
        act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=5)
        sleep_group_1.append(act)

    sleep_group_2 = []
    for _ in range(parallel_count):
        act = ServiceActivity(component_code="sleep_timer")
        act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=5)
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

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    engine.pause_pipeline(pipeline["id"])

    state = runtime.get_state(pipeline["id"])
    assert state.name == states.SUSPENDED

    engine.resume_pipeline(pipeline["id"])

    finished = [start.id, pg_1.id, pg_2.id]
    finished.extend([a.id for a in sleep_group_1])
    finished.extend([a.id for a in sleep_group_2])
    finished.extend([cg_1.id, cg_2.id, end.id])
    finished.extend([a.id for a in acts_group_1])
    finished.extend([a.id for a in acts_group_2])
    finished.append(pipeline["id"])

    sleep(10)

    assert_all_finish(finished)


def test_pause_and_resume_pipeline_with_subprocess():
    subproc_start = EmptyStartEvent()
    subproc_act = ServiceActivity(component_code="sleep_timer")
    subproc_act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
    subproc_end = EmptyEndEvent()

    subproc_start.extend(subproc_act).extend(subproc_end)

    start = EmptyStartEvent()
    subproc = SubProcess(start=subproc_start)
    end = EmptyEndEvent()

    start.extend(subproc).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    engine.pause_pipeline(pipeline["id"])

    sleep(6)

    assert_all_finish([start.id, subproc_start.id, subproc_act.id])

    state = runtime.get_state(pipeline["id"])
    assert state.name == states.SUSPENDED

    assert_not_executed([subproc_end.id, end.id])
    assert_all_running([subproc.id])

    engine.resume_pipeline(pipeline["id"])

    sleep(2)

    assert_all_finish([pipeline["id"], start.id, subproc.id, end.id, subproc_start.id, subproc_act.id, subproc_end.id])


def test_pause_and_resume_pipeline_with_subprocess_has_parallel():
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

    sleep(2)

    engine.pause_pipeline(pipeline["id"])

    sleep(10)

    finished = [parent_start.id, start.id, pg_1.id, pg_2.id]
    finished.extend([a.id for a in sleep_group_1])
    finished.extend([a.id for a in sleep_group_2])

    state = runtime.get_state(pipeline["id"])
    assert state.name == states.SUSPENDED

    assert_all_finish(finished)
    assert_all_running([subproc.id])

    not_execute = [cg_1.id, cg_2.id, end.id, parent_end.id]
    not_execute.extend([a.id for a in acts_group_1])
    not_execute.extend([a.id for a in acts_group_2])
    assert_not_executed(not_execute)

    engine.resume_pipeline(pipeline["id"])

    sleep(2)

    finished.extend(not_execute)
    finished.append(pipeline["id"])

    assert_all_finish(finished)
