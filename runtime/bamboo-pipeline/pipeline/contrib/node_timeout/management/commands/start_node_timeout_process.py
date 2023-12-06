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
import datetime
import json
import logging
import signal
import time

from django.core.management import BaseCommand
from django.db import connections
from pipeline.contrib.node_timeout.models import TimeoutNodesRecord
from pipeline.contrib.node_timeout.settings import node_timeout_settings
from pipeline.contrib.node_timeout.tasks import dispatch_timeout_nodes

logger = logging.getLogger("root")


class Command(BaseCommand):
    help = "scanning timeout nodes and dispatch them to celery task"
    has_killed = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._graceful_exit)
        redis_inst = node_timeout_settings.redis_inst
        nodes_pool = node_timeout_settings.executing_pool
        while not self.has_killed:
            try:
                start = time.time()
                self._pop_timeout_nodes(redis_inst, nodes_pool)
                end = time.time()
                logger.info(f"[node_timeout_process] time consuming: {end-start}")
            except Exception as e:
                logger.exception(e)
            time.sleep(1)

    def _graceful_exit(self, *args):
        self.has_killed = True

    def _pop_timeout_nodes(self, redis_inst, nodes_pool) -> list:
        now = datetime.datetime.now().timestamp()
        timeout_nodes = [
            node.decode("utf-8") if isinstance(node, bytes) else node
            for node in redis_inst.zrangebyscore(nodes_pool, "-inf", now)
        ]
        if timeout_nodes:
            self.record_timeout_nodes(timeout_nodes)
            redis_inst.zrem(nodes_pool, *timeout_nodes)
        return timeout_nodes

    @staticmethod
    def record_timeout_nodes(timeout_nodes: list):
        # 处理因为过长时间没有访问导致的链接失效问题
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

        record = TimeoutNodesRecord.objects.create(timeout_nodes=json.dumps(timeout_nodes))
        if node_timeout_settings.dispatch_queue is None:
            dispatch_timeout_nodes.apply_async(kwargs={"record_id": record.id})
        else:
            dispatch_timeout_nodes.apply_async(
                kwargs={"record_id": record.id},
                queue=node_timeout_settings.dispatch_queue,
                routing_key=node_timeout_settings.dispatch_queue,
            )
