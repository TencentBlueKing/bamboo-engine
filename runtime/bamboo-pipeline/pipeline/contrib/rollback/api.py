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
from pipeline.contrib.rollback.handler import RollbackHandler
from pipeline.contrib.utils import ensure_return_pipeline_contrib_api_result


@ensure_return_pipeline_contrib_api_result
def rollback(root_pipeline_id: str, start_node_id: str, target_node_id: str):
    """
    :param root_pipeline_id: pipeline id
    :param start_node_id: 开始的 id
    :param target_node_id: 开始的 id
    :return: True or False

    回退的思路是，先搜索计算出来当前允许跳过的节点，在计算的过程中网关节点会合并成一个节点
    只允许回退到已经执行过的节点
    """
    RollbackHandler(root_pipeline_id, start_node_id, target_node_id).rollback()


@ensure_return_pipeline_contrib_api_result
def get_allowed_rollback_node_id_list(root_pipeline_id: str, start_node_id: str):
    return RollbackHandler(root_pipeline_id).get_allowed_rollback_node_id_list(start_node_id)
