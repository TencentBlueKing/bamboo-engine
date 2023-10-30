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
import datetime
import json
import logging
import re
import typing
from typing import Any, Dict, List, Optional, Union

from django.db import models
from django.utils.translation import ugettext_lazy as _
from pipeline.contrib.node_timer_event.settings import node_timer_event_settings
from pipeline.contrib.node_timer_event.types import TimeDefined
from pipeline.contrib.node_timer_event.utils import parse_timer_defined
from pipeline.core.constants import PE

logger = logging.getLogger(__name__)


EVENT_KEY_PATTERN = re.compile(r".*node:(?P<node_id>.+):version:(?P<version>.+):index:(?P<index>\d+)")


class NodeTimerEventConfigManager(models.Manager):
    def parse_node_timer_event_configs(self, pipeline_tree: Dict[str, Any]) -> Dict[str, Any]:
        """解析事件时间"""
        configs: List[Dict[str, Any]] = []
        for act_id, act in pipeline_tree[PE.activities].items():
            if act["type"] == PE.SubProcess:
                result = self.parse_node_timer_event_configs(act[PE.pipeline])
                if not result["result"]:
                    return result
                configs.extend(result["data"])
            elif act["type"] == PE.ServiceActivity:
                index: int = 1
                treated_timer_events: List[Dict[str, Any]] = []
                timer_events: List[Dict[str, Any]] = (act.get("events") or {}).get("timer_events") or []
                for timer_event in timer_events:
                    enable: bool = timer_event.get("enable") or False
                    if not enable:
                        continue

                    timer_type: Optional[str] = timer_event.get("timer_type")
                    defined: Optional[str] = timer_event.get("defined")

                    try:
                        timer_defined: TimeDefined = parse_timer_defined(timer_type, defined)
                    except Exception:
                        # 对于不符合格式要求的情况，记录日志并跳过
                        logger.exception(
                            "[parse_node_timer_event_configs] parse timer_defined failed: "
                            "node_id -> %s, timer_type -> %s, defined -> %s",
                            act_id,
                            timer_type,
                            defined,
                        )
                        continue

                    treated_timer_events.append(
                        {
                            "index": index,
                            "action": timer_event.get("action"),
                            "timer_type": timer_type,
                            "repetitions": timer_defined["repetitions"],
                            "defined": defined,
                        }
                    )

                    index += 1

                configs.append({"node_id": act_id, "events": treated_timer_events})

        return {"result": True, "data": configs, "message": ""}

    def batch_create_node_timer_event_config(self, root_pipeline_id: str, pipeline_tree: dict):
        """批量创建节点超时配置"""

        config_parse_result: Dict[str, Any] = self.parse_node_timer_event_configs(pipeline_tree)
        # 这里忽略解析失败的情况，保证即使解析失败也能正常创建任务
        if not config_parse_result["result"]:
            logger.error(
                f"[batch_create_node_timer_event_config] parse node timer event config "
                f'failed: {config_parse_result["result"]}'
            )
            return config_parse_result

        configs: List[Dict[str, Any]] = config_parse_result["data"] or []
        config_objs: typing.List[NodeTimerEventConfig] = [
            NodeTimerEventConfig(
                root_pipeline_id=root_pipeline_id, node_id=config["node_id"], events=json.dumps(config["events"])
            )
            for config in configs
        ]
        objs = self.bulk_create(config_objs, batch_size=1000)
        return {"result": True, "data": objs, "message": ""}


class NodeTimerEventConfig(models.Model):
    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    node_id = models.CharField(verbose_name="task node id", max_length=64, primary_key=True)
    events = models.TextField(verbose_name="timer events", default="[]")

    objects = NodeTimerEventConfigManager()

    class Meta:
        verbose_name = _("节点时间事件配置 NodeTimerEventConfig")
        verbose_name_plural = _("节点时间事件配置 NodeTimerEventConfig")
        index_together = [("root_pipeline_id", "node_id")]

    def get_events(self) -> List[Dict[str, Any]]:
        return json.loads(self.events)

    def get_index__event_map(self) -> Dict[int, Dict[str, Any]]:
        return {event["index"]: event for event in self.get_events()}

    @classmethod
    def get_event_key(cls, node_id: str, version: str, event: Dict[str, Any]) -> str:
        """
        获取事件 Key
        :param node_id: 节点 ID
        :param version: State 版本
        :param event: 事件详情
        :return:
        """
        # zset 没有按字符串匹配模式批量删除 key 的支持，使用 key 的命名采用已检索的信息进行拼接
        # 之前想把 loop 也维护进去，发觉移除操作非常麻烦，故采用 incr 的方式，单独维护每个事件事件的触发次数
        key_prefix: str = f"{node_timer_event_settings.key_prefix}:node:{node_id}:version:{version}"
        return f"{key_prefix}:index:{event['index']}"

    @classmethod
    def get_next_expired_time(cls, event: Dict[str, Any], start: Optional[datetime.datetime] = None) -> float:
        """
        获取时间事件下一次过期时间
        :param event: 事件详情
        :param start: 开始时间，默认取 datetime.now()
        :return:
        """
        return parse_timer_defined(event["timer_type"], event["defined"], start=start or datetime.datetime.now())[
            "timestamp"
        ]

    @classmethod
    def add_to_pool(cls, redis_inst, node_id: str, version: str, event: Dict[str, Any]):
        key: str = cls.get_event_key(node_id, version, event)
        expired_time: float = cls.get_next_expired_time(event)

        # TODO 考虑 incr & zadd 合并，使用 lua 封装成原子操作
        loop: int = int(redis_inst.incr(key, 1))
        if loop > event["repetitions"]:
            logger.info(
                "[add_to_pool] No need to add: node -> %s, version -> %s, loop -> %s, event -> %s",
                node_id,
                version,
                loop,
                event,
            )
            return

        redis_inst.zadd(node_timer_event_settings.executing_pool, mapping={key: expired_time}, nx=True)

        logger.info(
            "[add_to_pool] add event to redis: "
            "node_id -> %s, version -> %s, event -> %s, key -> %s, expired_time -> %s",
            node_id,
            version,
            event,
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


class ExpiredNodesRecord(models.Model):
    id = models.BigAutoField(verbose_name="ID", primary_key=True)
    nodes = models.TextField(verbose_name="到期节点信息")

    class Meta:
        verbose_name = _("到期节点数据记录 ExpiredNodesRecord")
        verbose_name_plural = _("到期节点数据记录 ExpiredNodesRecord")
