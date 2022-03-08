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
from mock import MagicMock
from bamboo_engine.eri.models.interrupt import ExecuteInterruptPoint, HandlerExecuteData

from bamboo_engine.interrupt import ExecuteInterrupter, InterruptException


@pytest.fixture
def interrupter():
    return ExecuteInterrupter(
        runtime=MagicMock(),
        current_node_id="node1",
        process_id=1,
        parent_pipeline_id="parent",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(
            name="s1",
            state_already_exist=True,
            running_node_version="version",
            execute_result=MagicMock(),
            set_schedule_done=True,
            handler_data=MagicMock(),
        ),
        recover_point=MagicMock(),
    )


@pytest.fixture
def call_interrupter():
    runtime = MagicMock()
    runtime.interrupt_errors = MagicMock(return_value=(ValueError,))
    return ExecuteInterrupter(
        runtime=runtime,
        current_node_id="node1",
        process_id=1,
        parent_pipeline_id="parent",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(name="s1"),
        recover_point=None,
    )


def test_to_node(interrupter):
    interrupter.to_node("node2")
    assert interrupter.current_node_id == "node2"
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version is None
    assert interrupter.check_point.execute_result is None
    assert interrupter.check_point.set_schedule_done is False
    assert isinstance(interrupter.check_point.handler_data, HandlerExecuteData)
    assert interrupter.recover_point is None


def test_call(call_interrupter):
    try:
        with call_interrupter():
            raise Exception
    except Exception:
        call_interrupter.runtime.execute.assert_not_called()
    else:
        assert False

    try:
        with call_interrupter():
            raise ValueError()
    except InterruptException:
        call_interrupter.runtime.execute.assert_called_once_with(
            process_id=call_interrupter.process_id,
            node_id=call_interrupter.current_node_id,
            root_pipeline_id=call_interrupter.root_pipeline_id,
            parent_pipeline_id=call_interrupter.parent_pipeline_id,
            recover_point=call_interrupter.latest_recover_point,
        )
        call_interrupter.runtime.handle_execute_interrupt_event.assert_called_once()
    else:
        assert False
