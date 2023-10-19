# -*- coding: utf-8 -*-
import pytest

from bamboo_engine.builder import (
    ConditionalParallelGateway,
    ConvergeGateway,
    EmptyEndEvent,
    EmptyStartEvent,
    ExclusiveGateway,
    ParallelGateway,
    ServiceActivity,
    build_tree,
)
from bamboo_engine.exceptions import StartPositionInvalidException
from bamboo_engine.validator import (
    get_allowed_start_node_ids,
    validate_pipeline_start_node,
)
from bamboo_engine.validator.gateway import validate_gateways


def test_get_allowed_start_node_ids_by_parallel_gateway():
    """
    并行网关内的节点将会被忽略
    """
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    pg = ParallelGateway()
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    cg = ConvergeGateway()
    end = EmptyEndEvent()
    start.extend(act_1).extend(pg).connect(act_2, act_3).to(pg).converge(cg).extend(end)
    pipeline = build_tree(start)
    # 需要使用 validate_gateways 匹配网关对应的汇聚节点
    validate_gateways(pipeline)
    allowed_start_node_ids = get_allowed_start_node_ids(pipeline)

    assert len(allowed_start_node_ids) == 2
    assert allowed_start_node_ids == [start.id, act_1.id]


def test_get_allowed_start_node_ids_by_exclusive_gateway():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    eg = ExclusiveGateway(conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0"}, name="act_2 or act_3")
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    end = EmptyEndEvent()

    start.extend(act_1).extend(eg).connect(act_2, act_3).to(eg).converge(end)
    pipeline = build_tree(start)
    validate_gateways(pipeline)
    allowed_start_node_ids = get_allowed_start_node_ids(pipeline)

    assert len(allowed_start_node_ids) == 4
    assert allowed_start_node_ids == [start.id, act_1.id, act_2.id, act_3.id]


def test_get_allowed_start_node_ids_by_condition_parallel_gateway():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    cpg = ConditionalParallelGateway(
        conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0", 2: "${act_1_output} >= 0"},
        name="[act_2] or [act_3 and act_4]",
    )
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    act_4 = ServiceActivity(component_code="pipe_example_component", name="act_4")
    cg = ConvergeGateway()
    end = EmptyEndEvent()
    start.extend(act_1).extend(cpg).connect(act_2, act_3, act_4).to(cpg).converge(cg).extend(end)

    pipeline = build_tree(start)
    validate_gateways(pipeline)
    allowed_start_node_ids = get_allowed_start_node_ids(pipeline)

    assert len(allowed_start_node_ids) == 2
    assert allowed_start_node_ids == [start.id, act_1.id]


def test_get_allowed_start_node_ids_by_normal():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    end = EmptyEndEvent()
    start.extend(act_1).extend(act_2).extend(end)

    pipeline = build_tree(start)
    validate_gateways(pipeline)
    allowed_start_node_ids = get_allowed_start_node_ids(pipeline)

    assert len(allowed_start_node_ids) == 3
    assert allowed_start_node_ids == [start.id, act_1.id, act_2.id]


def test_validate_pipeline_start_node():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
    eg = ExclusiveGateway(conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0"}, name="act_2 or act_3")
    act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
    act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
    end = EmptyEndEvent()

    start.extend(act_1).extend(eg).connect(act_2, act_3).to(eg).converge(end)
    pipeline = build_tree(start)
    validate_gateways(pipeline)

    with pytest.raises(StartPositionInvalidException):
        validate_pipeline_start_node(pipeline, eg.id)

    validate_pipeline_start_node(pipeline, act_1.id)
