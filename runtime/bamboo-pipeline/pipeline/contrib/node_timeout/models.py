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

from django.db import models
from django.utils.translation import ugettext_lazy as _

from pipeline.core.constants import PE


logger = logging.getLogger(__name__)


class TimeoutNodeConfigManager(models.Manager):
    def parse_node_timeout_configs(self, pipeline_tree: dict) -> list:
        configs = []
        for act_id, act in pipeline_tree[PE.activities].items():
            if act["type"] == PE.SubProcess:
                result = self.parse_node_timeout_configs(act[PE.pipeline])
                if not result["result"]:
                    return result
                configs.extend(result["data"])
            elif act["type"] == PE.ServiceActivity:
                timeout_config = act.get("timeout_config", {})
                enable = timeout_config.get("enable")
                if not enable:
                    continue
                timeout_seconds = timeout_config.get("seconds")
                action = timeout_config.get("action")
                if not timeout_seconds or not isinstance(timeout_seconds, int):
                    logger.error(
                        f"[parse_node_timeout_configs] node [{act_id}] timeout "
                        f"config seconds [{timeout_seconds}] is invalid"
                    )
                    # 对于不符合格式要求的情况，则不设置对应超时时间
                    continue
                configs.append({"action": action, "node_id": act_id, "timeout": timeout_seconds})
        return {"result": True, "data": configs, "message": ""}

    def batch_create_node_timeout_config(self, root_pipeline_id: str, pipeline_tree: dict):
        """批量创建节点超时配置"""

        config_parse_result = self.parse_node_timeout_configs(pipeline_tree)
        # 这里忽略解析失败的情况，保证即使解析失败也能正常创建任务
        if not config_parse_result["result"]:
            logger.error(
                f'[batch_create_node_timeout_config] parse node timeout config failed: {config_parse_result["result"]}'
            )
            return config_parse_result
        configs = config_parse_result["data"] or []
        config_objs = [
            TimeoutNodeConfig(
                action=config["action"],
                root_pipeline_id=root_pipeline_id,
                node_id=config["node_id"],
                timeout=config["timeout"],
            )
            for config in configs
        ]
        objs = self.bulk_create(config_objs, batch_size=1000)
        return {"result": True, "data": objs, "message": ""}


class TimeoutNodeConfig(models.Model):
    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    action = models.CharField(verbose_name="action", max_length=32)
    node_id = models.CharField(verbose_name="task node id", max_length=64, primary_key=True)
    timeout = models.IntegerField(verbose_name="node timeout time")

    objects = TimeoutNodeConfigManager()

    class Meta:
        verbose_name = _("节点超时配置 TimeoutNodeConfig")
        verbose_name_plural = _("节点超时配置 TimeoutNodeConfig")
        index_together = [("root_pipeline_id", "node_id")]


class TimeoutNodesRecord(models.Model):
    id = models.BigAutoField(verbose_name="ID", primary_key=True)
    timeout_nodes = models.TextField(verbose_name="超时节点信息")

    class Meta:
        verbose_name = _("超时节点数据记录 TimeoutNodesRecord")
        verbose_name_plural = _("超时节点数据记录 TimeoutNodesRecord")
