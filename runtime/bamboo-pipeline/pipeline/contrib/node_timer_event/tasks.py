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
from typing import Any, Dict, List, Union

from celery import task
from pipeline.contrib.node_timer_event.handlers import ActionFactory
from pipeline.contrib.node_timer_event.models import (
    ExpiredNodesRecord,
    NodeTimerEventConfig,
)
from pipeline.contrib.node_timer_event.settings import node_timer_event_settings
from pipeline.eri.models import Process, State

logger = logging.getLogger("celery")


@task(acks_late=True)
def dispatch_expired_nodes(record_id: int):
    record: ExpiredNodesRecord = ExpiredNodesRecord.objects.get(id=record_id)
    node_keys: List[str] = json.loads(record.nodes)
    for node_key in node_keys:
        key_info: Dict[str, Union[str, int]] = NodeTimerEventConfig.parse_event_key(node_key)
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


@task(ignore_result=True)
def execute_node_timer_event_action(node_id: str, version: str, index: int):

    node_timer_event_config: NodeTimerEventConfig = NodeTimerEventConfig.objects.filter(node_id=node_id).first()

    if node_timer_event_config is None or index not in node_timer_event_config.get_index__event_map():
        message: str = (
            f"[execute_node_timer_event_action] no timer config: "
            f"node_id -> {node_id}, version -> {version}, index -> {index}"
        )
        logger.info(message)
        return {"result": False, "message": message, "data": None}

    event: Dict[str, Any] = node_timer_event_config.get_index__event_map()[index]
    root_pipeline_id: str = node_timer_event_config.root_pipeline_id

    # 判断当前节点是否符合策略执行要求
    is_process_current_node: bool = Process.objects.filter(
        root_pipeline_id=root_pipeline_id, current_node_id=node_id
    ).exists()
    is_node_match = State.objects.filter(node_id=node_id, version=version).exists()
    if not (is_node_match and is_process_current_node):
        message = (
            f"[execute_node_timer_event_action] node {node_id} with version {version} "
            f"in pipeline {root_pipeline_id} has been passed."
        )
        logger.error(message)
        return {"result": False, "message": message, "data": None}

    # 计算事件下一次触发事件并丢进待调度节点池
    NodeTimerEventConfig.add_to_pool(node_timer_event_settings.redis_inst, node_id, version, event)

    try:
        is_success: bool = ActionFactory.get_action(root_pipeline_id, node_id, version, event["action"]).notify()
        logger.info(
            f"[execute_node_timer_event_action] node {node_id} with version {version} in pipeline {root_pipeline_id} "
            f"action result is: {is_success}."
        )
        return {"result": is_success, "data": None}
    except Exception as e:
        logger.exception(
            f"[execute_node_timer_event_action] node {node_id} with version {version} in pipeline {root_pipeline_id} "
            f"error is: {e}."
        )
        return {"result": False, "data": None, "message": str(e)}
