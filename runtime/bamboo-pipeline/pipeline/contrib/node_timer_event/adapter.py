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

import abc
import datetime
import json
import logging
import re
from typing import Dict, List, Optional, Union

from pipeline.contrib.node_timer_event.models import NodeTimerEventConfig
from pipeline.contrib.node_timer_event.settings import node_timer_event_settings
from pipeline.contrib.node_timer_event.types import TimerEvent, TimerEvents
from pipeline.contrib.node_timer_event.utils import parse_timer_defined

logger = logging.getLogger(__name__)

EVENT_KEY_PATTERN = re.compile(r".*node:(?P<node_id>.+):version:(?P<version>.+):index:(?P<index>\d+)")


class NodeTimerEventBaseAdapter(abc.ABC):

    node_id: str = None
    version: str = None
    root_pipeline_id: Optional[str] = None
    events: Optional[TimerEvents] = None
    index__event_map: Optional[Dict[int, TimerEvent]] = None

    def __init__(self, node_id: str, version: str):
        self.node_id: str = node_id
        self.version: str = version

    def is_ready(self) -> bool:
        """适配器是否就绪"""
        if not self.events:
            return False
        return True

    def fetch_keys_to_be_rem(self) -> List[str]:
        """
        获取需要被移除的事件 Key
        :return:
        """
        return [self.get_event_key(event) for event in self.events]

    def get_event_key(self, event: TimerEvent) -> str:
        """
        获取事件 Key
        :param event:
        :return:
        """

        # zset 没有按字符串匹配模式批量删除 key 的支持，使用 key 的命名采用已检索的信息进行拼接
        # 之前想把 loop 也维护进去，发觉移除操作非常麻烦，故采用 incr 的方式，单独维护每个事件事件的触发次数
        key_prefix: str = f"{node_timer_event_settings.key_prefix}:node:{self.node_id}:version:{self.version}"
        return f"{key_prefix}:index:{event['index']}"

    @classmethod
    def get_next_expired_time(cls, event: TimerEvent, start: Optional[datetime.datetime] = None) -> float:
        """
        获取时间事件下一次过期时间
        :param event: 事件详情
        :param start: 开始时间，默认取 datetime.now()
        :return:
        """
        return parse_timer_defined(event["timer_type"], event["defined"], start=start or datetime.datetime.now())[
            "timestamp"
        ]

    def add_to_pool(self, redis_inst, event: TimerEvent):

        key: str = self.get_event_key(event)

        expired_time: float = self.get_next_expired_time(event)

        # TODO 考虑 incr & zadd 合并，使用 lua 封装成原子操作
        loop: int = int(redis_inst.incr(key, 1))
        redis_inst.expire(key, node_timer_event_settings.max_expire_time)
        if loop > event["repetitions"]:
            logger.info(
                "[add_to_pool] No need to add: node -> %s, version -> %s, loop -> %s, event -> %s",
                self.node_id,
                self.version,
                loop,
                event,
            )
            return

        redis_inst.zadd(node_timer_event_settings.executing_pool, mapping={key: expired_time}, nx=True)

        logger.info(
            "[add_to_pool] add event to redis: "
            "node_id -> %s, version -> %s, event -> %s, key -> %s, expired_time -> %s",
            self.node_id,
            self.version,
            event,
            key,
            expired_time,
        )

    @classmethod
    def parse_event_key(cls, key: str) -> Dict[str, Union[str, int]]:
        match = EVENT_KEY_PATTERN.match(key)
        if match:
            key_info: Dict[str, Union[str, int]] = match.groupdict()
            # to int
            key_info["index"] = int(key_info["index"])

            return key_info

        else:
            raise ValueError(f"invalid key -> {key}")


class NodeTimerEventAdapter(NodeTimerEventBaseAdapter):
    def __init__(self, node_id: str, version: str):
        super().__init__(node_id, version)

        node_timer_event_config: NodeTimerEventConfig = NodeTimerEventConfig.objects.filter(
            node_id=self.node_id
        ).first()

        if not node_timer_event_config:
            return

        self.root_pipeline_id: str = node_timer_event_config.root_pipeline_id
        self.events: TimerEvents = json.loads(node_timer_event_config.events)
        self.index__event_map: Dict[int, TimerEvent] = {event["index"]: event for event in self.events}
