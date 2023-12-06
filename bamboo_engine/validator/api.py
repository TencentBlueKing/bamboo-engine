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
import copy

from bamboo_engine import exceptions
from bamboo_engine.eri import NodeType

from . import rules
from .connection import validate_graph_connection, validate_graph_without_circle
from .gateway import validate_gateways, validate_stream
from .utils import (
    compute_pipeline_main_nodes,
    compute_pipeline_skip_executed_map,
    format_pipeline_tree_io_to_list,
    get_nodes_dict,
)


def validate_pipeline_start_node(pipeline: dict, node_id: str):
    # 当开始位置位于开始节点时,则直接返回
    if node_id == pipeline["start_event"]["id"]:
        return

    allowed_start_node_ids = get_allowed_start_node_ids(pipeline)
    if node_id not in allowed_start_node_ids:
        raise exceptions.StartPositionInvalidException("this node_id is not allowed as a starting node")


def get_skipped_execute_node_ids(pipeline_tree, start_node_id, validate=True):
    if validate and start_node_id not in get_allowed_start_node_ids(pipeline_tree):
        raise Exception("the start_node_id is not legal, please check")
    start_event_id = pipeline_tree["start_event"]["id"]

    # 如果开始节点 = start_node_id， 说明要从开始节点开始执行，此时没有任何节点被跳过
    if start_node_id == start_event_id:
        return []

    node_dict = get_nodes_dict(pipeline_tree)
    # 流程的开始位置只允许出现在主干，子流程/并行网关内的节点不允许作为起始位置
    will_skipped_nodes = compute_pipeline_skip_executed_map(start_event_id, node_dict, start_node_id)
    return list(will_skipped_nodes)


def get_allowed_start_node_ids(pipeline_tree):
    # 检查该流程是否已经经过汇聚网关填充
    def check_converge_gateway():
        gateways = pipeline_tree["gateways"]
        if not gateways:
            return True
        # 经过填充的网关会有converge_gateway_id 字段
        for gateway in gateways.values():
            if (
                gateway["type"] in ["ParallelGateway", "ConditionalParallelGateway"]
                and "converge_gateway_id" not in gateway
            ):
                return False

        return True

    if check_converge_gateway():
        pipeline_tree = copy.deepcopy(pipeline_tree)
        validate_gateways(pipeline_tree)
    start_event_id = pipeline_tree["start_event"]["id"]
    node_dict = get_nodes_dict(pipeline_tree)
    # 流程的开始位置只允许出现在主干，子流程/并行网关内的节点不允许作为起始位置
    allowed_start_node_ids = compute_pipeline_main_nodes(start_event_id, node_dict)
    return allowed_start_node_ids


def validate_and_process_pipeline(pipeline: dict, cycle_tolerate=False):
    for subproc in [act for act in pipeline["activities"].values() if act["type"] == NodeType.SubProcess.value]:
        validate_and_process_pipeline(subproc["pipeline"], cycle_tolerate)

    format_pipeline_tree_io_to_list(pipeline)
    # 1. connection validation
    validate_graph_connection(pipeline)

    # do not tolerate circle in flow
    if not cycle_tolerate:
        no_cycle = validate_graph_without_circle(pipeline)
        if not no_cycle["result"]:
            raise exceptions.TreeInvalidException(no_cycle["message"])

    # 2. gateway validation
    validate_gateways(pipeline)

    # 3. stream validation
    validate_stream(pipeline)


def add_sink_type(node_type: str):
    rules.FLOW_NODES_WITHOUT_STARTEVENT.append(node_type)
    rules.NODE_RULES[node_type] = rules.SINK_RULE
