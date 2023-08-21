# -*- coding: utf-8 -*-

from bamboo_engine.builder import (
    ConditionalParallelGateway,
    ConvergeGateway,
    EmptyEndEvent,
    EmptyStartEvent,
    ExclusiveGateway,
    ParallelGateway,
    ServiceActivity,
    SubProcess,
    build_tree,
)
from bamboo_engine.builder.builder import generate_pipeline_token


def get_node_token(tree, name: str, node_map):
    # 根据 name 获取对应的token
    if name.startswith("act"):
        for activity_id, value in tree["activities"].items():
            if value["name"] == name:
                return node_map[activity_id]

    if (
        name.startswith("ParallelGateway")
        or name.startswith("ExclusiveGateway")
        or name.startswith("ConvergeGateway")
        or name.startswith("ConditionalParallelGateway")
    ):
        for gateway_id, value in tree["gateways"].items():
            if value["name"] == name:
                return node_map[gateway_id]

    if name.startswith("start_event"):
        return node_map[tree["start_event"]["id"]]

    if name.startswith("end_event"):
        return node_map[tree["end_event"]["id"]]


def test_inject_pipeline_token_normal():
    start = EmptyStartEvent()
    act = ServiceActivity(name="act_1", component_code="example_component")
    end = EmptyEndEvent()

    start.extend(act).extend(end)
    pipeline = build_tree(start)

    node_token_map = generate_pipeline_token(pipeline)

    assert get_node_token(pipeline, "act_1", node_token_map) == get_node_token(pipeline, "start_event", node_token_map)
    assert get_node_token(pipeline, "start_event", node_token_map) == get_node_token(
        pipeline, "end_event", node_token_map
    )


def test_inject_pipeline_token_parallel_gateway():
    start = EmptyStartEvent()
    pg = ParallelGateway(name="ParallelGateway")
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    cg = ConvergeGateway(name="ConvergeGateway")
    end = EmptyEndEvent()

    start.extend(pg).connect(act_1, act_2, act_3).to(pg).converge(cg).extend(end)

    pipeline = build_tree(start)
    node_token_map = generate_pipeline_token(pipeline)

    assert (
        get_node_token(pipeline, "start_event", node_token_map)
        == get_node_token(pipeline, "ParallelGateway", node_token_map)
        == get_node_token(pipeline, "ConvergeGateway", node_token_map)
        == get_node_token(pipeline, "end_event", node_token_map)
        != get_node_token(pipeline, "act_1", node_token_map)
    )

    assert (
        get_node_token(pipeline, "act_1", node_token_map)
        != get_node_token(pipeline, "act_2", node_token_map)
        != get_node_token(pipeline, "act_3", node_token_map)
    )


def test_inject_pipeline_token_exclusive_gateway():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    eg = ExclusiveGateway(conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0"}, name="ExclusiveGateway")
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    end = EmptyEndEvent()
    start.extend(act_1).extend(eg).connect(act_2, act_3).to(eg).converge(end)

    pipeline = build_tree(start)
    node_token_map = generate_pipeline_token(pipeline)

    assert (
        get_node_token(pipeline, "start_event", node_token_map)
        == get_node_token(pipeline, "act_1", node_token_map)
        == get_node_token(pipeline, "ExclusiveGateway", node_token_map)
        == get_node_token(pipeline, "end_event", node_token_map)
        != get_node_token(pipeline, "act_2", node_token_map)
    )

    assert get_node_token(pipeline, "act_2", node_token_map) == get_node_token(pipeline, "act_3", node_token_map)


def test_inject_pipeline_token_conditional_exclusive_gateway():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    cpg = ConditionalParallelGateway(
        conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0", 2: "${act_1_output} >= 0"},
        name="ConditionalParallelGateway",
    )
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    act_4 = ServiceActivity(component_code="pipe_example_component", name="act_4")
    cg = ConvergeGateway(name="ConvergeGateway")
    end = EmptyEndEvent()

    start.extend(act_1).extend(cpg).connect(act_2, act_3, act_4).to(cpg).converge(cg).extend(end)

    pipeline = build_tree(start)
    node_token_map = generate_pipeline_token(pipeline)
    assert (
        get_node_token(pipeline, "start_event", node_token_map)
        == get_node_token(pipeline, "act_1", node_token_map)
        == get_node_token(pipeline, "ConditionalParallelGateway", node_token_map)
        == get_node_token(pipeline, "ConvergeGateway", node_token_map)
        == get_node_token(pipeline, "end_event", node_token_map)
        != get_node_token(pipeline, "act_3", node_token_map)
    )

    assert (
        get_node_token(pipeline, "act_2", node_token_map)
        != get_node_token(pipeline, "act_3", node_token_map)
        != get_node_token(pipeline, "act_4", node_token_map)
    )


def test_inject_pipeline_token_subprocess():
    def sub_process(name):
        subproc_start = EmptyStartEvent()
        subproc_act = ServiceActivity(component_code="pipe_example_component", name="act_2")
        subproc_end = EmptyEndEvent()
        subproc_start.extend(subproc_act).extend(subproc_end)
        return SubProcess(start=subproc_start, name=name)

    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    eg = ExclusiveGateway(conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0"}, name="ExclusiveGateway")

    subproc_1 = sub_process(name="act_3")
    subproc_2 = sub_process(name="act_4")
    end = EmptyEndEvent()

    start.extend(act_1).extend(eg).connect(subproc_1, subproc_2).converge(end)

    pipeline = build_tree(start)
    node_token_map = generate_pipeline_token(pipeline)

    assert (
        get_node_token(pipeline, "start_event", node_token_map)
        == get_node_token(pipeline, "end_event", node_token_map)
        == get_node_token(pipeline, "ExclusiveGateway", node_token_map)
        == get_node_token(pipeline, "end_event", node_token_map)
        != get_node_token(pipeline, "act_3", node_token_map)
    )

    assert get_node_token(pipeline, "act_3", node_token_map) == get_node_token(pipeline, "act_4", node_token_map)

    subproc_pipeline = pipeline["activities"][subproc_1.id]["pipeline"]

    assert (
        get_node_token(subproc_pipeline, "start_event", node_token_map)
        == get_node_token(subproc_pipeline, "end_event", node_token_map)
        == get_node_token(subproc_pipeline, "act_2", node_token_map)
    )


def test_inject_pipeline_token_with_cycle():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    eg = ExclusiveGateway(
        conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0", 2: "${act_1_output} >= 0"},
        name="ExclusiveGateway",
    )
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    end = EmptyEndEvent()
    start.extend(act_1).extend(eg).connect(act_2, act_3, act_1).to(eg).converge(end)

    pipeline = build_tree(start)
    node_token_map = generate_pipeline_token(pipeline)

    assert (
        get_node_token(pipeline, "start_event", node_token_map)
        == get_node_token(pipeline, "act_1", node_token_map)
        == get_node_token(pipeline, "ExclusiveGateway", node_token_map)
        == get_node_token(pipeline, "end_event", node_token_map)
        != get_node_token(pipeline, "act_2", node_token_map)
    )

    assert get_node_token(pipeline, "act_2", node_token_map) == get_node_token(pipeline, "act_3", node_token_map)
