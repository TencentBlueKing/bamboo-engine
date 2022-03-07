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

import json

from typing import List, Optional

from .runtime import DispatchProcess
from .handler import ExecuteResult, ScheduleResult


class InterruptPoint:
    def __init__(
        self,
        name: str,
        version: int = 0,
    ):
        self.name = name
        self.version = version


class HandlerExecuteData:
    def __init__(
        self,
        dispatch_processes: Optional[List[DispatchProcess]] = None,
        end_event_executed: bool = False,
        end_event_execute_fail: bool = False,
        end_event_execute_ex_data: str = "",
        service_executed: bool = False,
        service_execute_fail: bool = False,
        execute_serialize_outputs: str = "{}",
        execute_outputs_serializer: str = "",
        pipeline_stack_setted: bool = False,
    ):
        self.dispatch_processes = dispatch_processes or []
        self.end_event_executed = end_event_executed
        self.end_event_execute_fail = end_event_execute_fail
        self.end_event_execute_ex_data = end_event_execute_ex_data
        self.service_executed = service_executed
        self.service_execute_fail = service_execute_fail
        self.execute_serialize_outputs = execute_serialize_outputs
        self.execute_outputs_serializer = execute_outputs_serializer
        self.pipeline_stack_setted = pipeline_stack_setted

    def to_dict(self) -> dict:
        return {
            "dispatch_processes": [dp.to_dict() for dp in self.dispatch_processes],
            "end_event_executed": self.end_event_executed,
            "end_event_execute_fail": self.end_event_execute_fail,
            "end_event_execute_ex_data": self.end_event_execute_ex_data,
            "service_executed": self.service_executed,
            "service_execute_fail": self.service_execute_fail,
            "execute_serialize_outputs": self.execute_serialize_outputs,
            "execute_outputs_serializer": self.execute_outputs_serializer,
            "pipeline_stack_setted": self.pipeline_stack_setted,
        }

    @classmethod
    def from_dict(cls, obj: dict):
        return cls(
            dispatch_processes=[DispatchProcess.from_dict(dp_obj) for dp_obj in obj["dispatch_processes"]],
            end_event_executed=obj["end_event_executed"],
            end_event_execute_fail=obj["end_event_execute_fail"],
            end_event_execute_ex_data=obj["end_event_execute_ex_data"],
            service_executed=obj["service_executed"],
            service_execute_fail=obj["service_execute_fail"],
            execute_serialize_outputs=obj["execute_serialize_outputs"],
            execute_outputs_serializer=obj["execute_outputs_serializer"],
            pipeline_stack_setted=obj["pipeline_stack_setted"],
        )


class ExecuteInterruptPoint(InterruptPoint):
    def __init__(
        self,
        name: str,
        version: int = 0,
        state_already_exist: bool = False,
        running_node_version: Optional[str] = None,
        execute_result: Optional[ExecuteResult] = None,
        set_schedule_done: bool = False,
        handler_data: Optional[HandlerExecuteData] = None,
    ) -> None:
        super().__init__(name=name, version=version)
        self.state_already_exist = state_already_exist
        self.running_node_version = running_node_version
        self.execute_result = execute_result
        self.set_schedule_done = set_schedule_done
        self.handler_data = handler_data or HandlerExecuteData()

    @classmethod
    def from_json(cls, json_obj: Optional[str]):
        if not json_obj:
            return None

        obj = json.loads(json_obj)
        if not obj:
            return None

        return cls(
            name=obj["name"],
            version=obj["version"],
            state_already_exist=obj["state_already_exist"],
            running_node_version=obj["running_node_version"],
            execute_result=ExecuteResult.from_dict(obj["execute_result"]) if obj["execute_result"] else None,
            set_schedule_done=obj["set_schedule_done"],
            handler_data=HandlerExecuteData.from_dict(obj["handler_data"]) if obj["handler_data"] else None,
        )

    def to_json(self) -> str:
        execute_result = self.execute_result.to_dict() if self.execute_result else None
        handler_data = self.handler_data.to_dict() if self.handler_data else None
        obj = {
            "name": self.name,
            "version": self.version,
            "state_already_exist": self.state_already_exist,
            "running_node_version": self.running_node_version,
            "execute_result": execute_result,
            "set_schedule_done": self.set_schedule_done,
            "handler_data": handler_data,
        }
        return json.dumps(obj)


class HandlerScheduleData:
    def __init__(
        self,
        service_scheduled: bool = False,
        service_schedule_fail: bool = False,
        is_schedule_done: bool = False,
        schedule_times_added: bool = False,
        schedule_serialize_outputs: str = "{}",
        schedule_outputs_serializer: str = "",
    ) -> None:
        self.service_scheduled = service_scheduled
        self.service_schedule_fail = service_schedule_fail
        self.is_schedule_done = is_schedule_done
        self.schedule_times_added = schedule_times_added
        self.schedule_serialize_outputs = schedule_serialize_outputs
        self.schedule_outputs_serializer = schedule_outputs_serializer

    def to_dict(self) -> dict:
        return {
            "service_scheduled": self.service_scheduled,
            "service_schedule_fail": self.service_schedule_fail,
            "is_schedule_done": self.is_schedule_done,
            "schedule_times_added": self.schedule_times_added,
            "schedule_serialize_outputs": self.schedule_serialize_outputs,
            "schedule_outputs_serializer": self.schedule_outputs_serializer,
        }

    @classmethod
    def from_dict(cls, obj: dict):
        return cls(
            service_scheduled=obj["service_scheduled"],
            service_schedule_fail=obj["service_schedule_fail"],
            is_schedule_done=obj["is_schedule_done"],
            schedule_times_added=obj["schedule_times_added"],
            schedule_serialize_outputs=obj["schedule_serialize_outputs"],
            schedule_outputs_serializer=obj["schedule_outputs_serializer"],
        )


class ScheduleInterruptPoint(InterruptPoint):
    def __init__(
        self,
        name: str,
        version: int = 0,
        version_mismatch: Optional[bool] = None,
        node_not_running: Optional[bool] = None,
        lock_get: Optional[bool] = None,
        schedule_result: Optional[ScheduleResult] = None,
        lock_released: bool = False,
        handler_data: Optional[HandlerScheduleData] = None,
    ) -> None:
        super().__init__(name=name, version=version)
        self.version_mismatch = version_mismatch
        self.node_not_running = node_not_running
        self.lock_get = lock_get
        self.schedule_result = schedule_result
        self.lock_released = lock_released
        self.handler_data = handler_data or HandlerScheduleData()

    @classmethod
    def from_json(cls, json_obj: Optional[str]):
        if not json_obj:
            return None

        obj = json.loads(json_obj)
        if not obj:
            return None

        return cls(
            name=obj["name"],
            version=obj["version"],
            version_mismatch=obj["version_mismatch"],
            node_not_running=obj["node_not_running"],
            lock_get=obj["lock_get"],
            schedule_result=ScheduleResult.from_dict(obj["schedule_result"]) if obj["schedule_result"] else None,
            lock_released=obj["lock_released"],
            handler_data=HandlerScheduleData.from_dict(obj["handler_data"]) if obj["handler_data"] else None,
        )

    def to_json(self) -> str:
        schedule_result = self.schedule_result.to_dict() if self.schedule_result else None
        handler_data = self.handler_data.to_dict() if self.handler_data else None
        obj = {
            "name": self.name,
            "version": self.version,
            "version_mismatch": self.version_mismatch,
            "node_not_running": self.node_not_running,
            "lock_get": self.lock_get,
            "schedule_result": schedule_result,
            "lock_released": self.lock_released,
            "handler_data": handler_data,
        }
        return json.dumps(obj)
