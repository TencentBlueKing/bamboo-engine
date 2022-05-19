# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_exclusive_execution():
    start = EmptyStartEvent()
    eg = ExclusiveGateway(conditions={0: "True == True", 1: "True == False", 2: "True == False"})
    acts = [ServiceActivity(component_code="debug_node") for _ in range(3)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg).connect(*acts).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [pipeline["id"], start.id, eg.id, acts[0].id, cg.id, end.id]
    node_data_dict = {
        acts[0].id: {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        },
        pipeline["id"]: {"inputs": {}, "outputs": {}},
    }

    assert_all_finish(node_id_list)
    assert_not_executed([acts[1].id, acts[2].id])
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(acts[0].id, times=1)


def test_nest_exclusive_execution():
    start = EmptyStartEvent()
    eg_1 = ExclusiveGateway(conditions={0: "True == True", 1: "True == False", 2: "True == False"})
    eg_2 = ExclusiveGateway(conditions={0: "True == True", 1: "True == False"})
    acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(2)]
    acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(2)]
    cg_1 = ConvergeGateway()
    cg_2 = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg_1).connect(eg_2, *acts_group_1).to(eg_2).connect(*acts_group_2).converge(cg_1).to(eg_1).converge(
        cg_2
    ).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [
        pipeline["id"],
        start.id,
        eg_1.id,
        eg_2.id,
        acts_group_2[0].id,
        cg_1.id,
        cg_2.id,
        end.id,
    ]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        acts_group_2[0].id: {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        },
    }

    assert_all_finish(node_id_list)
    assert_not_executed([acts_group_1[0].id, acts_group_1[1].id, acts_group_2[1].id])
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(acts_group_2[0].id, times=1)


def test_template_exclusive_execution():
    start = EmptyStartEvent()
    eg = ExclusiveGateway(
        conditions={0: '"${a}" == "1"', 1: '"${b}" == "1"', 2: '"${c}" == "1"', 3: '"${d}" == "1"', 4: "True == False"}
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg).connect(*acts).converge(cg).extend(end)
    pipeline_data = Data()
    pipeline_data.inputs["${a}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="0")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="0")

    pipeline = build_tree(start, data=pipeline_data)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [pipeline["id"], start.id, eg.id, acts[0].id, cg.id, end.id]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        acts[0].id: {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        },
    }

    assert_all_finish(node_id_list)
    assert_not_executed([acts[1].id, acts[2].id, acts[3].id, acts[4].id])
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(acts[0].id, times=1)


def test_exclusive_execution_no_match():
    start = EmptyStartEvent()
    eg = ExclusiveGateway(
        conditions={0: "True == False", 1: "True == False", 2: "True == False", 3: "True == False", 4: "True == False"}
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg).connect(*acts).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [start.id]
    node_data_dict = {eg.id: {"inputs": {}, "outputs": {"ex_data": "all conditions of branches are not meet"}}}

    assert_all_finish(node_id_list)
    assert_all_failed([eg.id])
    assert_all_running([pipeline["id"]])
    assert_not_executed([acts[0].id, acts[1].id, acts[2].id, acts[3].id, acts[4].id, cg.id, end.id])
    assert_exec_data_equal(node_data_dict)


def test_exclusive_execution_no_match_with_default():
    start = EmptyStartEvent()
    eg = ExclusiveGateway(
        conditions={0: "True == False", 1: "True == False", 2: "True == False", 3: "True == False", 4: "True == False"},
        default_condition_outgoing=1,
    )
    acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg).connect(*acts).converge(cg).extend(end)

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
