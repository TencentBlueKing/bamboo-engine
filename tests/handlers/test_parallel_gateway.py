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

from dis import dis
import pytest
from mock import MagicMock

from bamboo_engine import states
from bamboo_engine.eri.models.interrupt import HandlerExecuteData
from bamboo_engine.interrupt import ExecuteInterrupter, ExecuteKeyPoint
from bamboo_engine.eri import ProcessInfo, NodeType, ParallelGateway, ExecuteInterruptPoint
from bamboo_engine.handlers.parallel_gateway import (
    ParallelGatewayHandler,
)


@pytest.mark.parametrize(
    "recover_point",
    [
        pytest.param(ExecuteInterruptPoint("n"), id="recover_is_not_none"),
        pytest.param(
            ExecuteInterruptPoint("n", handler_data=HandlerExecuteData(dispatch_processes=["p1", "p2"])),
            id="recover_is_not_none",
        ),
        pytest.param(None, id="recover_is_none"),
    ],
)
def test_parallel_gateway_handler__execute_success(recover_point):
    pi = ProcessInfo(
        process_id="pid",
        destination_id="",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="parent",
    )

    node = ParallelGateway(
        id="nid",
        type=NodeType.ParallelGateway,
        target_flows=["f1", "f2", "f3"],
        target_nodes=["t1", "t2", "t3"],
        targets={"f1": "t1", "f2": "t2", "f3": "t3"},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        can_skip=True,
        converge_gateway_id="cg",
    )

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

    dispatch_processes = ["p1", "p2", "p3"]

    runtime = MagicMock()
    runtime.fork = MagicMock(return_value=dispatch_processes)

    handler = ParallelGatewayHandler(node, runtime, interrupter)
    result = handler.execute(pi, 1, 1, "v1", recover_point)

    assert result.should_sleep == True
    assert result.schedule_ready == False
    assert result.schedule_type == None
    assert result.schedule_after == -1
    if recover_point and recover_point.handler_data.dispatch_processes:
        assert result.dispatch_processes == recover_point.handler_data.dispatch_processes
    else:
        assert result.dispatch_processes == dispatch_processes
    assert result.next_node_id == None
    assert result.should_die == False

    if recover_point and recover_point.handler_data.dispatch_processes:
        runtime.fork.assert_not_called()
    else:
        runtime.fork.assert_called_once_with(
            parent_id=pi.process_id,
            root_pipeline_id=pi.root_pipeline_id,
            pipeline_stack=pi.pipeline_stack,
            from_to={
                "t1": "cg",
                "t2": "cg",
                "t3": "cg",
            },
        )

    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        version="v1",
        to_state=states.FINISHED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.PG_PROCESS_FORK_DONE
