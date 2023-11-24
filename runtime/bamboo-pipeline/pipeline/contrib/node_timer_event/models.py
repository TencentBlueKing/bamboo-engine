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
import json
import logging
import re
import typing
from typing import Any, Dict, List, Optional

from django.db import models
from django.utils.translation import ugettext_lazy as _
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

                if treated_timer_events:
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

        configs: List[Dict[str, Any]] = config_parse_result["data"]
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


class ExpiredNodesRecord(models.Model):
    id = models.BigAutoField(verbose_name="ID", primary_key=True)
    nodes = models.TextField(verbose_name="到期节点信息")

    class Meta:
        verbose_name = _("到期节点数据记录 ExpiredNodesRecord")
        verbose_name_plural = _("到期节点数据记录 ExpiredNodesRecord")
