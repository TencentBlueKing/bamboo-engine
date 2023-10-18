# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import mock
import pytest
from mock import MagicMock, call

from bamboo_engine import states
from bamboo_engine.engine import Engine
from bamboo_engine.eri import (
    DispatchProcess,
    ExecutionData,
    NodeType,
    ProcessInfo,
    Schedule,
    ScheduleType,
    ServiceActivity,
    State,
)
from bamboo_engine.handler import ExecuteResult
from bamboo_engine.interrupt import (
    ExecuteInterrupter,
    ExecuteInterruptPoint,
    ExecuteKeyPoint,
)


@pytest.fixture
def node_id():
    return "nid"


@pytest.fixture
def pi():
    return ProcessInfo(
        process_id="pid",
        destination_id="d",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="parent",
    )


@pytest.fixture
def interrupter():
    return ExecuteInterrupter(
        runtime=MagicMock(),
        current_node_id="node1",
        process_id=1,
        parent_pipeline_id="parent",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(name="s1"),
        recover_point=None,
        headers={},
    )


@pytest.fixture
def state(node_id):
    return State(
        node_id=node_id,
        root_id="root",
        parent_id="root",
        name=states.FINISHED,
        version="v",
        loop=1,
        inner_loop=1,
        retry=0,
        skip=False,
        error_ignored=False,
        created_time=None,
        started_time=None,
        archived_time=None,
    )


@pytest.fixture
def node(node_id):
    return ServiceActivity(
        id=node_id,
        type=NodeType.ServiceActivity,
        target_flows=["f1"],
        target_nodes=["t1"],
        targets={"f1": "t1"},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        code="",
        version="",
        reserve_rollback=True,
        error_ignorable=False,
    )


@pytest.fixture
def schedule(node_id, pi, state):
    return Schedule(
        id=2,
        type=ScheduleType.POLL,
        process_id=pi.process_id,
        node_id=node_id,
        finished=False,
        expired=False,
        version=state.version,
        times=0,
    )


@pytest.fixture
def recover_point():
    return ExecuteInterruptPoint(name=ExecuteKeyPoint.SET_NODE_RUNNING_PRE_CHECK_DONE, version=2)


def test_execute__reach_destination_and_wake_up_failed(node_id, pi, interrupter):
    pi.destination_id = node_id

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.child_process_finish = MagicMock(return_value=False)

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.wake_up.assert_called_once_with(pi.process_id)
    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.child_process_finish.assert_called_once_with(pi.parent_id, pi.process_id)
    runtime.execute.assert_not_called()

    assert interrupter.check_point.name == ExecuteKeyPoint.START_PUSH_NODE


def test_execute__reach_destination_and_wake_up_success(node_id, pi, interrupter):
    pi.destination_id = node_id

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.child_process_finish = MagicMock(return_value=True)

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {"k": "v"})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.wake_up.assert_called_once_with(pi.process_id)
    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.child_process_finish.assert_called_once_with(pi.parent_id, pi.process_id)
    runtime.execute.assert_called_once_with(
        process_id=pi.parent_id,
        node_id=pi.destination_id,
        root_pipeline_id="root",
        parent_pipeline_id="root",
        headers={"k": "v"},
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.START_PUSH_NODE


def test_execute__root_pipeline_revoked(node_id, pi, interrupter):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.REVOKED})

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.die.assert_called_once_with(pi.process_id)

    assert interrupter.check_point.name == ExecuteKeyPoint.START_PUSH_NODE


def test_execute__root_pipeline_suspended(node_id, pi, interrupter):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.SUSPENDED})

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.suspend.assert_called_once_with(pi.process_id, pi.root_pipeline_id)

    assert interrupter.check_point.name == ExecuteKeyPoint.START_PUSH_NODE


def test_execute__suspended_in_pipeline_stack(node_id, pi, interrupter):
    pi.pipeline_stack = ["root", "s1", "s2"]

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(
        return_value={
            "root": states.RUNNING,
            "s1": states.SUSPENDED,
            "s2": states.SUSPENDED,
        }
    )

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.suspend.assert_called_once_with(pi.process_id, pi.pipeline_stack[1])

    assert interrupter.check_point.name == ExecuteKeyPoint.START_PUSH_NODE


def test_execute__exceed_rerun_limit(node_id, pi, interrupter, node, state):
    state.loop = 11
    state.inner_loop = 11

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.node_rerun_limit = MagicMock(return_value=10)
    runtime.get_execution_data_outputs = MagicMock(return_value={})

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_called_once_with(pi.root_pipeline_id, node_id)
    runtime.set_execution_data_outputs.assert_called_once_with(
        node_id, {"ex_data": "node execution exceed rerun limit 10"}
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id, version="v", to_state=states.FAILED, set_archive_time=True, ignore_boring_set=False
    )
    runtime.sleep.assert_called_once_with(pi.process_id)

    assert interrupter.check_point.name == ExecuteKeyPoint.SET_NODE_RUNNING_PRE_CHECK_DONE
    assert interrupter.check_point.state_already_exist is True


def test_execute__node_has_suspended_appoint(node_id, pi, interrupter, node, state):
    state.name = states.SUSPENDED

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.node_rerun_limit = MagicMock(return_value=10)

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})
    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_called_once_with(pi.root_pipeline_id, node_id)
    runtime.set_state_root_and_parent.assert_called_once_with(
        node_id=node_id, root_id=pi.root_pipeline_id, parent_id=pi.top_pipeline_id
    )
    runtime.suspend.assert_called_once_with(pi.process_id, node_id)

    assert interrupter.check_point.name == ExecuteKeyPoint.SET_NODE_RUNNING_PRE_CHECK_DONE
    assert interrupter.check_point.state_already_exist is True


def test_execute__node_can_not_transit_to_running(node_id, pi, interrupter, node, state):
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.node_rerun_limit = MagicMock(return_value=10)

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_called_once_with(pi.root_pipeline_id, node_id)
    runtime.set_state.assert_not_called()
    runtime.sleep.assert_called_once_with(pi.process_id)

    assert interrupter.check_point.name == ExecuteKeyPoint.SET_NODE_RUNNING_PRE_CHECK_DONE
    assert interrupter.check_point.state_already_exist is True


def test_execute__rerun_and_have_to_sleep(node_id, pi, interrupter, node, state):
    execution_data = ExecutionData(inputs={"1": "1"}, outputs={"2": "2"})

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.node_rerun_limit = MagicMock(return_value=10)
    runtime.get_execution_data = MagicMock(return_value=execution_data)
    runtime.set_state = MagicMock(return_value=state.version)

    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=[],
            next_node_id=None,
            should_die=False,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_called_once_with(pi.root_pipeline_id, node_id)
    runtime.get_execution_data.assert_called_once_with(node.id)
    runtime.add_history.assert_called_once_with(
        node_id=node.id,
        started_time=state.started_time,
        archived_time=state.archived_time,
        loop=state.loop,
        skip=state.skip,
        retry=state.retry,
        version=state.version,
        inputs=execution_data.inputs,
        outputs=execution_data.outputs,
    )
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=state.loop + 1,
        inner_loop=state.inner_loop + 1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=True,
        reset_retry=True,
        reset_error_ignored=True,
        refresh_version=True,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop + 1,
        inner_loop=state.loop + 1,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is True
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None


def test_execute__have_to_sleep(node_id, pi, interrupter, node, state):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_state = MagicMock(return_value=state.version)
    runtime.node_enter = MagicMock(return_value=None)

    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=[],
            next_node_id=None,
            should_die=False,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None


def test_execute__poll_schedule_ready(node_id, pi, interrupter, node, state, schedule):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_schedule = MagicMock(return_value=schedule)
    runtime.set_state = MagicMock(return_value=state.version)
    runtime.node_enter = MagicMock(return_value=None)

    handler = MagicMock()
    execute_result = ExecuteResult(
        should_sleep=True,
        schedule_ready=True,
        schedule_type=ScheduleType.POLL,
        schedule_after=5,
        dispatch_processes=[],
        next_node_id=None,
        should_die=False,
    )
    handler.execute = MagicMock(return_value=execute_result)
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {"k": "v"})

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_called_once_with(
        process_id=pi.process_id,
        node_id=node.id,
        version=state.version,
        schedule_type=execute_result.schedule_type,
    )
    runtime.schedule.assert_called_once_with(
        process_id=pi.process_id, node_id=node.id, schedule_id=schedule.id, headers={"k": "v"}
    )
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_DONE_SET_SCHEDULE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None
    assert interrupter.check_point.set_schedule_done is True


def test_execute__callback_schedule_ready(node_id, pi, interrupter, node, state, schedule):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_schedule = MagicMock(return_value=schedule)
    runtime.set_state = MagicMock(return_value=state.version)

    handler = MagicMock()
    execute_result = ExecuteResult(
        should_sleep=True,
        schedule_ready=True,
        schedule_type=ScheduleType.CALLBACK,
        schedule_after=5,
        dispatch_processes=[],
        next_node_id=None,
        should_die=False,
    )
    handler.execute = MagicMock(return_value=execute_result)
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_called_once_with(
        process_id=pi.process_id,
        node_id=node.id,
        version=state.version,
        schedule_type=execute_result.schedule_type,
    )
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_DONE_SET_SCHEDULE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None
    assert interrupter.check_point.set_schedule_done is True


def test_execute__multi_callback_schedule_ready(node_id, pi, interrupter, node, state, schedule):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_schedule = MagicMock(return_value=schedule)
    runtime.set_state = MagicMock(return_value=state.version)

    handler = MagicMock()
    execute_result = ExecuteResult(
        should_sleep=True,
        schedule_ready=True,
        schedule_type=ScheduleType.MULTIPLE_CALLBACK,
        schedule_after=5,
        dispatch_processes=[],
        next_node_id=None,
        should_die=False,
    )
    handler.execute = MagicMock(return_value=execute_result)
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_called_once_with(
        process_id=pi.process_id,
        node_id=node.id,
        version=state.version,
        schedule_type=execute_result.schedule_type,
    )
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_DONE_SET_SCHEDULE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None
    assert interrupter.check_point.set_schedule_done is True


def test_execute__has_dispatch_processes(node_id, pi, interrupter, node, state):
    dispatch_processes = [
        DispatchProcess(process_id=3, node_id="n3"),
        DispatchProcess(process_id=4, node_id="n4"),
    ]

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_state = MagicMock(return_value=state.version)

    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=dispatch_processes,
            next_node_id=None,
            should_die=False,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {"k": "v"})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.join.assert_called_once_with(pi.process_id, [d.process_id for d in dispatch_processes])
    runtime.execute.assert_has_calls(
        [
            call(
                process_id=dispatch_processes[0].process_id,
                node_id=dispatch_processes[0].node_id,
                root_pipeline_id="root",
                parent_pipeline_id="root",
                headers={"k": "v"},
            ),
            call(
                process_id=dispatch_processes[1].process_id,
                node_id=dispatch_processes[1].node_id,
                root_pipeline_id="root",
                parent_pipeline_id="root",
                headers={"k": "v"},
            ),
        ]
    )
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None


def test_execute__have_to_die(node_id, pi, interrupter, node, state):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_state = MagicMock(return_value=state.version)

    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=False,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=[],
            next_node_id=None,
            should_die=True,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.sleep.assert_not_called()
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_called_once_with(pi.process_id)

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None


def test_execute__has_reversed_rollback_plan(node_id, pi, interrupter, node, state):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_config = MagicMock(return_value=True)
    runtime.start_rollback = MagicMock(return_value=True)
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.get_state = MagicMock(return_value=state)
    runtime.set_state = MagicMock(return_value=state.version)
    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=False,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=[],
            next_node_id=None,
            should_die=True,
        )
    )

    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.set_state.assert_called_once_with(
        node_id=node.id,
        to_state=states.RUNNING,
        version=None,
        loop=1,
        inner_loop=1,
        root_id=pi.root_pipeline_id,
        parent_id=pi.top_pipeline_id,
        set_started_time=True,
        reset_skip=False,
        reset_retry=False,
        reset_error_ignored=False,
        refresh_version=False,
        ignore_boring_set=False,
    )
    runtime.start_rollback.assert_called_once_with(pi.root_pipeline_id, node_id)
    runtime.sleep.assert_not_called()
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_called_once_with(pi.process_id)

    get_handler.assert_called_once_with(node, runtime, interrupter)

    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None


def test_execute__recover_with_state_not_exsit(node_id, pi, interrupter, node, state, recover_point):
    recover_point.state_already_exist = False
    recover_point.running_node_version = "set_running_return_version"
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.set_state = MagicMock()

    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=[],
            next_node_id=None,
            should_die=False,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.get_execution_data.assert_not_called()
    runtime.add_history.assert_not_called()
    runtime.set_state.assert_not_called()
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=recover_point.running_node_version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == recover_point.running_node_version
    assert interrupter.check_point.execute_result is not None


def test_execute__recover_with_state_not_exsit_and_version_is_none(
    node_id, pi, interrupter, node, state, recover_point
):
    recover_point.state_already_exist = False
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.set_state = MagicMock()

    handler = MagicMock()
    handler.execute = MagicMock(
        return_value=ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=[],
            next_node_id=None,
            should_die=False,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.get_execution_data.assert_not_called()
    runtime.add_history.assert_not_called()
    runtime.set_state.assert_not_called()
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_called_once_with(node, runtime, interrupter)
    handler.execute.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.loop,
        version=state.version,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == "v"
    assert interrupter.check_point.execute_result is not None


def test_execute__recover_exceed_rerun_limit(node_id, pi, interrupter, node, state, recover_point):
    recover_point.state_already_exist = True
    interrupter.recover_point = recover_point
    state.loop = 11
    state.inner_loop = 11

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.node_rerun_limit = MagicMock(return_value=10)
    runtime.get_execution_data_outputs = MagicMock(return_value={})

    engine = Engine(runtime=runtime)
    engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_called_once_with(pi.root_pipeline_id, node_id)
    runtime.set_execution_data_outputs.assert_called_once_with(
        node_id, {"ex_data": "node execution exceed rerun limit 10"}
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id, version="v", to_state=states.FAILED, set_archive_time=True, ignore_boring_set=True
    )
    runtime.sleep.assert_called_once_with(pi.process_id)

    assert interrupter.check_point.name == ExecuteKeyPoint.SET_NODE_RUNNING_PRE_CHECK_DONE
    assert interrupter.check_point.state_already_exist is True


def test_execute__recover_with_execute_result(node_id, pi, interrupter, node, state, recover_point):
    recover_point.state_already_exist = False
    recover_point.running_node_version = "set_running_return_version"
    recover_point.execute_result = ExecuteResult(
        should_sleep=True,
        schedule_ready=False,
        schedule_type=None,
        schedule_after=-1,
        dispatch_processes=[],
        next_node_id=None,
        should_die=False,
    )
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.set_state = MagicMock()

    get_handler = MagicMock()

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.get_execution_data.assert_not_called()
    runtime.add_history.assert_not_called()
    runtime.set_state.assert_not_called()
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_not_called()
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_not_called()

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_NODE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == recover_point.running_node_version
    assert interrupter.check_point.execute_result is not None


def test_execute__recover_with_set_schedule_done(node_id, pi, interrupter, node, state, recover_point):
    recover_point.state_already_exist = False
    recover_point.running_node_version = "set_running_return_version"
    recover_point.execute_result = ExecuteResult(
        should_sleep=True,
        schedule_ready=True,
        schedule_type=ScheduleType.POLL,
        schedule_after=-1,
        dispatch_processes=[],
        next_node_id=None,
        should_die=False,
    )
    recover_point.set_schedule_done = True
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(return_value=state)
    runtime.set_state = MagicMock()

    get_handler = MagicMock()

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.execute(pi.process_id, node_id, pi.root_pipeline_id, pi.top_pipeline_id, interrupter, {})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state_or_none.assert_called_once_with(node_id)
    runtime.node_rerun_limit.assert_not_called()
    runtime.get_execution_data.assert_not_called()
    runtime.add_history.assert_not_called()
    runtime.set_state.assert_not_called()
    runtime.sleep.assert_called_once_with(pi.process_id)
    runtime.set_schedule.assert_called_once_with(
        process_id=pi.process_id,
        node_id=node_id,
        version=recover_point.running_node_version,
        schedule_type=ScheduleType.POLL,
    )
    runtime.schedule.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.die.assert_not_called()

    get_handler.assert_not_called()

    assert interrupter.check_point.name == ExecuteKeyPoint.EXECUTE_DONE_SET_SCHEDULE_DONE
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.running_node_version == recover_point.running_node_version
    assert interrupter.check_point.execute_result is not None
