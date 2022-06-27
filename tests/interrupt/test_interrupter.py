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

import pytest
from mock import MagicMock

from bamboo_engine.eri.models import DispatchProcess, ExecuteResult, HandlerExecuteData, ScheduleType
from bamboo_engine.eri.models.interrupt import ExecuteInterruptPoint

from bamboo_engine.interrupt import Interrupter


@pytest.fixture
def interrupter():
    return Interrupter(
        runtime=MagicMock(),
        process_id=1,
        current_node_id="node",
        check_point=ExecuteInterruptPoint(
            name="s1",
            version=1,
            state_already_exist=True,
            execute_result=ExecuteResult(
                should_sleep=True,
                schedule_ready=False,
                schedule_type=ScheduleType.POLL,
                schedule_after=2,
                dispatch_processes=[
                    DispatchProcess(process_id=1, node_id="1"),
                    DispatchProcess(process_id=2, node_id="2"),
                ],
                next_node_id=None,
                should_die=False,
            ),
            set_schedule_done=False,
            handler_data=HandlerExecuteData(
                dispatch_processes=[
                    DispatchProcess(process_id=1, node_id="1"),
                    DispatchProcess(process_id=2, node_id="2"),
                ],
                end_event_executed=False,
                end_event_execute_fail=False,
                end_event_execute_ex_data="",
                service_executed=True,
                service_execute_fail=True,
                execute_serialize_outputs="{}",
                execute_outputs_serializer="json",
                pipeline_stack_setted=True,
            ),
        ),
        recover_point=ExecuteInterruptPoint(name="s3", version=10),
        headers={},
    )


@pytest.fixture
def no_recover_point_interrupter():
    return Interrupter(
        runtime=MagicMock(),
        process_id=1,
        current_node_id="node",
        check_point=ExecuteInterruptPoint(name="s2", version=1),
        recover_point=None,
        headers={},
    )


def test_check(interrupter, no_recover_point_interrupter):
    interrupter.check("s2")
    assert interrupter.check_point.version == 2
    assert interrupter.check_point.name == "s2"

    interrupter.check("s3")
    assert interrupter.check_point.version == 10
    assert interrupter.check_point.name == "s3"

    no_recover_point_interrupter.check("s2")
    assert no_recover_point_interrupter.check_point.version == 2
    assert no_recover_point_interrupter.check_point.name == "s2"


def test_check_and_set(interrupter):
    interrupter.check_and_set(name="s1", state_already_exist=False, set_schedule_done=True)
    assert interrupter.check_point.version == 2
    assert interrupter.check_point.name == "s1"
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.set_schedule_done is True

    interrupter.check_and_set(name="s2", end_event_executed=True, end_event_execute_fail=True, from_handler=True)
    assert interrupter.check_point.version == 3
    assert interrupter.check_point.name == "s2"
    assert interrupter.check_point.handler_data.end_event_executed is True
    assert interrupter.check_point.handler_data.end_event_execute_fail is True


def test_check_and_set_and_inherite_version(interrupter):
    interrupter.check_and_set(name="s3", state_already_exist=False, set_schedule_done=True)
    assert interrupter.check_point.version == 10
    assert interrupter.check_point.name == "s3"
    assert interrupter.check_point.state_already_exist is False
    assert interrupter.check_point.set_schedule_done is True


def test_check_and_set_and_inherite_version_from_handler(interrupter):
    interrupter.check_and_set(name="s3", end_event_executed=True, end_event_execute_fail=True, from_handler=True)
    assert interrupter.check_point.version == 10
    assert interrupter.check_point.name == "s3"
    assert interrupter.check_point.handler_data.end_event_executed is True
    assert interrupter.check_point.handler_data.end_event_execute_fail is True


def test_check_point_string(no_recover_point_interrupter):
    assert (
        no_recover_point_interrupter.check_point_string
        == '[check_point: {"name": "s2", "version": 1, "state_already_exist": false, "running_node_version": null, "execute_result": null, "set_schedule_done": false, "handler_data": {"dispatch_processes": [], "end_event_executed": false, "end_event_execute_fail": false, "end_event_execute_ex_data": "", "service_executed": false, "service_execute_fail": false, "execute_serialize_outputs": "{}", "execute_outputs_serializer": "", "pipeline_stack_setted": false}}] [recover_point: None]'
    )  # noqa


def test_latest_recover_point(interrupter, no_recover_point_interrupter):
    assert interrupter.latest_recover_point is interrupter.recover_point
    interrupter.check("s3")
    assert interrupter.latest_recover_point is interrupter.check_point
    assert no_recover_point_interrupter.latest_recover_point is no_recover_point_interrupter.check_point
