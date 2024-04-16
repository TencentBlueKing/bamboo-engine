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
import logging
from typing import Any, Dict, List, Type, Union

from celery import current_app
from pipeline.contrib.node_timer_event.adapter import NodeTimerEventBaseAdapter
from pipeline.contrib.node_timer_event.handlers import ActionManager
from pipeline.contrib.node_timer_event.models import ExpiredNodesRecord
from pipeline.contrib.node_timer_event.settings import node_timer_event_settings
from pipeline.eri.models import Process, State

logger = logging.getLogger("celery")


@current_app.task(acks_late=True)
def dispatch_expired_nodes(record_id: int):
    record: ExpiredNodesRecord = ExpiredNodesRecord.objects.get(id=record_id)
    node_keys: List[str] = json.loads(record.nodes)
    logger.info("[dispatch_expired_nodes] record -> %s, nodes -> %s", record_id, node_keys)

    adapter_class: Type[NodeTimerEventBaseAdapter] = node_timer_event_settings.adapter_class

    for node_key in node_keys:
        try:
            key_info: Dict[str, Union[str, int]] = adapter_class.parse_event_key(node_key)
        except ValueError:
            logger.warning(
                "[dispatch_expired_nodes] failed to parse key, skipped: record -> %s, node_key -> %s",
                record_id,
                node_key,
            )
            continue

        index: int = key_info["index"]
        node_id: str = key_info["node_id"]
        version: str = key_info["version"]

        if node_timer_event_settings.handle_queue is None:
            execute_node_timer_event_action.apply_async(kwargs={"node_id": node_id, "version": version, "index": index})
        else:
            execute_node_timer_event_action.apply_async(
                kwargs={"node_id": node_id, "version": version, "index": index},
                queue=node_timer_event_settings.handle_queue,
                routing_key=node_timer_event_settings.handle_queue,
            )

    logger.info("[dispatch_expired_nodes] dispatch finished: record -> %s, nodes -> %s", record_id, node_keys)
    # 删除临时记录
    record.delete()
    logger.info("[dispatch_expired_nodes] record deleted: record -> %s", record_id)


@current_app.task(ignore_result=True)
def execute_node_timer_event_action(node_id: str, version: str, index: int):

    adapter_class: Type[NodeTimerEventBaseAdapter] = node_timer_event_settings.adapter_class
    adapter: NodeTimerEventBaseAdapter = adapter_class(node_id=node_id, version=version)
    if not adapter.is_ready() or (adapter.index__event_map and index not in adapter.index__event_map):
        message: str = (
            f"[execute_node_timer_event_action] no timer config: "
            f"node_id -> {node_id}, version -> {version}, index -> {index}"
        )
        logger.exception(message)
        return {"result": False, "message": message, "data": None}

    event: Dict[str, Any] = adapter.index__event_map[index]

    # 判断当前节点是否符合策略执行要求
    is_process_current_node: bool = Process.objects.filter(
        root_pipeline_id=adapter.root_pipeline_id, current_node_id=node_id
    ).exists()
    is_node_match = State.objects.filter(node_id=node_id, version=version).exists()
    if not (is_node_match and is_process_current_node):
        message = (
            f"[execute_node_timer_event_action] node {node_id} with version {version} "
            f"in pipeline {adapter.root_pipeline_id} has been passed."
        )
        logger.error(message)
        return {"result": False, "message": message, "data": None}

    # 计算事件下一次触发事件并丢进待调度节点池
    adapter.add_to_pool(node_timer_event_settings.redis_inst, event)

    try:
        is_success: bool = ActionManager.get_action(
            adapter.root_pipeline_id, node_id, version, event["action"]
        ).notify()
        logger.info(
            f"[execute_node_timer_event_action] node {node_id} with version {version} in pipeline "
            f"{adapter.root_pipeline_id} action result is: {is_success}."
        )
        return {"result": is_success, "data": None}
    except Exception as e:
        logger.exception(
            f"[execute_node_timer_event_action] node {node_id} with version {version} in pipeline "
            f"{adapter.root_pipeline_id} error is: {e}."
        )
        return {"result": False, "data": None, "message": str(e)}
