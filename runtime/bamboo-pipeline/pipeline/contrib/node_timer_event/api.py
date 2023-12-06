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
from typing import Any, Dict, List

from pipeline.contrib.node_timer_event.models import NodeTimerEventConfig
from pipeline.contrib.utils import ensure_return_pipeline_contrib_api_result
from pipeline.core.constants import PE


@ensure_return_pipeline_contrib_api_result
def apply_node_timer_event_configs(pipeline_tree: Dict[str, Any], configs: Dict[str, List[Dict[str, Any]]]):
    """
    在 pipeline_tree 中应用节点计时器边界事件配置
    :param pipeline_tree: pipeline_tree
    :param configs: 节点计时器边界事件配置
    e.g. {"node_id": [{"enable": True, "action": "forced_fail", "timer_type": "time_duration", "defined": "PT10M"}]}
    """
    new_pipeline_tree = copy.deepcopy(pipeline_tree)
    for act_id, act in pipeline_tree[PE.activities].items():
        if act["type"] == PE.SubProcess:
            apply_node_timer_event_configs(act[PE.pipeline], configs)
        elif act["type"] == PE.ServiceActivity and act_id in configs:
            act.setdefault("events", {})["timer_events"] = [
                {
                    "enable": config["enable"],
                    "timer_type": config["timer_type"],
                    "action": config["action"],
                    "defined": config["defined"],
                }
                for config in configs[act_id]
            ]
    return new_pipeline_tree


@ensure_return_pipeline_contrib_api_result
def batch_create_node_timer_event_config(root_pipeline_id: str, pipeline_tree: Dict[str, Any]):
    """
    批量创建节点时间事件配置
    :param root_pipeline_id: pipeline root ID
    :param pipeline_tree: pipeline_tree
    :return: 节点计时器边界事件配置数据插入结果，e.g. {"result": True, "data": objs, "message": ""}
    """
    return NodeTimerEventConfig.objects.batch_create_node_timer_event_config(root_pipeline_id, pipeline_tree)
