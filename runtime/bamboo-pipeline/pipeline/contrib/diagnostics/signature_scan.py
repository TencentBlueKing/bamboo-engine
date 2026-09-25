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

import time

from django.db.models import Q
from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.case_types import PROCESS_SIGNATURE_TYPES
from pipeline.contrib.diagnostics.cases import upsert_case
from pipeline.contrib.diagnostics.cursor import EXHAUSTED_ID, chunks, process_window_pages, save_cursor, window_start
from pipeline.contrib.diagnostics.metrics import observe_hit, record_scan_report
from pipeline.contrib.diagnostics.progress import stall_cutoff
from pipeline.contrib.diagnostics.signatures import (
    build_context,
    close_resolved_signature_cases,
    evaluate,
    hit_identity,
)
from pipeline.contrib.diagnostics.types import ScanReport
from pipeline.eri.models import Process

TIER_FAST = "signature_fast"
TIER_SLOW = "signature_slow"
# S1 按节点完成时间判静默，完成时间比心跳晚一段调度处理耗时；快档窗口多留一分钟，
# 让处理耗时在一分钟内的 S1 在快档读到它的那一轮就已满足阈值
FAST_WINDOW_GRACE_SECONDS = 60


def _candidates():
    # 存活进程只看睡眠中的（运行中的由窗口扫描兜底）；已结束的子进程用来发现父进程没被唤醒
    return Process.objects.defer("pipeline_stack").filter(Q(dead=False, asleep=True) | Q(dead=True, parent_id__gt=0))


def _confirm(found, confirm_seconds, now):
    """等待 confirm_seconds 后按最新数据重判，只保留形态与心跳都没变的命中，剔除消息还在路上的情况。"""
    if not found:
        return []
    if confirm_seconds:
        time.sleep(confirm_seconds)
    beats = {process.id: process.last_heartbeat for process, _hit in found}
    wanted = {hit_identity(hit) for _process, hit in found}
    fresh = []
    for chunk in chunks(beats):
        fresh.extend(_candidates().filter(id__in=chunk))
    confirmed, seen = [], set()
    for process, hit in evaluate(fresh, build_context(fresh, now=now), slow=True):
        identity = hit_identity(hit)
        if identity in wanted and identity not in seen and process.last_heartbeat == beats.get(process.id):
            seen.add(identity)
            confirmed.append((process, hit))
    return confirmed


def _scan_tier(name, threshold_seconds, slow, now, dry_run, max_rows, confirm_seconds, start_override):
    cutoff = stall_cutoff(threshold_seconds, now=now)
    start, start_id = window_start(name, cutoff, conf.scan_initial_lookback_seconds(), start_override)
    rows, last, found = 0, None, []
    for page in process_window_pages(_candidates(), start, start_id, cutoff, conf.scan_page_size(), max_rows):
        rows += len(page)
        last = page[-1]
        found.extend(evaluate(page, build_context(page, now=now), slow=slow))
    capped = rows >= max_rows
    confirmed = _confirm(found, confirm_seconds, now)

    hits, cases = [], 0
    for process, hit in confirmed:
        root_id, node_id = hit.related_objects["root_pipeline_id"], hit.related_objects["node_id"]
        hits.append((root_id, node_id, hit))
        if dry_run:
            continue
        case = upsert_case(root_id, node_id, hit)
        if case is not None:
            cases += 1
            if case.hit_count == 1:
                observe_hit(hit.type, (now - process.last_heartbeat).total_seconds())

    if capped:
        position, position_id = last.last_heartbeat, last.id
        lag = int((cutoff - last.last_heartbeat).total_seconds())
    else:
        position, position_id, lag = cutoff, EXHAUSTED_ID, 0
    if not dry_run:
        save_cursor(name, position=position, position_id=position_id)
    return ScanReport(name, rows, len(found), hits, cases, lag, capped, dry_run, {})


def scan_signatures(
    now=None, dry_run=False, max_rows=None, confirm_seconds=None, start_override=None, force=False, tiers=None
):
    """快档（心跳刚跨过快档阈值加一分钟，默认 5+1 分钟）查 S1/S2/S5/S6，慢档（跨过 30 分钟）再查一遍并加上 S3。

    每个进程在每一档只在跨线那一轮被检查一次；跨线之后才出现的形态由慢档或窗口扫描兜底。
    """
    if not (force or conf.signature_scan_enabled()):
        return []
    now = now or timezone.now()
    max_rows = conf.scan_max_rows() if max_rows is None else max_rows
    confirm_seconds = conf.second_confirm_seconds() if confirm_seconds is None else confirm_seconds
    plan = [
        (TIER_FAST, conf.signature_fast_threshold_seconds() + FAST_WINDOW_GRACE_SECONDS, False),
        (TIER_SLOW, conf.signature_slow_threshold_seconds(), True),
    ]
    reports = [
        _scan_tier(name, threshold, slow, now, dry_run, max_rows, confirm_seconds, start_override)
        for name, threshold, slow in plan
        if not tiers or name in tiers
    ]
    if not dry_run and reports:
        reports[0].outcomes["closed"] = close_resolved_signature_cases(PROCESS_SIGNATURE_TYPES, now=now)
    for report in reports:
        record_scan_report(report)
    return reports
