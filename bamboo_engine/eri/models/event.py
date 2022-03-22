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
