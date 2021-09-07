# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_executable_end_event_execution():
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="debug_node")
    end = ExecutableEndEvent(type="MyTestEndEvent")

    start.extend(act).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    node_id_list = [pipeline["id"], start.id, act.id, end.id]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        act.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}},
    }

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(act.id, times=1)


def test_executable_end_event_raise():
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="debug_node")
    end = ExecutableEndEvent(type="MyRaiseEndEvent")

    start.extend(act).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    node_data_dict = {
        act.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}},
    }

    assert_all_finish([start.id, act.id])
    assert_all_running([pipeline["id"]])
    assert_all_failed([end.id])
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(act.id, times=1)


def test_executable_end_event_in_subprocess():
    sub_start = EmptyStartEvent()
    act = ServiceActivity(component_code="debug_node")
    sub_end = ExecutableEndEvent(type="MyTestEndEvent")

    sub_start.extend(act).extend(sub_end)

    start = EmptyStartEvent()
    subproc = SubProcess(start=sub_start)
    end = ExecutableEndEvent(type="MyTestEndEvent")

    start.extend(subproc).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    node_id_list = [pipeline["id"], start.id, subproc.id, end.id, sub_start.id, act.id, sub_end.id]
    node_data_dict = {
        pipeline["id"]: {"inputs": {}, "outputs": {}},
        act.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}},
    }

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(act.id, times=1)


def test_executable_end_event_raise_in_subproc():
    sub_start = EmptyStartEvent()
    act = ServiceActivity(component_code="debug_node")
    sub_end = ExecutableEndEvent(type="MyRaiseEndEvent")

    sub_start.extend(act).extend(sub_end)

    start = EmptyStartEvent()
    subproc = SubProcess(start=sub_start)
    end = ExecutableEndEvent(type="MyTestEndEvent")

    start.extend(subproc).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    node_data_dict = {
        act.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}},
    }

    assert_all_finish([start.id, act.id, sub_start.id])
    assert_all_running([pipeline["id"], subproc.id])
    assert_all_failed([sub_end.id])
    assert_exec_data_equal(node_data_dict)
    assert_schedule_finish(act.id, times=1)
