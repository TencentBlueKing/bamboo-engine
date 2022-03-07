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

from typing import List, Optional

from .runtime import ScheduleType, DispatchProcess


class ExecuteResult:
    """
    Handler execute 方法返回的结果
    """

    def __init__(
        self,
        should_sleep: bool,
        schedule_ready: bool,
        schedule_type: Optional[ScheduleType],
        schedule_after: int,
        dispatch_processes: List[DispatchProcess],
        next_node_id: Optional[str],
        should_die: bool = False,
    ):
        """

        :param should_sleep: 当前进程是否应该进入休眠
        :type should_sleep: bool
        :param schedule_ready: 被处理的节点是否准备好进入调度
        :type schedule_ready: bool
        :param schedule_type: 被处理的节点的调度类型
        :type schedule_type: Optional[ScheduleType]
        :param schedule_after: 在 schedule_after 秒后开始执行调度
        :type schedule_after: int
        :param dispatch_processes: 需要派发的子进程信息列表
        :type dispatch_processes: List[DispatchProcess]
        :param next_node_id: 推进循环中下一个要处理的节点的 ID
        :type next_node_id: Optional[str]
        :param should_die: 当前进程是否需要进入死亡状态, defaults to False
        :type should_die: bool, optional
        """
        self.should_sleep = should_sleep
        self.schedule_ready = schedule_ready
        self.schedule_type = schedule_type
        self.schedule_after = schedule_after
        self.dispatch_processes = dispatch_processes
        self.next_node_id = next_node_id
        self.should_die = should_die

    def to_dict(self) -> dict:
        return {
            "should_sleep": self.should_sleep,
            "schedule_ready": self.schedule_ready,
            "schedule_type": self.schedule_type.value if self.schedule_type else None,
            "schedule_after": self.schedule_after,
            "dispatch_processes": [dp.to_dict() for dp in self.dispatch_processes],
            "next_node_id": self.next_node_id,
            "should_die": self.should_die,
        }

    @classmethod
    def from_dict(cls, obj: dict):
        schedule_type = ScheduleType(obj["schedule_type"]) if obj["schedule_type"] else None
        return cls(
            should_sleep=obj["should_sleep"],
            schedule_ready=obj["schedule_ready"],
            schedule_type=schedule_type,
            schedule_after=obj["schedule_after"],
            dispatch_processes=[DispatchProcess.from_dict(dp_obj) for dp_obj in obj["dispatch_processes"]],
            next_node_id=obj["next_node_id"],
            should_die=obj["should_die"],
        )


class ScheduleResult:
    """
    Handler schedule 方法返回的结果
    """

    def __init__(
        self,
        has_next_schedule: bool,
        schedule_after: int,
        schedule_done: bool,
        next_node_id: Optional[str],
    ):
        """

        :param has_next_schedule: 是否还有下次调度
        :type has_next_schedule: bool
        :param schedule_after: 在 schedule_after 秒后开始下次调度
        :type schedule_after: int
        :param schedule_done: 调度是否完成
        :type schedule_done: bool
        :param next_node_id: 调度完成后下一个需要执行的节点的 ID
        :type next_node_id: Optional[str]
        """
        self.has_next_schedule = has_next_schedule
        self.schedule_after = schedule_after
        self.schedule_done = schedule_done
        self.next_node_id = next_node_id

    def to_dict(self) -> dict:
        return {
            "has_next_schedule": self.has_next_schedule,
            "schedule_after": self.schedule_after,
            "schedule_done": self.schedule_done,
            "next_node_id": self.next_node_id,
        }

    @classmethod
    def from_dict(cls, obj: dict):
        return cls(
            has_next_schedule=obj["has_next_schedule"],
            schedule_after=obj["schedule_after"],
            schedule_done=obj["schedule_done"],
            next_node_id=obj["next_node_id"],
        )
