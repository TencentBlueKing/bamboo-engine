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

from copy import deepcopy

from bamboo_engine.exceptions import ValueError


def format_to_list(notype):
    """
    format a data to list
    :return:
    """
    if isinstance(notype, list):
        return notype
    if not notype:
        return []
    return [notype]


def format_node_io_to_list(node, i=True, o=True):
    if i:
        node["incoming"] = format_to_list(node["incoming"])

    if o:
        node["outgoing"] = format_to_list(node["outgoing"])


def format_pipeline_tree_io_to_list(pipeline_tree):
    """
    :summary: format incoming and outgoing to list
    :param pipeline_tree:
    :return:
    """
    for act in list(pipeline_tree["activities"].values()):
        format_node_io_to_list(act, o=False)

    for gateway in list(pipeline_tree["gateways"].values()):
        format_node_io_to_list(gateway, o=False)

    format_node_io_to_list(pipeline_tree["end_event"], o=False)


def get_node_for_sequence(sid, tree, node_type):
    target_id = tree["flows"][sid][node_type]

    if target_id in tree["activities"]:
        return tree["activities"][target_id]
    elif target_id in tree["gateways"]:
        return tree["gateways"][target_id]
    elif target_id == tree["end_event"]["id"]:
        return tree["end_event"]
    elif target_id == tree["start_event"]["id"]:
        return tree["start_event"]

    raise ValueError("node(%s) not in data" % target_id)


def get_nodes_dict(data):
    """
    get all FlowNodes of a pipeline
    """
    data = deepcopy(data)
    start = data["start_event"]["id"]
    end = data["end_event"]["id"]

    nodes = {start: data["start_event"], end: data["end_event"]}

    nodes.update(data["activities"])
    nodes.update(data["gateways"])

    for node in list(nodes.values()):
        # format to list
        node["incoming"] = format_to_list(node["incoming"])
        node["outgoing"] = format_to_list(node["outgoing"])

        node["source"] = [data["flows"][incoming]["source"] for incoming in node["incoming"]]
        node["target"] = [data["flows"][outgoing]["target"] for outgoing in node["outgoing"]]

    return nodes


def _compute_pipeline_main_nodes(node_id, node_dict):
    """
    计算流程中的主线节点，遇到并行网关/分支并行网关/子流程，则会跳过
    最后计算出来主干分支所允许开始的节点范围
    """
    nodes = []
    node_detail = node_dict[node_id]
    node_type = node_detail["type"]
    if node_type in [
        "EmptyStartEvent",
        "ServiceActivity",
        "ExclusiveGateway",
        "ParallelGateway",
        "ConditionalParallelGateway",
    ]:
        nodes.append(node_id)

    if node_type in ["EmptyStartEvent", "ServiceActivity", "ExclusiveGateway", "ConvergeGateway", "SubProcess"]:
        next_nodes = node_detail.get("target", [])
        for next_node_id in next_nodes:
            nodes += _compute_pipeline_main_nodes(next_node_id, node_dict)
    elif node_type in ["ParallelGateway", "ConditionalParallelGateway"]:
        next_node_id = node_detail["converge_gateway_id"]
        nodes += _compute_pipeline_main_nodes(next_node_id, node_dict)

    return nodes


def get_allowed_start_node_ids(pipeline_tree):
    start_event_id = pipeline_tree["start_event"]["id"]
    node_dict = get_nodes_dict(pipeline_tree)
    # 流程的开始位置只允许出现在主干，子流程/并行网关内的节点不允许作为起始位置
    allowed_start_node_ids = _compute_pipeline_main_nodes(start_event_id, node_dict)
    return allowed_start_node_ids
