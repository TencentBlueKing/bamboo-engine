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

from django.conf import settings


class NodeTimerEventSettngs:
    PREFIX = "PIPELINE_NODE_TIMER_EVENT"
    DEFAULT_SETTINGS = {
        # v1 表示 node_timer_event 的版本，预留以隔离
        "key_prefix": "bamboo:v1:node_timer_event",
        "dispatch_queue": None,
        "handle_queue": None,
        "executing_pool": "bamboo:v1:node_timer_event:executing_node_pool",
    }

    def __getattr__(self, item: str):
        if item == "redis_inst":
            return settings.redis_inst
        return getattr(settings, f"{self.PREFIX}_{item.upper()}", self.DEFAULT_SETTINGS.get(item))


node_timer_event_settings = NodeTimerEventSettngs()
