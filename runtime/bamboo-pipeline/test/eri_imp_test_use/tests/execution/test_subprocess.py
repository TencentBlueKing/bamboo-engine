# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_subprocess_execution():
    subproc_start = EmptyStartEvent()
    subproc_act = ServiceActivity(component_code="debug_node")
    subproc_end = EmptyEndEvent()

    subproc_start.extend(subproc_act).extend(subproc_end)

    start = EmptyStartEvent()
    subproc = SubProcess(start=subproc_start)
    end = EmptyEndEvent()

    start.extend(subproc).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [pipeline["id"], subproc_start.id, subproc_act.id, subproc_end.id, start.id, subproc.id, end.id]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        subproc_act.id: {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        },
        subproc.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
    }

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(subproc_act.id, times=1)


def test_parallel_subprocess_execution():
    start_nodes = []
    node_id_list = []
    act_id_list = []
    node_data_dict = {}

    for _ in range(5):
        subproc_start = EmptyStartEvent()
        subproc_act = ServiceActivity(component_code="debug_node")
        subproc_end = EmptyEndEvent()

        subproc_start.extend(subproc_act).extend(subproc_end)

        start_nodes.append(subproc_start)
        node_id_list.extend([subproc_start.id, subproc_act.id, subproc_end.id])
        node_data_dict[subproc_act.id] = {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        }
        act_id_list.append(subproc_act.id)

    start = EmptyStartEvent()
    pg = ParallelGateway()
    subprocs = [SubProcess(start=s) for s in start_nodes]

    # additioinal node
    additional_start = EmptyStartEvent()
    additional_act = ServiceActivity(component_code="debug_node")
    additional_end = EmptyEndEvent()

    additional_start.extend(additional_act).extend(additional_end)

    additional_subproc = SubProcess(start=additional_start)
    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg).connect(*subprocs).to(subprocs[0]).extend(additional_subproc).to(pg).converge(cg).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list.extend(
        [
            pipeline["id"],
            start.id,
            pg.id,
            additional_start.id,
            additional_act.id,
            additional_end.id,
            additional_subproc.id,
            cg.id,
            end.id,
        ]
    )
    node_id_list.extend([s.id for s in subprocs])
    act_id_list.append(additional_act.id)
    node_data_dict[additional_act.id] = {
        "inputs": {"_loop": 1, "_inner_loop": 1},
        "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
    }

    assert len(node_id_list) == 29
    node_data_dict.update(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            subprocs[0].id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
            subprocs[1].id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
            subprocs[2].id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
            subprocs[3].id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
            subprocs[4].id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        }
    )

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    for aid in act_id_list:
        assert_schedule_finish(aid, times=1)


def test_nest_subprocess_execution():
    subproc_start = EmptyStartEvent()
    subproc_act = ServiceActivity(component_code="debug_node")
    subproc_end = EmptyEndEvent()

    subproc_start.extend(subproc_act).extend(subproc_end)

    start = EmptyStartEvent()
    subproc = SubProcess(start=subproc_start)
    end = EmptyEndEvent()

    start.extend(subproc).extend(end)

    parent_start = EmptyStartEvent()
    parent_subproc = SubProcess(start=start)
    parent_end = EmptyEndEvent()

    parent_start.extend(parent_subproc).extend(parent_end)

    pipeline = build_tree(parent_start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    node_id_list = [
        pipeline["id"],
        subproc_start.id,
        subproc_act.id,
        subproc_end.id,
        start.id,
        subproc.id,
        end.id,
        parent_start.id,
        parent_subproc.id,
        parent_end.id,
    ]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        subproc_act.id: {
            "inputs": {"_loop": 1, "_inner_loop": 1},
            "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
        },
        subproc.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        parent_subproc.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
    }

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(subproc_act.id, times=1)


def test_subprocess_preset_context():
    subproc_start = EmptyStartEvent()
    subproc_act = ServiceActivity(component_code="debug_node")
    subproc_act.component.inputs.u = Var(type=Var.SPLICE, value="${user}")
    subproc_act.component.inputs.p = Var(type=Var.SPLICE, value="${password}")
    subproc_end = EmptyEndEvent()

    subproc_start.extend(subproc_act).extend(subproc_end)

    start = EmptyStartEvent()
    act = ServiceActivity(component_code="debug_node")
    act.component.inputs.u = Var(type=Var.SPLICE, value="${user}")
    act.component.inputs.p = Var(type=Var.SPLICE, value="${password}")
    subproc = SubProcess(start=subproc_start)
    end = EmptyEndEvent()

    start.extend(act).extend(subproc).extend(end)

    parent_start = EmptyStartEvent()
    parent_subproc = SubProcess(start=start)
    parent_end = EmptyEndEvent()

    parent_start.extend(parent_subproc).extend(parent_end)

    pipeline = build_tree(parent_start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(
        pipeline=pipeline, root_pipeline_data={}, subprocess_context={"${user}": "user00", "${password}": "password"}
    )

    

    node_id_list = [
        pipeline["id"],
        subproc_start.id,
        subproc_act.id,
        subproc_end.id,
        start.id,
        subproc.id,
        end.id,
        parent_start.id,
        parent_subproc.id,
        parent_end.id,
    ]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        subproc_act.id: {
            "inputs": {"u": "user00", "p": "password", "_loop": 1, "_inner_loop": 1},
            "outputs": {"u": "user00", "p": "password", "_loop": 1, "_inner_loop": 1, "_result": True},
        },
        act.id: {
            "inputs": {"u": "user00", "p": "password", "_loop": 1, "_inner_loop": 1},
            "outputs": {"u": "user00", "p": "password", "_loop": 1, "_inner_loop": 1, "_result": True},
        },
        subproc.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        parent_subproc.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
    }

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(subproc_act.id, times=1)
