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

import sched
import mock
from py import process
import pytest
from mock import MagicMock

from bamboo_engine.eri import (
    ProcessInfo,
    ServiceActivity,
    State,
    NodeType,
    ScheduleType,
    Schedule,
    CallbackData,
)
from bamboo_engine import states
from bamboo_engine.engine import Engine
from bamboo_engine.eri.models.interrupt import ScheduleInterruptPoint
from bamboo_engine.handler import ScheduleResult
from bamboo_engine.interrupt import ScheduleInterrupter, ScheduleKeyPoint


@pytest.fixture
def node_id():
    return "nid"


@pytest.fixture
def schedule_id():
    return 1


@pytest.fixture
def version():
    return "v"


@pytest.fixture
def state(version):
    return State(
        node_id=node_id,
        root_id="root",
        parent_id="root",
        name=states.RUNNING,
        version=version,
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
def pi():
    return ProcessInfo(
        process_id="pid",
        destination_id="",
        root_pipeline_id="root",
        pipeline_stack=["root"],
        parent_id="parent",
    )


@pytest.fixture
def schedule(schedule_id, version):
    return Schedule(
        id=schedule_id,
        type=ScheduleType.MULTIPLE_CALLBACK,
        process_id=1,
        node_id="nid",
        finished=False,
        expired=False,
        version=version,
        times=0,
    )


@pytest.fixture
def interrupter(pi, node_id, schedule_id):
    return ScheduleInterrupter(
        runtime=MagicMock(),
        process_id=pi.process_id,
        current_node_id=node_id,
        schedule_id=schedule_id,
        callback_data_id=None,
        check_point=ScheduleInterruptPoint(name="name"),
        recover_point=None,
        headers={},
    )


@pytest.fixture
def node():
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
        error_ignorable=False,
    )


@pytest.fixture
def recover_point():
    return ScheduleInterruptPoint(name="name")


def test_schedule__lock_get_failed(node_id, schedule_id, state, pi, schedule, interrupter):

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=False)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_schedule = MagicMock(return_value=schedule)

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule_id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_schedule.assert_called_once_with(schedule_id)
    runtime.apply_schedule_lock.assert_called_once_with(schedule_id)
    assert runtime.set_next_schedule.call_args.kwargs["process_id"] == pi.process_id
    assert runtime.set_next_schedule.call_args.kwargs["node_id"] == node_id
    assert runtime.set_next_schedule.call_args.kwargs["schedule_id"] == schedule_id
    assert runtime.set_next_schedule.call_args.kwargs["callback_data_id"] is None
    assert runtime.set_next_schedule.call_args.kwargs["schedule_after"] <= 5
    runtime.beat.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.APPLY_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is False


def test_schedule__lock_get_failed_but_not_retry(node_id, schedule_id, state, pi, schedule, interrupter):
    schedule.type = ScheduleType.CALLBACK

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=False)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_schedule = MagicMock(return_value=schedule)

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule_id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_schedule.assert_called_once_with(schedule_id)
    runtime.set_next_schedule.assert_not_called()
    runtime.beat.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.APPLY_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is False


def test_schedule__schedule_is_finished(node_id, pi, schedule, interrupter):
    schedule.finished = True

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock()

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.apply_schedule_lock.assert_not_called()
    runtime.beat.assert_not_called()


def test_schedule__schedule_version_not_match(node_id, pi, state, schedule, interrupter):
    state.version = "v2"

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.expire_schedule.assert_called_once_with(schedule.id)
    runtime.beat.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.VERSION_MISMATCH_CHECKED
    assert interrupter.check_point.version_mismatch is True


def test_schedule__schedule_node_state_is_not_running(node_id, pi, state, schedule, interrupter):
    state.name = states.FAILED

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.expire_schedule.assert_called_once_with(schedule.id)
    runtime.get_node.assert_not_called()
    runtime.beat.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.NODE_NOT_RUNNING_CHECKED
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is True


def test_schedule__has_callback_data(node_id, state, pi, version, schedule, node, interrupter):
    schedule.type = ScheduleType.POLL

    callback_data = CallbackData(id=1, node_id=node_id, version=version, data={})

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_callback_data = MagicMock(return_value=callback_data)
    runtime.get_node = MagicMock(return_value=node)

    handler = MagicMock()
    handler.schedule = MagicMock(
        return_value=ScheduleResult(
            has_next_schedule=False,
            schedule_after=-1,
            schedule_done=False,
            next_node_id=None,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.schedule(
            pi.process_id, node_id, schedule.id, interrupter, callback_data_id=callback_data.id, headers={"k": "v"}
        )

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.apply_schedule_lock.assert_called_once_with(schedule.id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_callback_data.assert_called_once_with(callback_data.id)
    handler.schedule.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.inner_loop,
        schedule=schedule,
        callback_data=callback_data,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ScheduleKeyPoint.RELEASE_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is True
    assert interrupter.check_point.schedule_result is not None
    assert interrupter.check_point.lock_released is True


def test_schedule__without_callback_data(node_id, state, pi, schedule, node, interrupter):
    schedule.type = ScheduleType.POLL

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_node = MagicMock(return_value=node)

    handler = MagicMock()
    handler.schedule = MagicMock(
        return_value=ScheduleResult(
            has_next_schedule=False,
            schedule_after=-1,
            schedule_done=False,
            next_node_id=None,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.apply_schedule_lock.assert_called_once_with(schedule.id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_callback_data.assert_not_called()
    handler.schedule.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.inner_loop,
        schedule=schedule,
        callback_data=None,
        recover_point=interrupter.recover_point,
    )

    assert interrupter.check_point.name == ScheduleKeyPoint.RELEASE_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is True
    assert interrupter.check_point.schedule_result is not None
    assert interrupter.check_point.lock_released is True


def test_schedule__has_next_schedule(node_id, state, pi, schedule, node, interrupter):
    schedule.type = ScheduleType.POLL

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_node = MagicMock(return_value=node)

    handler = MagicMock()
    handler.schedule = MagicMock(
        return_value=ScheduleResult(
            has_next_schedule=True,
            schedule_after=60,
            schedule_done=False,
            next_node_id=None,
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={"k": "v"})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.apply_schedule_lock.assert_called_once_with(schedule.id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_callback_data.assert_not_called()
    handler.schedule.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.inner_loop,
        schedule=schedule,
        callback_data=None,
        recover_point=interrupter.recover_point,
    )
    runtime.set_next_schedule.assert_called_once_with(
        process_id=pi.process_id, node_id=node_id, schedule_id=schedule.id, schedule_after=60, headers={"k": "v"}
    )
    runtime.finish_schedule.assert_not_called()
    runtime.execute.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.RELEASE_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is True
    assert interrupter.check_point.schedule_result is not None
    assert interrupter.check_point.lock_released is True


def test_schedule__schedule_done(node_id, state, pi, schedule, node, interrupter):
    schedule.type = ScheduleType.POLL

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_node = MagicMock(return_value=node)

    handler = MagicMock()
    handler.schedule = MagicMock(
        return_value=ScheduleResult(
            has_next_schedule=False,
            schedule_after=-1,
            schedule_done=True,
            next_node_id="nid2",
        )
    )
    get_handler = MagicMock(return_value=handler)

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.apply_schedule_lock.assert_called_once_with(schedule.id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_callback_data.assert_not_called()
    handler.schedule.assert_called_once_with(
        process_info=pi,
        loop=state.loop,
        inner_loop=state.inner_loop,
        schedule=schedule,
        callback_data=None,
        recover_point=interrupter.recover_point,
    )
    runtime.set_next_schedule.assert_not_called()
    runtime.finish_schedule.assert_called_once_with(schedule.id)
    runtime.execute.assert_called_once_with(
        process_id=pi.process_id, node_id="nid2", root_pipeline_id="root", parent_pipeline_id="root", headers={}
    )

    assert interrupter.check_point.name == ScheduleKeyPoint.RELEASE_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is True
    assert interrupter.check_point.schedule_result is not None
    assert interrupter.check_point.lock_released is True


def test_schedule__recover_version_mismatch(node_id, pi, state, schedule, interrupter, recover_point):
    recover_point.version_mismatch = True
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.expire_schedule.assert_called_once_with(schedule.id)
    runtime.beat.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.VERSION_MISMATCH_CHECKED
    assert interrupter.check_point.version_mismatch is True


def test_schedule__recover_not_not_running(node_id, pi, state, schedule, interrupter, recover_point):
    recover_point.node_not_running = True
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)

    engine = Engine(runtime=runtime)
    engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={})

    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.expire_schedule.assert_called_once_with(schedule.id)
    runtime.get_node.assert_not_called()
    runtime.beat.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.NODE_NOT_RUNNING_CHECKED
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is True


def test_schedule__recover_has_schedule_result(node_id, pi, node, state, schedule, interrupter, recover_point):
    recover_point.schedule_result = ScheduleResult(
        has_next_schedule=True,
        schedule_after=60,
        schedule_done=False,
        next_node_id=None,
    )
    interrupter.recover_point = recover_point

    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_node = MagicMock(return_value=node)

    get_handler = MagicMock()

    engine = Engine(runtime=runtime)

    with mock.patch(
        "bamboo_engine.engine.HandlerFactory.get_handler",
        get_handler,
    ):
        engine.schedule(pi.process_id, node_id, schedule.id, interrupter, headers={"k": "v"})

    runtime.beat.assert_called_once_with(pi.process_id)
    runtime.get_process_info.assert_called_once_with(pi.process_id)
    runtime.apply_schedule_lock.assert_called_once_with(schedule.id)
    runtime.schedule.assert_not_called()
    runtime.get_schedule.assert_called_once_with(schedule.id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_callback_data.assert_not_called()
    runtime.set_next_schedule.assert_called_once_with(
        process_id=pi.process_id, node_id=node_id, schedule_id=schedule.id, schedule_after=60, headers={"k": "v"}
    )
    runtime.finish_schedule.assert_not_called()
    runtime.execute.assert_not_called()
    get_handler.assert_not_called()

    assert interrupter.check_point.name == ScheduleKeyPoint.RELEASE_LOCK_DONE
    assert interrupter.check_point.version_mismatch is False
    assert interrupter.check_point.node_not_running is False
    assert interrupter.check_point.lock_get is True
    assert interrupter.check_point.schedule_result is not None
    assert interrupter.check_point.lock_released is True
