# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from mailbox import Mailbox
import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.eri import (
    ProcessInfo,
    NodeType,
    EmptyStartEvent,
    Data,
    ContextValue,
    ContextValueType,
    DataInput,
)
from bamboo_engine.handlers.empty_start_event import EmptyStartEventHandler


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(MagicMock, id="recover_is_not_none"),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_empty_start_event_handler__execute_success(recover_point):
    # ContextValue 各个属性值相等即判断为相等，用于assert生成的函数入参
    def mock_eq_func(self, other):
        return (
            self.key == other.key and self.value == other.value and self.type == other.type and self.code == other.code
        )

    setattr(ContextValue, "__eq__", mock_eq_func)

    pi = ProcessInfo(
        process_id="pid",
        destination_id="",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="parent",
    )

    node = EmptyStartEvent(
        id="nid",
        type=NodeType.EmptyStartEvent,
        target_flows=["f1"],
        target_nodes=["t1"],
        targets={"f1": "t1"},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        can_skip=True,
    )

    context_values = [
        ContextValue(
            key="${a}",
            value="${c}",
            type=ContextValueType.SPLICE,
        ),
        ContextValue(
            key="${b}",
            value="b: ${a}",
            type=ContextValueType.SPLICE,
        ),
        ContextValue(key="${c}", value="1", type=ContextValueType.PLAIN),
    ]

    upsert_context_dict = {
        "${a}": ContextValue(
            key="${a}",
            value="1",
            type=ContextValueType.PLAIN,
        ),
        "${b}": ContextValue(
            key="${b}",
            value="b: 1",
            type=ContextValueType.PLAIN,
        ),
    }

    data = Data(
        inputs={"pre_render_keys": DataInput(need_render=True, value=["${a}", "${b}"])},
        outputs={},
    )

    runtime = MagicMock()
    runtime.get_context_key_references = MagicMock(return_value={"${c}"})
    runtime.get_context_values = MagicMock(return_value=context_values)
    runtime.get_data = MagicMock(return_value=data)

    handler = EmptyStartEventHandler(node, runtime, MagicMock())
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == False
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    assert result.dispatch_processes == []
    assert result.next_node_id == node.target_nodes[0]
    assert result.should_die == False

    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FINISHED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )
    runtime.get_context_values.assert_called_once_with(pipeline_id=pi.top_pipeline_id, keys={"${a}", "${b}", "${c}"})
    runtime.upsert_plain_context_values.assert_called_once_with(pi.top_pipeline_id, upsert_context_dict)
