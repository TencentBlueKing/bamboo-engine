# -*- coding: utf-8 -*-

from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine

from ..utils import *  # noqa


def test_parallel_execution():
    start = EmptyStartEvent()
    cpg = ConditionalParallelGateway(
        conditions={0: "True == True", 1: "True == True", 2: "True == True", 3: "True == False", 4: "True == False"}
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(cpg).connect(*acts).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [pipeline["id"], start.id, cpg.id, acts[0].id, acts[1].id, acts[2].id, cg.id, end.id]
    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts[:3]
    }
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}

    assert_all_finish(node_id_list)
    assert_not_executed([acts[3].id, acts[4].id])
    assert_exec_data_equal(node_data_dict)
    for a in acts[:3]:
        assert_schedule_finish(a.id, times=1)


def test_nest_parallel_execution():
    start = EmptyStartEvent()
    cpg_1 = ConditionalParallelGateway(
        conditions={0: "True == True", 1: "True == True", 2: "True == True", 3: "True == False", 4: "True == False"}
    )
    cpg_2 = ConditionalParallelGateway(
        conditions={0: "True == True", 1: "True == False", 2: "True == False", 3: "True == False", 4: "True == False"}
    )
    acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(4)]
    acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg_1 = ConvergeGateway()
    cg_2 = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(cpg_1).connect(cpg_2, *acts_group_1).to(cpg_2).connect(*acts_group_2).converge(cg_1).to(
        cpg_1
    ).converge(cg_2).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [
        pipeline["id"],
        start.id,
        cpg_1.id,
        cpg_2.id,
        acts_group_1[0].id,
        acts_group_1[1].id,
        acts_group_2[0].id,
        cg_1.id,
        cg_2.id,
        end.id,
    ]
    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts_group_1[:2]
    }
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}
    node_data_dict[acts_group_2[0].id] = {
        "inputs": {"_loop": 1, "_inner_loop": 1},
        "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
    }

    assert_all_finish(node_id_list)
    assert_not_executed(
        [
            acts_group_1[2].id,
            acts_group_1[3].id,
            acts_group_2[1].id,
            acts_group_2[2].id,
            acts_group_2[3].id,
            acts_group_2[4].id,
        ]
    )
    assert_exec_data_equal(node_data_dict)
    for a in acts_group_1[:2]:
        assert_schedule_finish(a.id, times=1)
    assert_schedule_finish(acts_group_2[0].id, times=1)


def test_template_parallel_execution():
    start = EmptyStartEvent()
    cpg = ConditionalParallelGateway(
        conditions={0: '"${a}" == "1"', 1: '"${b}" == "1"', 2: '"${c}" == "1"', 3: '"${d}" == "1"', 4: "True == False"}
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(cpg).connect(*acts).converge(cg).extend(end)
    pipeline_data = Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="0")

    pipeline = build_tree(start, data=pipeline_data)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [pipeline["id"], start.id, cpg.id, acts[0].id, acts[1].id, cg.id, end.id]
    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts[:2]
    }
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}

    assert_all_finish(node_id_list)
    assert_not_executed([acts[2].id, acts[3].id, acts[4].id])
    assert_exec_data_equal(node_data_dict)
    for a in acts[:2]:
        assert_schedule_finish(a.id, times=1)


def test_parallel_execution_no_match():
    start = EmptyStartEvent()
    cpg = ConditionalParallelGateway(
        conditions={0: "True == False", 1: "True == False", 2: "True == False", 3: "True == False", 4: "True == False"}
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(cpg).connect(*acts).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [start.id]
    node_data_dict = {cpg.id: {"inputs": {}, "outputs": {"ex_data": "all conditions of branches are not meet"}}}

    assert_all_finish(node_id_list)
    assert_all_failed([cpg.id])
    assert_all_running([pipeline["id"]])
    assert_not_executed([acts[0].id, acts[1].id, acts[2].id, acts[3].id, acts[4].id, cg.id, end.id])
    assert_exec_data_equal(node_data_dict)


def test_parallel_execution_no_match_with_default():
    start = EmptyStartEvent()
    cpg = ConditionalParallelGateway(
        conditions={0: "True == False", 1: "True == False", 2: "True == False", 3: "True == False", 4: "True == False"},
        default_condition_outgoing=1,
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(cpg).connect(*acts).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    node_id_list = [start.id]
    node_data_dict = {
        acts[1].id: {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        },
        pipeline["id"]: {"inputs": {}, "outputs": {}},
    }

    assert_all_finish(node_id_list)
    assert_not_executed([acts[0].id, acts[2].id, acts[3].id, acts[4].id])
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(acts[1].id, times=1)
