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
import queue

from bamboo_engine.utils.string import unique_id

from ..validator.connection import validate_graph_without_circle
from .flow.data import Data, Params
from .flow.event import ExecutableEndEvent

__all__ = ["build_tree"]

__skeleton = {
    "id": None,
    "start_event": None,
    "end_event": None,
    "activities": {},
    "gateways": {},
    "flows": {},
    "data": {"inputs": {}, "outputs": []},
}

__node_type = {
    "ServiceActivity": "activities",
    "SubProcess": "activities",
    "EmptyEndEvent": "end_event",
    "EmptyStartEvent": "start_event",
    "ParallelGateway": "gateways",
    "ConditionalParallelGateway": "gateways",
    "ExclusiveGateway": "gateways",
    "ConvergeGateway": "gateways",
}

__start_elem = {"EmptyStartEvent"}

__end_elem = {"EmptyEndEvent"}

__multiple_incoming_type = {
    "ServiceActivity",
    "ConvergeGateway",
    "EmptyEndEvent",
    "ParallelGateway",
    "ConditionalParallelGateway",
    "ExclusiveGateway",
    "SubProcess",
}

__incoming = "__incoming"


def build_tree(start_elem, id=None, data=None):
    tree = copy.deepcopy(__skeleton)
    elem_queue = queue.Queue()
    processed_elem = set()

    tree[__incoming] = {}
    elem_queue.put(start_elem)

    while not elem_queue.empty():
        # get elem
        elem = elem_queue.get()

        # update node when we meet again
        if elem.id in processed_elem:
            __update(tree, elem)
            continue

        # add to queue
        for e in elem.outgoing:
            elem_queue.put(e)

        # mark as processed
        processed_elem.add(elem.id)

        # tree grow
        __grow(tree, elem)

    del tree[__incoming]
    tree["id"] = id or unique_id("p")
    user_data = data.to_dict() if isinstance(data, Data) else data
    tree["data"] = user_data or tree["data"]
    return tree


def _get_next_node(node, pipeline_tree):
    """
    获取当前节点的下一个节点
    """

    out_goings = node["outgoing"]

    # 说明曾经去除过环，此时没有out_goings
    if out_goings == "":
        return []

    # 当只有一个输出时,
    if not isinstance(out_goings, list):
        out_goings = [out_goings]

    next_nodes = []
    for out_going in out_goings:
        target_id = pipeline_tree["flows"][out_going]["target"]
        if target_id in pipeline_tree["activities"]:
            next_nodes.append(pipeline_tree["activities"][target_id])
        elif target_id in pipeline_tree["gateways"]:
            next_nodes.append(pipeline_tree["gateways"][target_id])
        elif target_id == pipeline_tree["end_event"]["id"]:
            next_nodes.append(pipeline_tree["end_event"])

    return next_nodes


def _get_all_nodes(pipeline_tree: dict, with_subprocess: bool = False) -> dict:
    """
    获取 pipeline_tree 中所有 activity 的信息

    :param pipeline_tree: pipeline web tree
    :param with_subprocess: 是否是子流程的 tree
    :return: 包含 pipeline_tree 中所有 activity 的字典（包括子流程的 acitivity）
    """
    all_nodes = {}
    all_nodes.update(pipeline_tree["activities"])
    all_nodes.update(pipeline_tree["gateways"])
    all_nodes.update(
        {
            pipeline_tree["start_event"]["id"]: pipeline_tree["start_event"],
            pipeline_tree["end_event"]["id"]: pipeline_tree["end_event"],
        }
    )
    if with_subprocess:
        for act in pipeline_tree["activities"].values():
            if act["type"] == "SubProcess":
                all_nodes.update(_get_all_nodes(act["pipeline"], with_subprocess=True))
    return all_nodes


def _delete_flow_id_from_node_io(node, flow_id, io_type):
    """
    删除节点的某条连线，io_type(incoming or outgoing)
    """
    if node[io_type] == flow_id:
        node[io_type] = ""
    elif isinstance(node[io_type], list):
        if len(node[io_type]) == 1 and node[io_type][0] == flow_id:
            node[io_type] = (
                "" if node["type"] not in ["ExclusiveGateway", "ParallelGateway", "ConditionalParallelGateway"] else []
            )
        else:
            node[io_type].pop(node[io_type].index(flow_id))

            # recover to original format
            if (
                len(node[io_type]) == 1
                and io_type == "outgoing"
                and node["type"] in ["EmptyStartEvent", "ServiceActivity", "ConvergeGateway"]
            ):
                node[io_type] = node[io_type][0]


def _acyclic(pipeline):
    """
    @summary: 逆转反向边
    @return:
    """

    pipeline["all_nodes"] = _get_all_nodes(pipeline, with_subprocess=True)

    deformed_flows = {
        "{}.{}".format(flow["source"], flow["target"]): flow_id for flow_id, flow in pipeline["flows"].items()
    }
    while True:
        no_circle = validate_graph_without_circle(pipeline)
        if no_circle["result"]:
            break
        source = no_circle["error_data"][-2]
        target = no_circle["error_data"][-1]
        circle_flow_key = "{}.{}".format(source, target)
        flow_id = deformed_flows[circle_flow_key]
        pipeline["flows"][flow_id].update({"source": target, "target": source})

        source_node = pipeline["all_nodes"][source]
        _delete_flow_id_from_node_io(source_node, flow_id, "outgoing")

        target_node = pipeline["all_nodes"][target]
        _delete_flow_id_from_node_io(target_node, flow_id, "incoming")


def _acyclic_flow(tree):
    _acyclic(tree)
    for node in tree["activities"].values():
        if node["type"] == "SubProcess":
            _acyclic_flow(node["pipeline"])


def generate_pipeline_token(pipeline_tree):
    tree = copy.deepcopy(pipeline_tree)
    # 去环
    _acyclic_flow(tree)

    start_node = tree["start_event"]
    token = unique_id("t")
    node_token_map = {start_node["id"]: token}
    inject_pipeline_token(start_node, tree, node_token_map, token)
    return node_token_map


# 需要处理子流程的问题
def inject_pipeline_token(node, pipeline_tree, node_token_map, token):
    # 如果是网关
    if node["type"] in ["ParallelGateway", "ExclusiveGateway", "ConditionalParallelGateway"]:
        next_nodes = _get_next_node(node, pipeline_tree)
        target_nodes = {}
        for next_node in next_nodes:
            # 分支网关各个分支token相同
            node_token = token
            node_token_map[next_node["id"]] = node_token
            # 并行网关token不同
            if node["type"] in ["ParallelGateway", "ConditionalParallelGateway"]:
                node_token = unique_id("t")
                node_token_map[next_node["id"]] = node_token

            # 如果是并行网关，沿着路径向内搜索，最终遇到对应的汇聚网关会返回
            target_node = inject_pipeline_token(next_node, pipeline_tree, node_token_map, node_token)
            if target_node:
                target_nodes[target_node["id"]] = target_node

        for target_node in target_nodes.values():
            # 汇聚网关可以直连结束节点，所以可能会存在找不到对应的汇聚网关的情况
            if target_node["type"] in ["EmptyEndEvent", "ExecutableEndEvent"]:
                node_token_map[target_node["id"]] = token
                continue
            # 汇聚网关的token等于对应的网关的token
            node_token_map[target_node["id"]] = token
            # 到汇聚网关之后，此时继续向下遍历
            next_node = _get_next_node(target_node, pipeline_tree)[0]
            # 汇聚网关只会有一个出度
            node_token_map[next_node["id"]] = token
            inject_pipeline_token(next_node, pipeline_tree, node_token_map, token)

    # 如果是汇聚网关，并且id等于converge_id，说明此时遍历在某个单元
    if node["type"] == "ConvergeGateway":
        return node

    # 如果是普通的节点，说明只有一个出度，此时直接向下遍历就好
    if node["type"] in ["ServiceActivity", "EmptyStartEvent"]:
        next_node_list = _get_next_node(node, pipeline_tree)
        # 此时有可能遇到一个去环的节点，该节点没有
        if not next_node_list:
            return
        next_node = next_node_list[0]
        node_token_map[next_node["id"]] = token
        return inject_pipeline_token(next_node, pipeline_tree, node_token_map, token)

    # 如果遇到结束节点，直接返回
    if node["type"] in ["EmptyEndEvent", "ExecutableEndEvent"]:
        return node

    if node["type"] == "SubProcess":
        subprocess_pipeline_tree = node["pipeline"]
        subprocess_start_node = subprocess_pipeline_tree["start_event"]
        subprocess_start_node_token = unique_id("t")
        node_token_map[subprocess_start_node["id"]] = subprocess_start_node_token
        inject_pipeline_token(
            subprocess_start_node, subprocess_pipeline_tree, node_token_map, subprocess_start_node_token
        )
        next_node = _get_next_node(node, pipeline_tree)[0]
        node_token_map[next_node["id"]] = token
        return inject_pipeline_token(next_node, pipeline_tree, node_token_map, token)


def __update(tree, elem):
    node_type = __node_type[elem.type()]
    node = tree[node_type] if node_type == "end_event" else tree[node_type][elem.id]
    node["incoming"] = tree[__incoming][elem.id]


def __grow(tree, elem):
    if elem.type() in __start_elem:
        outgoing = unique_id("f")
        tree["start_event"] = {
            "incoming": "",
            "outgoing": outgoing,
            "type": elem.type(),
            "id": elem.id,
            "name": elem.name,
        }

        next_elem = elem.outgoing[0]
        __grow_flow(tree, outgoing, elem, next_elem)

    elif elem.type() in __end_elem or isinstance(elem, ExecutableEndEvent):
        tree["end_event"] = {
            "incoming": tree[__incoming][elem.id],
            "outgoing": "",
            "type": elem.type(),
            "id": elem.id,
            "name": elem.name,
        }

    elif elem.type() == "ServiceActivity":
        outgoing = unique_id("f")

        tree["activities"][elem.id] = {
            "incoming": tree[__incoming][elem.id],
            "outgoing": outgoing,
            "type": elem.type(),
            "id": elem.id,
            "name": elem.name,
            "error_ignorable": elem.error_ignorable,
            "timeout": elem.timeout,
            "skippable": elem.skippable,
            "retryable": elem.retryable,
            "component": elem.component_dict(),
            "optional": False,
        }

        next_elem = elem.outgoing[0]
        __grow_flow(tree, outgoing, elem, next_elem)

    elif elem.type() == "SubProcess":
        outgoing = unique_id("f")

        subprocess_param = elem.params.to_dict() if isinstance(elem.params, Params) else elem.params

        subprocess = {
            "id": elem.id,
            "incoming": tree[__incoming][elem.id],
            "name": elem.name,
            "outgoing": outgoing,
            "type": elem.type(),
            "params": subprocess_param,
        }

        subprocess["pipeline"] = build_tree(start_elem=elem.start, id=elem.id, data=elem.data)

        tree["activities"][elem.id] = subprocess

        next_elem = elem.outgoing[0]
        __grow_flow(tree, outgoing, elem, next_elem)

    elif elem.type() == "ParallelGateway":
        outgoing = [unique_id("f") for _ in range(len(elem.outgoing))]

        tree["gateways"][elem.id] = {
            "id": elem.id,
            "incoming": tree[__incoming][elem.id],
            "outgoing": outgoing,
            "type": elem.type(),
            "name": elem.name,
        }

        for i, next_elem in enumerate(elem.outgoing):
            __grow_flow(tree, outgoing[i], elem, next_elem)

    elif elem.type() in {"ExclusiveGateway", "ConditionalParallelGateway"}:
        outgoing = [unique_id("f") for _ in range(len(elem.outgoing))]

        tree["gateways"][elem.id] = {
            "id": elem.id,
            "incoming": tree[__incoming][elem.id],
            "outgoing": outgoing,
            "type": elem.type(),
            "name": elem.name,
            "conditions": elem.link_conditions_with(outgoing),
            "default_condition": elem.link_default_condition_with(outgoing),
        }

        for i, next_elem in enumerate(elem.outgoing):
            __grow_flow(tree, outgoing[i], elem, next_elem)

    elif elem.type() == "ConvergeGateway":
        outgoing = unique_id("f")

        tree["gateways"][elem.id] = {
            "id": elem.id,
            "incoming": tree[__incoming][elem.id],
            "outgoing": outgoing,
            "type": elem.type(),
            "name": elem.name,
        }

        next_elem = elem.outgoing[0]
        __grow_flow(tree, outgoing, elem, next_elem)

    else:
        raise Exception()


def __grow_flow(tree, outgoing, elem, next_element):
    tree["flows"][outgoing] = {
        "is_default": False,
        "source": elem.id,
        "target": next_element.id,
        "id": outgoing,
    }
    if next_element.type() in __multiple_incoming_type:
        tree[__incoming].setdefault(next_element.id, []).append(outgoing)
    else:
        tree[__incoming][next_element.id] = outgoing
