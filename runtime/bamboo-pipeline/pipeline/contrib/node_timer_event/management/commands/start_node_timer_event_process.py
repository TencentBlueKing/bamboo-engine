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
from pipeline.contrib.node_timer_event.models import ExpiredNodesRecord
from pipeline.contrib.node_timer_event.settings import node_timer_event_settings
from pipeline.contrib.node_timer_event.tasks import dispatch_expired_nodes

logger = logging.getLogger("root")


class Command(BaseCommand):
    help = "scanning expired nodes and dispatch them to celery task"
    has_killed = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._graceful_exit)
        redis_inst = node_timer_event_settings.redis_inst
        nodes_pool = node_timer_event_settings.executing_pool
        while not self.has_killed:
            try:
                start = time.time()
                self._pop_expired_nodes(redis_inst, nodes_pool)
                end = time.time()
                logger.info(f"[node_timeout_process] time consuming: {end-start}")
            except Exception as e:
                logger.exception(e)
            time.sleep(node_timer_event_settings.pool_scan_interval)

    def _graceful_exit(self, *args):
        self.has_killed = True

    def _pop_expired_nodes(self, redis_inst, nodes_pool) -> list:
        now = datetime.datetime.now().timestamp()
        expired_nodes = [
            node.decode("utf-8") if isinstance(node, bytes) else node
            for node in redis_inst.zrangebyscore(nodes_pool, "-inf", now)
        ]
        if expired_nodes:
            self.record_expired_nodes(expired_nodes)
            redis_inst.zrem(nodes_pool, *expired_nodes)
        return expired_nodes

    @staticmethod
    def record_expired_nodes(timeout_nodes: list):
        # 处理因为过长时间没有访问导致的链接失效问题
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

        record = ExpiredNodesRecord.objects.create(nodes=json.dumps(timeout_nodes))
        if node_timer_event_settings.dispatch_queue is None:
            dispatch_expired_nodes.apply_async(kwargs={"record_id": record.id})
        else:
            dispatch_expired_nodes.apply_async(
                kwargs={"record_id": record.id},
                queue=node_timer_event_settings.dispatch_queue,
                routing_key=node_timer_event_settings.dispatch_queue,
            )
