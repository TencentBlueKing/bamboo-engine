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

from bamboo_engine.eri.models import DispatchProcess, ScheduleType
from bamboo_engine.eri.models.handler import ExecuteResult
from bamboo_engine.eri.models.interrupt import ExecuteInterruptPoint, HandlerExecuteData


def test_to_json():
    point = ExecuteInterruptPoint(
        name="n1",
        version=1,
        state_already_exist=True,
        execute_result=ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=ScheduleType.POLL,
            schedule_after=2,
            dispatch_processes=[DispatchProcess(process_id=1, node_id="1"), DispatchProcess(process_id=2, node_id="2")],
            next_node_id=None,
            should_die=False,
        ),
        set_schedule_done=False,
        handler_data=HandlerExecuteData(
            dispatch_processes=[DispatchProcess(process_id=1, node_id="1"), DispatchProcess(process_id=2, node_id="2")],
            end_event_executed=False,
            end_event_execute_fail=False,
            end_event_execute_ex_data="",
            service_executed=True,
            service_execute_fail=True,
            execute_serialize_outputs="{}",
            execute_outputs_serializer="json",
            pipeline_stack_setted=True,
        ),
    )
    assert (
        point.to_json()
        == '{"name": "n1", "version": 1, "state_already_exist": true, "running_node_version": null, "execute_result": {"should_sleep": true, "schedule_ready": false, "schedule_type": 3, "schedule_after": 2, "dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}], "next_node_id": null, "should_die": false}, "set_schedule_done": false, "handler_data": {"dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}], "end_event_executed": false, "end_event_execute_fail": false, "end_event_execute_ex_data": "", "service_executed": true, "service_execute_fail": true, "execute_serialize_outputs": "{}", "execute_outputs_serializer": "json", "pipeline_stack_setted": true}}'
    )  # noqa


def test_from_json():
    point = ExecuteInterruptPoint.from_json(
        '{"name": "n1", "version": 1, "state_already_exist": true, "running_node_version": null, "execute_result": {"should_sleep": true, "schedule_ready": false, "schedule_type": 3, "schedule_after": 2, "dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}], "next_node_id": null, "should_die": false}, "set_schedule_done": false, "handler_data": {"dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}], "end_event_executed": false, "end_event_execute_fail": false, "end_event_execute_ex_data": "", "service_executed": true, "service_execute_fail": true, "execute_serialize_outputs": "{}", "execute_outputs_serializer": "json", "pipeline_stack_setted": true}}'  # noq
    )

    assert ExecuteInterruptPoint.from_json(None) is None
    assert ExecuteInterruptPoint.from_json("null") is None

    assert point.execute_result.should_sleep is True
    assert point.execute_result.schedule_ready is False
    assert point.execute_result.schedule_type == ScheduleType.POLL
    assert point.execute_result.schedule_after == 2
    assert point.execute_result.dispatch_processes[0].process_id == 1
    assert point.execute_result.dispatch_processes[0].node_id == "1"
    assert point.execute_result.dispatch_processes[1].process_id == 2
    assert point.execute_result.dispatch_processes[1].node_id == "2"
    assert point.execute_result.next_node_id is None
    assert point.execute_result.should_die is False
    assert point.handler_data.dispatch_processes[0].process_id == 1
    assert point.handler_data.dispatch_processes[0].node_id == "1"
    assert point.handler_data.dispatch_processes[1].process_id == 2
    assert point.handler_data.dispatch_processes[1].node_id == "2"
    assert point.handler_data.end_event_executed is False
    assert point.handler_data.end_event_execute_fail is False
    assert point.handler_data.end_event_execute_ex_data == ""
    assert point.handler_data.service_executed is True
    assert point.handler_data.service_execute_fail is True
    assert point.handler_data.execute_serialize_outputs == "{}"
    assert point.handler_data.execute_outputs_serializer == "json"
    assert point.handler_data.pipeline_stack_setted is True
    assert point.name == "n1"
    assert point.version == 1
    assert point.state_already_exist is True
    assert point.running_node_version is None
    assert point.set_schedule_done is False
