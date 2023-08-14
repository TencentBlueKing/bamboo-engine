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

from pipeline.contrib.node_timeout.models import TimeoutNodeConfig
from pipeline.core.constants import PE


def apply_node_timout_configs(pipeline_tree: dict, configs: dict):
    """
    在 pipeline_tree 中应用节点超时配置
    :param pipeline_tree: pipeline_tree
    :param configs: 节点超时配置, e.g. {"node_id": {"enable": True, "action": "forced_fail", "seconds": "10"}}
    """
    new_pipeline_tree = copy.deepcopy(pipeline_tree)
    for act_id, act in pipeline_tree[PE.activities].items():
        if act["type"] == PE.SubProcess:
            apply_node_timout_configs(act[PE.pipeline], configs)
        elif act["type"] == PE.ServiceActivity and act_id in configs:
            act["timeout_config"] = {
                "enable": configs[act_id]["enable"],
                "action": configs[act_id]["action"],
                "seconds": configs[act_id]["seconds"],
            }
    return new_pipeline_tree


def batch_create_node_timeout_config(root_pipeline_id: str, pipeline_tree: dict):
    """
    批量创建节点超时配置
    :param root_pipeline_id: pipeline root ID
    :param pipeline_tree: pipeline_tree
    :return: 节点超时配置数据插入结果，e.g. {"result": True, "data": objs, "message": ""}
    """
    return TimeoutNodeConfig.objects.batch_create_node_timeout_config(root_pipeline_id, pipeline_tree)
