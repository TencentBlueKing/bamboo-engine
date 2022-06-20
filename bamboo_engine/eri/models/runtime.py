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


# ERI 中相关的模型对象

from enum import Enum
from datetime import datetime
from typing import List, Dict, Any, Optional

from bamboo_engine.utils.object import Representable
from bamboo_engine.utils.collections import FancyDict
from bamboo_engine.exceptions import ValueError


class ScheduleType(Enum):
    """
    调度类型
    """

    CALLBACK = 1
    MULTIPLE_CALLBACK = 2
    POLL = 3


class Schedule(Representable):
    """
    调度对象
    """

    def __init__(
        self,
        id: int,
        type: ScheduleType,
        process_id: int,
        node_id: str,
        finished: bool,
        expired: bool,
        version: str,
        times: int,
    ):
        """

        :param id: ID
        :type id: int
        :param type: 类型
        :type type: ScheduleType
        :param process_id: 进程 ID
        :type process_id: int
        :param node_id: 节点 ID
        :type node_id: str
        :param finished: 是否已完成
        :type finished: bool
        :param expired: 是否已过期
        :type expired: bool
        :param version: 绑定版本
        :type version: str
        :param times: 调度次数
        :type times: int
        """
        self.id = id
        self.type = type
        self.process_id = process_id
        self.node_id = node_id
        self.finished = finished
        self.expired = expired
        self.version = version
        self.times = times


class State(Representable):
    """
    节点状态对象
    """

    def __init__(
        self,
        node_id: str,
        root_id: str,
        parent_id: str,
        name: str,
        version: str,
        loop: int,
        inner_loop: int,
        retry: int,
        skip: bool,
        error_ignored: bool,
        created_time: datetime,
        started_time: datetime,
        archived_time: datetime,
    ):
        """
        :param node_id: 节点 ID
        :type node_id: str
        :param root_id: 根流程 ID
        :type root_id: str
        :param parent_id: 父流程 ID
        :type parent_id: str
        :param name: 状态名
        :type name: str
        :param version: 版本
        :type version: str
        :param loop: 重入次数
        :type loop: int
        :param inner_loop: 子流程重入次数
        :type inner_loop: int
        :param retry: 重试次数
        :type retry: int
        :param skip: 是否跳过
        :type skip: bool
        :param error_ignored: 是否出错后自动忽略
        :type error_ignored: bool
        :param started_time: 创建时间
        :type started_time: datetime
        :param started_time: 开始时间
        :type started_time: datetime
        :param archived_time: 归档时间
        :type archived_time: datetime
        """
        self.node_id = node_id
        self.root_id = root_id
        self.parent_id = parent_id
        self.name = name
        self.version = version
        self.loop = loop
        self.inner_loop = inner_loop
        self.retry = retry
        self.skip = skip
        self.error_ignored = error_ignored
        self.created_time = created_time
        self.started_time = started_time
        self.archived_time = archived_time


class DataInput(Representable):
    """
    节点数据输入项
    """

    def __init__(self, need_render: bool, value: Any):
        """
        :type is_splice: bool
        :param value: 是否需要进行模板解析
        :type value: Any
        """
        self.need_render = need_render
        self.value = value


class Data(Representable):
    """
    节点数据对象
    """

    def __init__(self, inputs: Dict[str, DataInput], outputs: Dict[str, str]):
        """

        :param inputs: 输入数据
        :type inputs: Dict[str, Any]
        :param outputs: 节点输出配置
        :type outputs: Dict[str, str]
        """
        self.inputs = inputs
        self.outputs = outputs

    def plain_inputs(self) -> Dict[str, Any]:
        """
        获取不带输入项类型的输入字典
        """
        return {key: di.value for key, di in self.inputs.items()}

    def need_render_inputs(self) -> Dict[str, Any]:
        """
        获取需要进行渲染的输入项字典
        """
        return {key: di.value for key, di in self.inputs.items() if di.need_render}

    def render_escape_inputs(self) -> Dict[str, Any]:
        """
        获取不需要进行渲染的输入项字典
        """
        return {key: di.value for key, di in self.inputs.items() if not di.need_render}


class ExecutionData(Representable):
    """
    节点执行数据
    """

    def __init__(self, inputs: Optional[dict], outputs: Optional[dict]):
        """

        :param inputs: 输入数据
        :type inputs: Optional[dict]
        :param outputs: 输出数据
        :type outputs: Optional[dict]
        """
        self.inputs = FancyDict(inputs)
        self.outputs = FancyDict(outputs)


class ExecutionHistory(Representable):
    """
    节点执行历史
    """

    def __init__(
        self,
        id: str,
        node_id: str,
        started_time: datetime,
        archived_time: datetime,
        loop: int,
        skip: bool,
        retry: int,
        version: str,
        inputs: dict,
        outputs: dict,
    ):
        """

        : param id: ID
        : type id: str
        : param node_id: Node ID
        : type node_id: str
        : param started_time: 开始时间
        : type started_time: datetime
        : param archived_time: 归档时间
        : type archived_time: datetime
        : param loop: 重入计数
        : type loop: int
        : param skip: 是否跳过
        : type skip: bool
        : param retry: 重试次数
        : type retry: int
        : param version: 版本号
        : type version: str
        : param inputs: 输入数据
        : type inputs: dict
        : param outputs: 输出数据
        : type outputs: dict
        """
        self.id = id
        self.node_id = node_id
        self.started_time = started_time
        self.archived_time = archived_time
        self.loop = loop
        self.skip = skip
        self.retry = retry
        self.version = version
        self.inputs = inputs
        self.outputs = outputs


class ExecutionShortHistory(Representable):
    """
    简短节点执行历史
    """

    def __init__(
        self,
        id: str,
        node_id: str,
        started_time: datetime,
        archived_time: datetime,
        loop: int,
        skip: bool,
        retry: int,
        version: str,
    ):
        """

        : param id: ID
        : type id: str
        : param node_id: Node ID
        : type node_id: str
        : param started_time: 开始时间
        : type started_time: datetime
        : param archived_time: 归档时间
        : type archived_time: datetime
        : param loop: 重入计数
        : type loop: int
        : param skip: 是否跳过
        : type skip: bool
        : param retry: 重试次数
        : type retry: int
        : param version: 版本号
        : type version: str
        """
        self.id = id
        self.node_id = node_id
        self.started_time = started_time
        self.archived_time = archived_time
        self.loop = loop
        self.skip = skip
        self.retry = retry
        self.version = version


class CallbackData(Representable):
    """
    节点回调数据
    """

    def __init__(self, id: int, node_id: str, version: str, data: dict):
        """

        :param id: 数据 ID
        :type id: int
        :param node_id: 节点 ID
        :type node_id: str
        :param version: 版本
        :type version: str
        :param data: 数据
        :type data: dict
        """
        self.id = id
        self.node_id = node_id
        self.version = version
        self.data = data


class SuspendedProcessInfo(Representable):
    """
    挂起进程信息
    """

    def __init__(
        self,
        process_id: int,
        current_node: str,
        root_pipeline_id: str,
        pipeline_stack: List[str],
    ):
        """

        :param process_id: 进程 ID
        :type process_id: int
        :param current_node: 当前节点 ID
        :type current_node: str
        :param root_pipeline_id: 根流程 ID
        :type root_pipeline_id: str
        :param pipeline_stack: 流程栈
        :type pipeline_stack: List[str]
        """
        self.process_id = process_id
        self.current_node = current_node
        self.root_pipeline_id = root_pipeline_id
        self.pipeline_stack = pipeline_stack

    @property
    def top_pipeline_id(self):
        return self.pipeline_stack[-1]


class ProcessInfo(Representable):
    """
    进程信息
    """

    def __init__(
        self,
        process_id: int,
        destination_id: str,
        root_pipeline_id: str,
        pipeline_stack: List[str],
        parent_id: int,
    ):
        """

        :param process_id: 进程 ID
        :type process_id: int
        :param destination_id: 进程目标节点 ID
        :type destination_id: str
        :param root_pipeline_id: 根流程 ID
        :type root_pipeline_id: str
        :param pipeline_stack: 流程栈
        :type pipeline_stack: List[str]
        :param parent_id: 父进程 ID
        :type parent_id: int
        """
        self.process_id = process_id
        self.destination_id = destination_id
        self.parent_id = parent_id
        self.root_pipeline_id = root_pipeline_id
        self.pipeline_stack = pipeline_stack

    @property
    def top_pipeline_id(self):
        return self.pipeline_stack[-1]


class DispatchProcess(Representable):
    """
    待调度进程信息
    """

    def __init__(self, process_id: int, node_id: str):
        """

        :param process_id: 进程 ID
        :type process_id: int
        :param node_id: 调度开始节点 ID
        :type node_id: str
        """
        self.process_id = process_id
        self.node_id = node_id

    def to_dict(self):
        return {"process_id": self.process_id, "node_id": self.node_id}

    @classmethod
    def from_dict(cls, obj: dict):
        return cls(process_id=obj["process_id"], node_id=obj["node_id"])


class ContextValueType(Enum):
    """

    :param Enum: [description]
    :type Enum: [type]
    """

    PLAIN = 1
    SPLICE = 2
    COMPUTE = 3


class ContextValue(Representable):
    def __init__(self, key: str, type: ContextValueType, value: Any, code: Optional[str] = None):
        if type is ContextValueType.COMPUTE and code is None:
            raise ValueError("code can't be none when type is COMPUTE")

        self.key = key
        self.type = type
        self.value = value
        self.code = code
