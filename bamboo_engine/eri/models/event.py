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
from enum import Enum


class HookType(Enum):
    # 节点继续操作前
    PRE_RESUME_NODE = "pre_resume_node"
    # 节点继续操作后
    POST_RESUME_NODE = "post_resume_node"
    # 节点暂停操作前
    PRE_PAUSE_NODE = "pre_pause_node"
    # 节点暂停操作后
    POST_PAUSE_NODE = "post_pause_node"
    # 节点重试操作前
    PRE_RETRY_NODE = "pre_retry_node"
    # 节点重试操作后
    POST_RETRY_NODE = "post_retry_node"
    # 节点跳过操作前
    PRE_SKIP_NODE = "pre_skip_node"
    # 节点跳过操作后
    POST_SKIP_NODE = "post_skip_node"
    # 节点强制失败操作前
    PRE_FORCED_FAIL_ACTIVITY = "pre_forced_fail_activity"
    # 节点强制失败操作后
    POST_FORCED_FAIL_ACTIVITY = "post_forced_fail_activity"
    # 节点回调前
    PRE_CALLBACK = "pre_callback"
    # 节点回调后
    POST_CALLBACK = "post_callback"
    # 节点 execute 失败后
    NODE_EXECUTE_FAIL = "node_execute_fail"
    # 节点调度失败后
    NODE_SCHEDULE_FAIL = "node_schedule_fail"
    # 节点 execute 异常后
    NODE_EXECUTE_EXCEPTION = "node_execute_exception"
    # 节点调度异常后
    NODE_SCHEDULE_EXCEPTION = "node_schedule_exception"
    # 节点 execute 前
    NODE_ENTER = "node_enter"
    # 节点执行结束
    NODE_FINISH = "node_finish"
    # 节点 execute
    EXECUTE = "execute"
    # 节点 schedule
    SCHEDULE = "schedule"


class InterruptEvent:
    def __init__(
        self, name: str, process_id: int, node_id: int, exception: Exception, exception_traceback: str
    ) -> None:
        """

        :param name: 事件名称
        :param process_id: 进程 ID
        :param node_id: 节点 ID
        :param exception 导致中断的异常
        :param exception_traceback 导致中断的异常堆栈
        """
        self.name = name
        self.process_id = process_id
        self.node_id = node_id
        self.exception = exception
        self.exception_traceback = exception_traceback


class ExecuteInterruptEvent(InterruptEvent):
    """
    执行中断事件
    """


class ScheduleInterruptEvent(InterruptEvent):
    """
    调度中断事件
    """
