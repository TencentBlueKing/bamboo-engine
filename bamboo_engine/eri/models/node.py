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

from enum import Enum
from typing import List, Dict

from bamboo_engine.utils.object import Representable


class NodeType(Enum):
    """
    节点类型枚举
    """

    ServiceActivity = "ServiceActivity"
    SubProcess = "SubProcess"
    ExclusiveGateway = "ExclusiveGateway"
    ParallelGateway = "ParallelGateway"
    ConditionalParallelGateway = "ConditionalParallelGateway"
    ConvergeGateway = "ConvergeGateway"
    EmptyStartEvent = "EmptyStartEvent"
    EmptyEndEvent = "EmptyEndEvent"
    ExecutableEndEvent = "ExecutableEndEvent"


class Node(Representable):
    """
    节点信息描述类
    """

    def __init__(
        self,
        id: str,
        type: NodeType,
        target_flows: List[str],
        target_nodes: List[str],
        targets: Dict[str, str],
        root_pipeline_id: str,
        parent_pipeline_id: str,
        can_skip: bool = True,
        can_retry: bool = True,
    ):
        """

        :param id: 节点 ID
        :type id: str
        :param type: 节点类型
        :type type: NodeType
        :param target_flows: 节点目标流 ID 列表
        :type target_flows: List[str]
        :param target_nodes: 目标节点 ID 列表
        :type target_nodes: List[str]
        :param targets: 节点目标流，目标节点 ID 映射
        :type targets: Dict[str, str]
        :param root_pipeline_id: 根流程 ID
        :type root_pipeline_id: str
        :param parent_pipeline_id: 父流程  ID
        :type parent_pipeline_id: str
        :param can_skip: 节点是否能够跳过
        :type can_skip: bool
        :param can_retry: 节点是否能够重试
        :type can_retry: bool
        """
        self.id = id
        self.type = type
        self.targets = targets
        self.target_flows = target_flows
        self.target_nodes = target_nodes
        self.root_pipeline_id = root_pipeline_id
        self.parent_pipeline_id = parent_pipeline_id
        self.can_skip = can_skip
        self.can_retry = can_retry


class EmptyStartEvent(Node):
    pass


class ConvergeGateway(Node):
    pass


class EmptyEndEvent(Node):
    pass


class Condition(Representable):
    """
    分支条件
    """

    def __init__(self, name: str, evaluation: str, target_id: str, flow_id: str):
        """

        :param name: 条件名
        :type name: str
        :param evaluation: 条件表达式
        :type evaluation: str
        :param target_id: 目标节点 ID
        :type target_id: str
        :param flow_id: 目标流 ID
        :type flow_id: str
        """
        self.name = name
        self.evaluation = evaluation
        self.target_id = target_id
        self.flow_id = flow_id


class ParallelGateway(Node):
    """
    并行网关
    """

    def __init__(self, converge_gateway_id: str, *args, **kwargs):
        """

        :param converge_gateway_id: 汇聚网关 ID
        :type converge_gateway_id: str
        """
        super().__init__(*args, **kwargs)
        self.converge_gateway_id = converge_gateway_id


class ConditionalParallelGateway(Node):
    """
    条件并行网关
    """

    def __init__(self, conditions: List[Condition], converge_gateway_id: str, *args, **kwargs):
        """

        :param conditions: 分支条件
        :type conditions: List[Condition]
        :param converge_gateway_id: 汇聚网关 ID
        :type converge_gateway_id: str
        """
        super().__init__(*args, **kwargs)
        self.conditions = conditions
        self.converge_gateway_id = converge_gateway_id


class ExclusiveGateway(Node):
    """
    分支网关
    """

    def __init__(self, conditions: List[Condition], *args, **kwargs):
        """

        :param conditions: 分支条件
        :type conditions: List[Condition]
        """
        super().__init__(*args, **kwargs)
        self.conditions = conditions


class ServiceActivity(Node):
    """
    服务节点
    """

    def __init__(self, code: str, version: str, error_ignorable: bool, *args, **kwargs):
        """

        :param code: Service Code
        :type code: str
        :param version: 版本
        :type version: str
        :param timeout: 超时限制
        :type timeout: Optional[int]
        :param error_ignorable: 是否忽略错误
        :type error_ignorable: bool
        """

        super().__init__(*args, **kwargs)
        self.code = code
        self.version = version
        self.error_ignorable = error_ignorable


class SubProcess(Node):
    """
    子流程
    """

    def __init__(self, start_event_id: str, *args, **kwargs):
        """

        :param start_event_id: 子流程开始节点 ID
        :type start_event_id: str
        """
        super().__init__(*args, **kwargs)
        self.start_event_id = start_event_id


class ExecutableEndEvent(Node):
    """
    可执行结束节点
    """

    def __init__(self, code: str, *args, **kwargs):
        """

        :param code: 可执行结束节点 ID
        :type code: str
        """
        super().__init__(*args, **kwargs)
        self.code = code
