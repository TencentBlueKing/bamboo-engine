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


def stalled_root_candidates(threshold_seconds, batch, now=None):
    """root 级 Max(last_heartbeat) 超阈值的存活流程，按最久静默升序。"""
    cutoff = stall_cutoff(threshold_seconds, now=now)
    rows = (
        Process.objects.filter(dead=False)
        .values("root_pipeline_id")
        .annotate(latest=Max("last_heartbeat"))
        .filter(latest__lt=cutoff)
        .order_by("latest")[:batch]
    )
    return [(row["root_pipeline_id"], row["latest"]) for row in rows]


def root_last_progress(root_pipeline_id):
    return (
        Process.objects.filter(root_pipeline_id=root_pipeline_id, dead=False)
        .aggregate(latest=Max("last_heartbeat"))
        .get("latest")
    )
