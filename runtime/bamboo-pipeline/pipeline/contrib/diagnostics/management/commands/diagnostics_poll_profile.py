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
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bamboo_engine.eri import ScheduleType

from pipeline.contrib.diagnostics.cursor import chunks
from pipeline.engine import states
from pipeline.eri.models import Node, Process, Schedule, State


def _percentile(values, percent):
    return int(values[min(len(values) - 1, int(len(values) * percent / 100))])


class Command(BaseCommand):
    help = "只读：按插件 code 统计当前正在轮询的节点距上次轮询的静默时长，用来设定 S3 阈值与排除清单"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="只看心跳在这么多天内的进程，排除历史遗留")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--max-rows", type=int, default=20000, dest="max_rows")

    def handle(self, *args, **options):
        now = timezone.now()
        since = now - timedelta(days=options.get("days") or 7)
        processes = Process.objects.filter(dead=False, asleep=True, last_heartbeat__gte=since).only(
            "id", "current_node_id", "last_heartbeat"
        )
        by_node = {
            process.current_node_id: process
            for process in processes.order_by("-last_heartbeat")[: options.get("max_rows") or 20000]
            if process.current_node_id
        }

        state_map, code_map, schedule_map = {}, {}, {}
        for chunk in chunks(by_node):
            for state in State.objects.filter(node_id__in=chunk, name=states.RUNNING):
                state_map[state.node_id] = state
            for node in Node.objects.filter(node_id__in=chunk):
                code_map.setdefault(node.node_id, json.loads(node.detail).get("code", ""))
            for schedule in Schedule.objects.filter(
                node_id__in=chunk, type=ScheduleType.POLL.value, finished=False, expired=False
            ):
                schedule_map[(schedule.node_id, schedule.version)] = schedule

        profile = defaultdict(list)
        for node_id, process in by_node.items():
            state = state_map.get(node_id)
            schedule = schedule_map.get((node_id, state.version)) if state is not None else None
            if schedule is None or schedule.schedule_times < 1:
                continue
            silent = (now - process.last_heartbeat).total_seconds()
            interval = None
            if state.started_time is not None:
                interval = (now - state.started_time).total_seconds() / schedule.schedule_times
            profile[code_map.get(node_id, "")].append((silent, interval))

        self.stdout.write("code count silent_p50 silent_p90 silent_max avg_interval")
        ranked = sorted(profile.items(), key=lambda item: -len(item[1]))[: options.get("limit") or 50]
        for code, samples in ranked:
            silents = sorted(silent for silent, _interval in samples)
            intervals = [interval for _silent, interval in samples if interval is not None]
            self.stdout.write(
                "{} {} {} {} {} {}".format(
                    code or "-",
                    len(samples),
                    _percentile(silents, 50),
                    _percentile(silents, 90),
                    int(silents[-1]),
                    int(sum(intervals) / len(intervals)) if intervals else "-",
                )
            )
