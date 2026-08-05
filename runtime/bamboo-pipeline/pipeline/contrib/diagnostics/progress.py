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

from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from pipeline.eri.models import Process


def stall_cutoff(threshold_seconds, now=None):
    now = now or timezone.now()
    return now - timedelta(seconds=threshold_seconds)


def stalled_root_candidates(threshold_seconds, batch, now=None, max_silent_seconds=None):
    """root 级 Max(last_heartbeat) 落在 [now-max_silent, now-threshold) 的存活流程，按最近静默优先。

    上界的作用：线上存在大量心跳停在数百天前的历史遗留 root（撤销、库迁移、早期版本残留），
    没有上界时它们会长期占满 batch，导致刚刚静默的 root 永远排不进本轮取样（队头阻塞）。

    排序方向为倒序：每一轮优先取刚跨过阈值的 root，保证新出现的停滞能被及时立案；
    窗口内的历史积压交给一次性回扫处理，不占用周期任务的名额。
    """
    cutoff = stall_cutoff(threshold_seconds, now=now)
    queryset = Process.objects.filter(dead=False)
    if max_silent_seconds:
        # 先按行过滤再分组：root 的 Max 只可能来自 >= floor 的行，语义与分组后再判上界等价，
        # 但能借 last_heartbeat 索引把参与分组的行数压下来。
        queryset = queryset.filter(last_heartbeat__gte=stall_cutoff(max_silent_seconds, now=now))
    rows = (
        queryset.values("root_pipeline_id")
        .annotate(latest=Max("last_heartbeat"))
        .filter(latest__lt=cutoff)
        .order_by("-latest")[:batch]
    )
    return [(row["root_pipeline_id"], row["latest"]) for row in rows]


def root_last_progress(root_pipeline_id):
    return (
        Process.objects.filter(root_pipeline_id=root_pipeline_id, dead=False)
        .aggregate(latest=Max("last_heartbeat"))
        .get("latest")
    )
