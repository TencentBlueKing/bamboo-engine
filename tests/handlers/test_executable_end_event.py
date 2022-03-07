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
specific language governing permissions and limitations underExecutableEndEvent the License.
"""

import pytest
from mock import MagicMock, call

from bamboo_engine import states
from bamboo_engine.eri import (
    ProcessInfo,
    NodeType,
    ExecutableEndEvent,
    ContextValue,
    ContextValueType,
)
from bamboo_engine.eri.models.interrupt import ExecuteInterruptPoint
from bamboo_engine.handlers.executable_end_event import ExecutableEndEventHandler


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
def node():
    return ExecutableEndEvent(
        id="nid",
        type=NodeType.ExecutableEndEvent,
        target_flows=[],
        target_nodes=[],
        targets={},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        can_skip=True,
        code="eee",
    )


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(MagicMock(), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_executable_end_event_handler__event_execute_error(pi, node, recover_point):

    event = MagicMock()
    event.execute = MagicMock(side_effect=Exception)

    runtime = MagicMock()
    runtime.get_executable_end_event = MagicMock(return_value=event)

    handler = ExecutableEndEventHandler(node, runtime, MagicMock())
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == None
    assert result.should_die == False

    runtime.get_executable_end_event.assert_called_once_with(code=node.code)
    if not recover_point:
        event.execute.assert_called_once_with(pipeline_stack=["root"], root_pipeline_id="root")
    else:
        event.exeucte.assert_not_called()
    runtime.set_execution_data_outputs.assert_called_once()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FAILED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(ExecuteInterruptPoint("n"), id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_executable_end_event_handler__event_execute_success(pi, node, recover_point):

    event = MagicMock()
    event.execute = MagicMock()

    context_outputs = ["${a}", "${b}", "${c}", "${d}"]
    context_values = [
        ContextValue(key="${a}", value="1", type=ContextValueType.PLAIN),
        ContextValue(key="${b}", value="2", type=ContextValueType.PLAIN),
        ContextValue(key="${c}", value="3", type=ContextValueType.PLAIN),
    ]

    pipeline_state = MagicMock()
    pipeline_state.version = "v2"

    runtime = MagicMock()
    runtime.get_executable_end_event = MagicMock(return_value=event)
    runtime.get_data_inputs = MagicMock(return_value={})
    runtime.get_context_outputs = MagicMock(return_value=context_outputs)
    runtime.get_context_values = MagicMock(return_value=context_values)
    runtime.get_state_or_none = MagicMock(return_value=pipeline_state)

    handler = ExecutableEndEventHandler(node, runtime, MagicMock())
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == False
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == None
    assert result.should_die == True

    runtime.get_executable_end_event.assert_called_once_with(code=node.code)
    event.execute.assert_called_once_with(pipeline_stack=["root"], root_pipeline_id="root")
    runtime.get_data_inputs.assert_called_once_with("root")
    runtime.get_context_outputs.assert_called_once_with("root")
    runtime.get_context_values.assert_has_calls(
        [call(pipeline_id="root", keys=context_outputs), call(pipeline_id="root", keys=set())]
    )
    runtime.set_execution_data_outputs.assert_called_once_with(
        node_id="root",
        outputs={
            "${a}": "1",
            "${b}": "2",
            "${c}": "3",
            "${d}": "${d}",
        },
    )
    runtime.set_state.assert_has_calls(
        [
            call(
                node_id=node.id,
                version="v1",
                to_state=states.FINISHED,
                set_archive_time=True,
                ignore_boring_set=recover_point is not None,
            ),
            call(
                node_id="root",
                version="v2",
                to_state=states.FINISHED,
                set_archive_time=True,
                ignore_boring_set=recover_point is not None,
            ),
        ]
    )
    assert pi.pipeline_stack == []
