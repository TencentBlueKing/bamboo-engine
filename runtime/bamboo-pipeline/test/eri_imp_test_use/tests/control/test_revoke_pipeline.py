# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_revoke_pipeline_with_nest_parallel():
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

    sleep(1)

    engine.revoke_pipeline(pipeline["id"])

    sleep(5)

    finished = [start.id, pg_1.id, pg_2.id]
    finished.extend([a.id for a in sleep_group_1])
    finished.extend([a.id for a in sleep_group_2])

    assert_all_finish(finished)

    state = runtime.get_state(pipeline["id"])
    assert state.name == states.REVOKED

    not_execute = [cg_1, cg_2, end]
    not_execute.extend([a.id for a in acts_group_1])
    not_execute.extend([a.id for a in acts_group_2])

    assert_not_executed(not_execute)
