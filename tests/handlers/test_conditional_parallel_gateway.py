# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from mock import MagicMock, patch

from bamboo_engine import states
from bamboo_engine.interrupt import ExecuteInterrupter, ExecuteKeyPoint
from bamboo_engine.eri import (
    ProcessInfo,
    NodeType,
    ConditionalParallelGateway,
    Condition,
    ExecuteInterruptPoint,
    DefaultCondition,
)
from bamboo_engine.handlers.conditional_parallel_gateway import (
    ConditionalParallelGatewayHandler,
)


@pytest.fixture
def pi():
    return ProcessInfo(
        process_id="pid",
        destination_id="",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="parent",
    )


@pytest.fixture
def conditions():
    return [
        Condition(name="c1", evaluation="${k} == 1", target_id="t1", flow_id="f1"),
        Condition(name="c2", evaluation="0 == 1", target_id="t2", flow_id="f2"),
    ]


@pytest.fixture
def node(conditions):
    return ConditionalParallelGateway(
        conditions=conditions,
        id="nid",
        type=NodeType.ConditionalParallelGateway,
        target_flows=["f1", "f2"],
        target_nodes=["t1", "t2"],
        targets={"f1": "t1", "f2": "t2"},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        can_skip=True,
        converge_gateway_id="cg",
    )


@pytest.fixture
def interrupter():
    return ExecuteInterrupter(
        runtime=MagicMock(),
        current_node_id="nid",
        process_id=1,
        parent_pipeline_id="parent",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(name="s1"),
        recover_point=None,
    )


@pytest.fixture
def recover_point():
    return ExecuteInterruptPoint(name=ExecuteKeyPoint.CPG_PROCESS_FORK_DONE, version=2)


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(MagicMock(), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_exclusive_gateway__context_hydrate_raise(pi, node, interrupter, recover_point):
    additional_refs = []

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value=additional_refs)
    runtime.get_context_values = MagicMock(return_value=[])
    runtime.get_execution_data_outputs = MagicMock(return_value={})
    runtime.get_data_inputs = MagicMock(return_value={})

    raise_context = MagicMock()
    raise_context.hydrate = MagicMock(side_effect=Exception)

    handler = ConditionalParallelGatewayHandler(node, runtime, interrupter)
    with patch("bamboo_engine.handlers.conditional_parallel_gateway.Context", MagicMock(return_value=raise_context)):
        with patch("bamboo_engine.handlers.conditional_parallel_gateway.BoolRule", MagicMock(side_effect=Exception)):
            result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_key_references.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys={"${k}"})
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys={"${k}"})
    runtime.get_execution_data_outputs.assert_called_once_with(node.id)
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FAILED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )
    runtime.set_execution_data_outputs.assert_called_once()


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(MagicMock(), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_conditional_parallel_gateway__execute_bool_rule_test_raise(pi, node, interrupter, recover_point):
    additional_refs = []

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value=additional_refs)
    runtime.get_context_values = MagicMock(return_value=[])
    runtime.get_execution_data_outputs = MagicMock(return_value={})
    runtime.get_data_inputs = MagicMock(return_value={})

    handler = ConditionalParallelGatewayHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_key_references.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys={"${k}"})
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys={"${k}"})
    runtime.get_execution_data_outputs.assert_called_once_with(node.id)
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FAILED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )
    runtime.set_execution_data_outputs.assert_called_once()


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(MagicMock(), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_conditional_parallel_gateway__execute_not_fork_targets(pi, node, interrupter, recover_point):
    additional_refs = []

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value=additional_refs)
    runtime.get_context_values = MagicMock(return_value=[])
    runtime.get_execution_data_outputs = MagicMock(return_value={})
    runtime.get_data_inputs = MagicMock(return_value={})

    handler = ConditionalParallelGatewayHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_key_references.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set({"${k}"}))
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set({"${k}"}))
    runtime.get_execution_data_outputs.assert_called_once_with(node.id)
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FAILED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )
    runtime.set_execution_data_outputs.assert_called_once_with(
        node.id, {"ex_data": "all conditions of branches are not meet"}
    )


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(ExecuteInterruptPoint(name="v1"), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_conditional_parallel_gateway__execute_success(pi, node, interrupter, recover_point):
    node.conditions = [
        Condition(name="c1", evaluation="0 == 1", target_id="t1", flow_id="f1"),
        Condition(name="c2", evaluation="1 == 1", target_id="t2", flow_id="f2"),
        Condition(name="c3", evaluation="1 == 1", target_id="t3", flow_id="f3"),
    ]
    additional_refs = []
    dispatch_processes = ["p1", "p2", "p3"]

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value=additional_refs)
    runtime.get_context_values = MagicMock(return_value=[])
    runtime.fork = MagicMock(return_value=dispatch_processes)
    runtime.get_data_inputs = MagicMock(return_value={})

    handler = ConditionalParallelGatewayHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == dispatch_processes
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_key_references.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set())
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set())
    runtime.fork.assert_called_once_with(
        parent_id=pi.process_id,
        root_pipeline_id=pi.root_pipeline_id,
        pipeline_stack=pi.pipeline_stack,
        from_to={"t2": "cg", "t3": "cg"},
    )
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FINISHED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.CPG_PROCESS_FORK_DONE
    assert len(interrupter.check_point.handler_data.dispatch_processes) > 0


def test_conditional_parallel_gateway__recover_with_dispatch_processes(pi, node, interrupter, recover_point):
    node.conditions = [
        Condition(name="c1", evaluation="0 == 1", target_id="t1", flow_id="f1"),
        Condition(name="c2", evaluation="1 == 1", target_id="t2", flow_id="f2"),
        Condition(name="c3", evaluation="1 == 1", target_id="t3", flow_id="f3"),
    ]
    recover_point.handler_data.dispatch_processes = ["p1", "p2", "p3"]
    interrupter.recover_point = recover_point
    additional_refs = []

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value=additional_refs)
    runtime.get_context_values = MagicMock(return_value=[])
    runtime.get_data_inputs = MagicMock(return_value={})

    handler = ConditionalParallelGatewayHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == recover_point.handler_data.dispatch_processes
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_key_references.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set())
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set())
    runtime.fork.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id, version="v1", to_state=states.FINISHED, set_archive_time=True, ignore_boring_set=True
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.CPG_PROCESS_FORK_DONE
    assert len(interrupter.check_point.handler_data.dispatch_processes) > 0


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(ExecuteInterruptPoint(name="v1"), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_conditional_parallel_gateway__no_meet_target_with_default_condition(pi, node, interrupter, recover_point):
    node.conditions = [
        Condition(name="c1", evaluation="0 == 1", target_id="t1", flow_id="f1"),
        Condition(name="c2", evaluation="0 == 1", target_id="t2", flow_id="f2"),
        Condition(name="c3", evaluation="0 == 1", target_id="t3", flow_id="f3"),
    ]
    node.default_condition = DefaultCondition(name="d1", target_id="t1", flow_id="f1")

    additional_refs = []
    dispatch_processes = ["p1"]

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value=additional_refs)
    runtime.get_context_values = MagicMock(return_value=[])
    runtime.fork = MagicMock(return_value=dispatch_processes)
    runtime.get_data_inputs = MagicMock(return_value={})

    handler = ConditionalParallelGatewayHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == dispatch_processes
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_key_references.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set())
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys=set())
    runtime.fork.assert_called_once_with(
        parent_id=pi.process_id,
        root_pipeline_id=pi.root_pipeline_id,
        pipeline_stack=pi.pipeline_stack,
        from_to={"t1": "cg"},
    )
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FINISHED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.CPG_PROCESS_FORK_DONE
    assert len(interrupter.check_point.handler_data.dispatch_processes) > 0
