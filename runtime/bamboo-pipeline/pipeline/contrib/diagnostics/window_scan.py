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

from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.cases import close_stale_cases, upsert_case
from pipeline.contrib.diagnostics.collector import collect_runtime_snapshot
from pipeline.contrib.diagnostics.cursor import EXHAUSTED_ID, chunks, process_window_pages, save_cursor, window_start
from pipeline.contrib.diagnostics.metrics import observe_hit, record_scan_report
from pipeline.contrib.diagnostics.progress import inactive_roots, root_last_activity, stall_cutoff
from pipeline.contrib.diagnostics.rules import diagnose_snapshot
from pipeline.contrib.diagnostics.scanner import _node_id_for_hit
from pipeline.contrib.diagnostics.types import ScanReport
from pipeline.eri.models import Process


def cursor_name(threshold_seconds):
    return "silence_window_{}".format(threshold_seconds)


def _silent_crossings(start, start_id, cutoff, max_rows, max_roots):
    """按页读心跳跨过 cutoff 的进程，随读随判静默；已结束的进程也参与，原因见 root_last_activity。

    静默 root 攒够 max_roots 就停在当前页末尾并按截断处理，水位停在已读的最后一行，剩下的行留给下一轮。
    """
    roots, silent, rows, last = set(), {}, 0, None
    queryset = Process.objects.only("id", "root_pipeline_id", "last_heartbeat")
    for page in process_window_pages(queryset, start, start_id, cutoff, conf.scan_page_size(), max_rows):
        rows += len(page)
        last = page[-1]
        new_roots = {process.root_pipeline_id for process in page} - roots
        roots.update(new_roots)
        silent.update(_silent_roots(new_roots, cutoff))
        if len(silent) >= max_roots:
            return roots, silent, rows, last, True
    return roots, silent, rows, last, rows >= max_rows


def _silent_roots(roots, cutoff):
    silent = {}
    for chunk in chunks(roots):
        inactive = inactive_roots(chunk)
        for root_id, (latest, live) in root_last_activity(chunk).items():
            if root_id not in inactive and live and latest is not None and latest <= cutoff:
                silent[root_id] = latest
    return silent


def _confirm(silent, confirm_seconds):
    if not confirm_seconds or not silent:
        return dict(silent)
    time.sleep(confirm_seconds)
    confirmed = {}
    for chunk in chunks(silent):
        for root_id, (latest, live) in root_last_activity(chunk).items():
            if live and latest == silent[root_id]:
                confirmed[root_id] = latest
    return confirmed


def scan_silence_window(
    threshold_seconds, now=None, confirm_seconds=None, max_rows=None, dry_run=False, start_override=None
):
    """只看心跳在上一轮水位到本轮 cutoff 之间跨线的 root，不做全表分组；每轮处理的静默 root 数有上限，超出的留给下一轮。"""
    now = now or timezone.now()
    confirm_seconds = conf.second_confirm_seconds() if confirm_seconds is None else confirm_seconds
    max_rows = conf.scan_max_rows() if max_rows is None else max_rows
    name = cursor_name(threshold_seconds)
    cutoff = stall_cutoff(threshold_seconds, now=now)
    start, start_id = window_start(name, cutoff, conf.scan_initial_lookback_seconds(), start_override)

    roots, silent, rows, last, capped = _silent_crossings(start, start_id, cutoff, max_rows, conf.window_max_roots())
    confirmed = _confirm(silent, confirm_seconds)

    hits, cases = [], 0
    for root_id, latest in confirmed.items():
        stall_seconds = int((now - latest).total_seconds())
        snapshot = collect_runtime_snapshot(root_pipeline_id=root_id, include_callback_data=False)
        for hit in diagnose_snapshot(snapshot, stall_seconds=stall_seconds):
            node_id = _node_id_for_hit(hit, snapshot.node_id)
            hits.append((root_id, node_id, hit))
            if dry_run:
                continue
            case = upsert_case(root_id, node_id, hit)
            if case is not None:
                cases += 1
                if case.hit_count == 1:
                    observe_hit(hit.type, stall_seconds)

    if capped:
        position, position_id = last.last_heartbeat, last.id
        lag = int((cutoff - last.last_heartbeat).total_seconds())
    else:
        position, position_id, lag = cutoff, EXHAUSTED_ID, 0
    if not dry_run and start_override is None:
        # 指定起点是人工补扫，写水位会让原水位与指定起点之间的行永远扫不到
        save_cursor(name, position=position, position_id=position_id)

    report = ScanReport(
        scanner=name,
        rows=rows,
        candidates=len(silent),
        hits=hits,
        cases=cases,
        cursor_lag_seconds=lag,
        capped=capped,
        dry_run=dry_run,
        outcomes={"roots": len(roots), "confirmed": len(confirmed)},
    )
    record_scan_report(report)
    return report


def scan_silence_windows(now=None, dry_run=False, force=False):
    """按配置的各档阈值依次扫描，返回各档的 ScanReport；开关关闭时什么都不做（force 供命令预演使用）。"""
    if not (force or conf.window_scan_enabled()):
        return []
    now = now or timezone.now()
    tiers = conf.window_tiers_seconds()
    reports = [scan_silence_window(tier, now=now, dry_run=dry_run) for tier in tiers]
    if not dry_run and tiers:
        # 只能按最短档关闭：按长档阈值关闭，会把 root 静默超过短档、未到长档的案例误判为已恢复
        close_stale_cases(tiers[0], now=now)
    return reports
