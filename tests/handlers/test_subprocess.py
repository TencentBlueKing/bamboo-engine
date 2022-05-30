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
    SubProcess,
    ContextValue,
    ContextValueType,
    Data,
    DataInput,
    ExecuteInterruptPoint,
)
from bamboo_engine.eri.models.interrupt import HandlerExecuteData
from bamboo_engine.handlers.subprocess import SubProcessHandler
from bamboo_engine.interrupt import ExecuteInterrupter, ExecuteKeyPoint


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(ExecuteInterruptPoint("n"), id="recover_is_not_none"),
        pytest.param(
            ExecuteInterruptPoint("n", handler_data=HandlerExecuteData(pipeline_stack_setted=True)),
            id="recover_is_not_none",
        ),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_subprocess_handler__execute_success(recover_point):
    pi = ProcessInfo(
        process_id="pid",
        destination_id="",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="parent",
    )

    node = SubProcess(
        id="nid",
        type=NodeType.ExecutableEndEvent,
        target_flows=[],
        target_nodes=[],
        targets={},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        can_skip=True,
        start_event_id="sid",
    )

    data = Data(
        inputs={
            "${k1}": DataInput(need_render=True, value="${v1}"),
            "${k2}": DataInput(need_render=True, value="${sub_loop}"),
        },
        outputs={"_loop": "${sub_loop}"},
    )

    context_values = [ContextValue(key="${v1}", value="var", type=ContextValueType.PLAIN)]

    interrupter = ExecuteInterrupter(
        runtime=MagicMock(),
        current_node_id="nid",
        process_id=1,
        parent_pipeline_id="parent",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(name="s1"),
        recover_point=None,
        headers={},
    )

    runtime = MagicMock()
    runtime.get_data = MagicMock(return_value=data)
    runtime.get_context_key_references = MagicMock(return_value=set())
    runtime.get_context_values = MagicMock(return_value=context_values)

    handler = SubProcessHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == False
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == node.start_event_id
    assert result.should_die == False

    runtime.get_data.assert_called_once_with(node.id)
    runtime.get_data_inputs.assert_called_once_with(pi.root_pipeline_id)
    runtime.get_context_key_references.assert_called_once_with(pipeline_id="root", keys={"${v1}", "${sub_loop}"})
    runtime.get_context_values.assert_called_once_with(pipeline_id="root", keys={"${v1}", "${sub_loop}"})
    runtime.reset_children_state_inner_loop.assert_called_once_with(node.id)
    upsert_call_args = runtime.upsert_plain_context_values.call_args.args
    assert upsert_call_args[0] == node.id
    assert upsert_call_args[1]["${k1}"].key == "${k1}"
    assert upsert_call_args[1]["${k1}"].type == ContextValueType.PLAIN
    assert upsert_call_args[1]["${k1}"].value == "var"
    assert upsert_call_args[1]["${k2}"].key == "${k2}"
    assert upsert_call_args[1]["${k2}"].type == ContextValueType.PLAIN
    assert upsert_call_args[1]["${k2}"].value == 1
    if recover_point and recover_point.handler_data.pipeline_stack_setted:
        runtime.set_pipeline_stack.assert_not_called()
    else:
        runtime.set_pipeline_stack.assert_called_once_with(pi.process_id, ["root", "nid"])
        assert pi.pipeline_stack == ["root", "nid"]

    assert interrupter.check_point.name == ExecuteKeyPoint.SP_SET_PIPELINE_STACK_DONE
