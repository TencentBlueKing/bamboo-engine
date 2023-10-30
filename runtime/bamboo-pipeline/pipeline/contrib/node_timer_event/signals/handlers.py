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
import logging
from typing import Any, Dict, List, Optional

from django.dispatch import receiver
from pipeline.contrib.node_timer_event.models import NodeTimerEventConfig
from pipeline.contrib.node_timer_event.settings import node_timer_event_settings
from pipeline.eri.signals import post_set_state

from bamboo_engine import states as bamboo_engine_states

logger = logging.getLogger(__name__)


def _node_timer_event_info_update(redis_inst, to_state: str, node_id: str, version: str):

    events: Optional[List[Dict[str, Any]]] = None
    node_timer_event_config: Optional[NodeTimerEventConfig] = None

    if to_state in [
        bamboo_engine_states.RUNNING,
        bamboo_engine_states.FAILED,
        bamboo_engine_states.FINISHED,
        bamboo_engine_states.SUSPENDED,
    ]:
        node_timer_event_config: Optional[NodeTimerEventConfig] = NodeTimerEventConfig.objects.filter(
            node_id=node_id
        ).first()
        if not node_timer_event_config:
            logger.info(
                "[node_timer_event_info_update] node_timer_event_config not exist and skipped: "
                "node_id -> %s, version -> %s",
                node_id,
                version,
            )
            return
        events = node_timer_event_config.get_events()
        logger.info(
            "[node_timer_event_info_update] load node_timer_event_config: node_id -> %s, version -> %s, events -> %s",
            node_id,
            version,
            events,
        )

    if to_state == bamboo_engine_states.RUNNING:
        # 遍历节点时间事件，丢进待调度节点池
        for event in events:
            node_timer_event_config.add_to_pool(redis_inst, node_id, version, event)

    elif to_state in [bamboo_engine_states.FAILED, bamboo_engine_states.FINISHED, bamboo_engine_states.SUSPENDED]:
        keys: List[str] = [node_timer_event_config.get_event_key(node_id, version, event) for event in events]
        redis_inst.zrem(node_timer_event_settings.executing_pool, *keys)
        redis_inst.delete(*keys)
        logger.info(
            "[node_timer_event_info_update] remove events from redis: "
            "node_id -> %s, version -> %s, events -> %s, keys -> %s",
            node_id,
            version,
            events,
            keys,
        )


@receiver(post_set_state)
def bamboo_engine_eri_node_state_handler(sender, node_id, to_state, version, root_id, parent_id, loop, **kwargs):
    try:
        _node_timer_event_info_update(node_timer_event_settings.redis_inst, to_state, node_id, version)
    except Exception:
        logger.exception("node_timeout_info_update error")
