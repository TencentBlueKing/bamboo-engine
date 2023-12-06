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
from pipeline.contrib.rollback.constants import TOKEN
from pipeline.contrib.rollback.handler import RollbackDispatcher
from pipeline.contrib.utils import ensure_return_pipeline_contrib_api_result


@ensure_return_pipeline_contrib_api_result
def rollback(
    root_pipeline_id: str, start_node_id: str, target_node_id: str, skip_rollback_nodes: list = None, mode: str = TOKEN
):
    """
    :param root_pipeline_id: pipeline id
    :param start_node_id: 开始的 id
    :param target_node_id: 开始的 id
    :param mode 回滚模式
    :return: True or False
    """
    RollbackDispatcher(root_pipeline_id, mode).rollback(start_node_id, target_node_id)


@ensure_return_pipeline_contrib_api_result
def reserve_rollback(root_pipeline_id: str, start_node_id: str, target_node_id: str, mode: str = TOKEN):
    RollbackDispatcher(root_pipeline_id, mode).reserve_rollback(start_node_id, target_node_id)


@ensure_return_pipeline_contrib_api_result
def cancel_reserved_rollback(root_pipeline_id: str, start_node_id: str, target_node_id: str, mode: str = TOKEN):
    RollbackDispatcher(root_pipeline_id, mode).cancel_reserved_rollback(start_node_id, target_node_id)


@ensure_return_pipeline_contrib_api_result
def retry_rollback_failed_node(root_pipeline_id: str, node_id: str, retry_data: dict = None, mode: str = TOKEN):
    RollbackDispatcher(root_pipeline_id, mode).retry_rollback_failed_node(node_id, retry_data)


@ensure_return_pipeline_contrib_api_result
def get_allowed_rollback_node_id_list(root_pipeline_id: str, start_node_id: str, mode: str = TOKEN):
    return RollbackDispatcher(root_pipeline_id, mode).get_allowed_rollback_node_id_list(start_node_id)
