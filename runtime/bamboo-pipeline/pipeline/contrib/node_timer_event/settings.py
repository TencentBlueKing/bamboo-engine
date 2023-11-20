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

from importlib import import_module

from django.conf import settings
from pipeline.contrib.node_timer_event import types


def get_import_path(cls: types.T) -> str:
    return f"{cls.__module__}.{cls.__name__}"


def import_string(dotted_path: str):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute/class') from err


class NodeTimerEventSettngs:
    PREFIX = "PIPELINE_NODE_TIMER_EVENT"
    DEFAULT_SETTINGS = {
        # # Redis key 前缀，用于记录正在执行的节点，命名示例: {app_code}:{app_env}:{module}:node_timer_event
        # v1 表示 node_timer_event 的版本，预留以隔离
        "key_prefix": "bamboo:v1:node_timer_event",
        # 节点计时器边界事件处理队列名称, 用于处理计时器边界事件， 需要 worker 接收该队列消息，默认为 None，即使用 celery 默认队列
        "dispatch_queue": None,
        # 节点计时器边界事件分发队列名称, 用于记录计时器边界事件， 需要 worker 接收该队列消息，默认为 None，即使用 celery 默认队列
        "handle_queue": None,
        # 执行节点池名称，用于记录正在执行的节点，需要保证 Redis key 唯一，命名示例: {app_code}:{app_env}:{module}:executing_node_pool
        "executing_pool": "bamboo:v1:node_timer_event:executing_node_pool",
        # 节点池扫描间隔，间隔越小，边界事件触发时间越精准，相应的事件处理的 workload 负载也会提升
        "pool_scan_interval": 1,
        # 最长过期时间，兜底删除 Redis 冗余数据，默认为 15 Days，请根据业务场景调整
        "max_expire_time": 60 * 60 * 24 * 15,
        # 边界事件处理适配器，默认为 `pipeline.contrib.node_timer_event.adapter.NodeTimerEventAdapter`
        "adapter_class": "pipeline.contrib.node_timer_event.adapter.NodeTimerEventAdapter",
    }

    def __getattr__(self, item: str):
        if item == "redis_inst":
            return settings.redis_inst
        if item == "adapter_class":
            return import_string(getattr(settings, f"{self.PREFIX}_{item.upper()}", self.DEFAULT_SETTINGS.get(item)))

        return getattr(settings, f"{self.PREFIX}_{item.upper()}", self.DEFAULT_SETTINGS.get(item))


node_timer_event_settings = NodeTimerEventSettngs()
