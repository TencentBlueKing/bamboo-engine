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

import json

from pipeline.eri.models import Node as DBNode

from bamboo_engine import metrics
from bamboo_engine.eri import (
    Condition,
    ConditionalParallelGateway,
    ConvergeGateway,
    DefaultCondition,
    EmptyEndEvent,
    EmptyStartEvent,
    ExclusiveGateway,
    ExecutableEndEvent,
    LoopControlConfig,
    Node,
    NodeType,
    ParallelGateway,
    ServiceActivity,
    SubProcess,
)


class NodeMixin:
    def _get_node(self, node: DBNode):
        node_detail = json.loads(node.detail)
        node_type = node_detail["type"]
        targets = node_detail["targets"]
        common_args = dict(
            id=node.node_id,
            target_flows=list(targets.keys()),
            target_nodes=list(targets.values()),
            targets=node_detail["targets"],
            root_pipeline_id=node_detail["root_pipeline_id"],
            parent_pipeline_id=node_detail["parent_pipeline_id"],
            can_skip=node_detail["can_skip"],
            name=node_detail.get("name"),
            can_retry=node_detail["can_retry"],
            reserve_rollback=node_detail.get("reserve_rollback", False),
        )

        if node_type == NodeType.ServiceActivity.value:
            loop_config_dict = node_detail.get("loop_config") or {}
            # 仅在显式开启循环时才构造 LoopControlConfig，未开启时保持为 None，
            # 让引擎主流程的 ``if node.loop_config`` 判断更直观、零成本
            loop_config = (
                LoopControlConfig(
                    loop_times=loop_config_dict.get("loop_times"),
                    fail_skip=loop_config_dict.get("fail_skip", False),
                    retryable=loop_config_dict.get("retryable", False),
                    skippable=loop_config_dict.get("skippable", False),
                    outputs_key=loop_config_dict.get("outputs_key", LoopControlConfig.DEFAULT_OUTPUTS_KEY),
                )
                if loop_config_dict.get("enable", False)
                else None
            )
            return ServiceActivity(
                type=NodeType.ServiceActivity,
                code=node_detail["code"],
                version=node_detail["version"],
                error_ignorable=node_detail["error_ignorable"],
                loop_config=loop_config,
                **common_args
            )

        elif node_type == NodeType.SubProcess.value:
            return SubProcess(type=NodeType.SubProcess, start_event_id=node_detail["start_event_id"], **common_args)

        elif node_type == NodeType.ExclusiveGateway.value:
            default_condition = node_detail.get("default_condition")
            return ExclusiveGateway(
                type=NodeType.ExclusiveGateway,
                conditions=[Condition(**c) for c in node_detail["conditions"]],
                default_condition=DefaultCondition(**default_condition) if default_condition else None,
                extra_info=node_detail.get("extra_info"),
                **common_args
            )

        elif node_type == NodeType.ParallelGateway.value:
            return ParallelGateway(
                type=NodeType.ParallelGateway, converge_gateway_id=node_detail["converge_gateway_id"], **common_args
            )

        elif node_type == NodeType.ConditionalParallelGateway.value:
            default_condition = node_detail.get("default_condition")
            return ConditionalParallelGateway(
                type=NodeType.ConditionalParallelGateway,
                converge_gateway_id=node_detail["converge_gateway_id"],
                conditions=[Condition(**c) for c in node_detail["conditions"]],
                default_condition=DefaultCondition(**default_condition) if default_condition else None,
                extra_info=node_detail.get("extra_info"),
                **common_args
            )

        elif node_type == NodeType.ConvergeGateway.value:
            return ConvergeGateway(type=NodeType.ConvergeGateway, **common_args)

        elif node_type == NodeType.EmptyStartEvent.value:
            return EmptyStartEvent(type=NodeType.EmptyStartEvent, **common_args)

        elif node_type == NodeType.EmptyEndEvent.value:
            return EmptyEndEvent(type=NodeType.EmptyEndEvent, **common_args)

        elif node_type == NodeType.ExecutableEndEvent.value:
            return ExecutableEndEvent(type=NodeType.ExecutableEndEvent, code=node_detail["code"], **common_args)

        else:
            raise ValueError("unknown node type: {}".format(node_type))

    @metrics.setup_histogram(metrics.ENGINE_RUNTIME_NODE_READ_TIME)
    def get_node(self, node_id: str) -> Node:
        """
        获取某个节点的详细信息

        :param node_id: 节点 ID
        :type node_id: str
        :return: Node 实例
        :rtype: Node
        """
        node = DBNode.objects.get(node_id=node_id)
        return self._get_node(node)

    @metrics.setup_histogram(metrics.ENGINE_RUNTIME_NODE_READ_TIME)
    def update_node_loop_times(self, node_id: str, loop_times: int):
        """
        更新某个节点的 loop_config.loop_times 配置

        :param node_id: 节点 ID
        :type node_id: str
        :param loop_times: 新的循环次数
        :type loop_times: int
        """
        if not isinstance(loop_times, int) or loop_times < 0:
            raise ValueError("loop_times must be a non-negative integer, got: {}".format(loop_times))

        try:
            node = DBNode.objects.get(node_id=node_id)
        except DBNode.DoesNotExist:
            raise DBNode.DoesNotExist("Node with node_id({}) does not exist".format(node_id))

        node_detail = json.loads(node.detail)

        loop_config = node_detail.get("loop_config") or {}
        loop_config["loop_times"] = loop_times
        node_detail["loop_config"] = loop_config

        DBNode.objects.filter(node_id=node_id).update(detail=json.dumps(node_detail))
