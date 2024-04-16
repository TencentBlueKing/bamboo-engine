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

from celery import current_app

from pipeline.contrib.node_timeout.settings import node_timeout_settings
from pipeline.eri.models import State, Process

from pipeline.contrib.node_timeout.models import TimeoutNodeConfig, TimeoutNodesRecord


logger = logging.getLogger("celery")


@current_app.task(acks_late=True)
def dispatch_timeout_nodes(record_id: int):
    record = TimeoutNodesRecord.objects.get(id=record_id)
    nodes = json.loads(record.timeout_nodes)
    for node in nodes:
        node_id, version = node.split("_")
        if node_timeout_settings.handle_queue is None:
            execute_node_timeout_strategy.apply_async(kwargs={"node_id": node_id, "version": version})
        else:
            execute_node_timeout_strategy.apply_async(
                kwargs={"node_id": node_id, "version": version},
                queue=node_timeout_settings.handle_queue,
                routing_key=node_timeout_settings.handle_queue,
            )


@current_app.task(ignore_result=True)
def execute_node_timeout_strategy(node_id, version):
    timeout_config = TimeoutNodeConfig.objects.filter(node_id=node_id).only("root_pipeline_id", "action").first()
    if timeout_config is None:
        logger.error(f"[execute_node_timeout_strategy] node {node_id} with version {version} has no timeout config.")
        return {
            "result": False,
            "message": f"no timeout config with node {node_id} and version {version}",
            "data": None,
        }

    root_pipeline_id, action = timeout_config.root_pipeline_id, timeout_config.action

    # 判断当前节点是否符合策略执行要求
    is_process_current_node = Process.objects.filter(
        root_pipeline_id=root_pipeline_id, current_node_id=node_id
    ).exists()
    node_match = State.objects.filter(node_id=node_id, version=version).exists()
    if not (node_match and is_process_current_node):
        message = (
            f"[execute_node_timeout_strategy] node {node_id} with version {version} "
            f"in pipeline {root_pipeline_id} has been passed."
        )
        logger.error(message)
        return {"result": False, "message": message, "data": None}

    try:
        handler = node_timeout_settings.handler.get(action)
        action_result = handler.deal_with_timeout_node(node_id)
        logger.info(
            f"[execute_node_timeout_strategy] node {node_id} with version {version} in pipeline {root_pipeline_id} "
            f"action result is: {action_result}."
        )
    except Exception as e:
        logger.exception(
            f"[execute_node_timeout_strategy] node {node_id} with version {version} in pipeline {root_pipeline_id} "
            f"error is: {e}."
        )
        return {"result": False, "data": None, "message": str(e)}

    return action_result
