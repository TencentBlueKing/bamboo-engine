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

from django.db.models import Q

from pipeline.contrib.diagnostics.models import DiagnosticScanCursor

# 水位停在某个时间点、且该时间点上的行已全部处理时使用的 ID 水位
EXHAUSTED_ID = 2 ** 63 - 1


def chunks(items, size=500):
    items = list(items)
    for index in range(0, len(items), size):
        yield items[index : index + size]


def load_cursor(name):
    return DiagnosticScanCursor.objects.filter(name=name).first()


def save_cursor(name, position=None, position_id=0, extra=None):
    cursor, _ = DiagnosticScanCursor.objects.update_or_create(
        name=name,
        defaults={"position": position, "position_id": position_id, "extra": {} if extra is None else extra},
    )
    return cursor


def window_start(name, cutoff, lookback_seconds, start_override=None):
    """返回本轮扫描的起点 (时间, ID)：显式指定 > 已保存的水位 > cutoff 往前回看 lookback_seconds。"""
    if start_override is not None:
        return start_override, 0
    cursor = load_cursor(name)
    if cursor is not None and cursor.position is not None:
        return cursor.position, cursor.position_id
    return cutoff - timedelta(seconds=lookback_seconds), 0


def process_window_pages(queryset, start, start_id, end, page_size, max_rows):
    """按 (last_heartbeat, id) 键集分页，逐页产出 (start, start_id) 之后、end（含）之前的进程。

    累计读到 max_rows 行即停止，调用方用最后一行作为下一轮的水位。
    """
    queryset = queryset.filter(last_heartbeat__lte=end).order_by("last_heartbeat", "id")
    position, position_id, seen = start, start_id, 0
    while seen < max_rows:
        limit = min(page_size, max_rows - seen)
        page = list(
            queryset.filter(Q(last_heartbeat__gt=position) | Q(last_heartbeat=position, id__gt=position_id))[:limit]
        )
        if not page:
            return
        seen += len(page)
        yield page
        position, position_id = page[-1].last_heartbeat, page[-1].id
        if len(page) < limit:
            return
