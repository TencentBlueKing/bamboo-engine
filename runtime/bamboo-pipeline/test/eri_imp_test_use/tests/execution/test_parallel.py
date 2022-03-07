# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_parallel_execution():
    start = EmptyStartEvent()
    pg = ParallelGateway()
    acts = [ServiceActivity(component_code="debug_node") for _ in range(10)]
    additional_act = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    for i in range(len(additional_act)):
        acts[i].connect(additional_act[i])

    start.extend(pg).connect(*acts).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [pipeline["id"], start.id, pg.id, cg.id, end.id]
    node_id_list.extend([a.id for a in acts])
    node_id_list.extend([a.id for a in additional_act])

    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts
    }
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    for a in acts:
        assert_schedule_finish(a.id, times=1)


def test_nest_parallel_execution():
    start = EmptyStartEvent()
    pg_1 = ParallelGateway()
    pg_2 = ParallelGateway()
    acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(10)]
    acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(10)]
    cg_1 = ConvergeGateway()
    cg_2 = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg_1).connect(pg_2, *acts_group_1).to(pg_2).connect(*acts_group_2).converge(cg_1).to(pg_1).converge(
        cg_2
    ).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [pipeline["id"], start.id, pg_1.id, pg_2.id, cg_1.id, cg_2.id, end.id]
    node_id_list.extend([a.id for a in acts_group_1])
    node_id_list.extend([a.id for a in acts_group_2])

    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts_group_1
    }
    node_data_dict.update(
        {
            a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
            for a in acts_group_2
        }
    )
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    for a in acts_group_1:
        assert_schedule_finish(a.id, times=1)
    for a in acts_group_2:
        assert_schedule_finish(a.id, times=1)
