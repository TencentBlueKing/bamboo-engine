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

from prometheus_client import Counter, Gauge, Histogram

from bamboo_engine.metrics import HOST_NAME

from pipeline.contrib.diagnostics import conf

logger = logging.getLogger(__name__)


def emit_alert_log(alert_type, root_pipeline_id, node_id="", payload=None):
    if not conf.alert_enabled():
        return

    logger.warning(
        "[pipeline_diagnostics_alert] type=%s root_pipeline_id=%s node_id=%s payload=%s",
        alert_type,
        root_pipeline_id,
        node_id,
        {} if payload is None else payload,
    )


DIAGNOSTICS_SCAN_ROWS = Counter(
    "pipeline_diagnostics_scan_rows", "rows read by diagnostics scanners", labelnames=["scanner", "hostname"]
)
DIAGNOSTICS_SCAN_HITS = Counter(
    "pipeline_diagnostics_scan_hits",
    "confirmed stuck shapes found by diagnostics scanners",
    labelnames=["scanner", "stuck_type", "hostname"],
)
DIAGNOSTICS_SCAN_CURSOR_LAG = Gauge(
    "pipeline_diagnostics_scan_cursor_lag",
    "cursor lag after a scan (seconds for time cursors, rows for id cursors)",
    labelnames=["scanner", "hostname"],
)
DIAGNOSTICS_DETECT_LATENCY = Histogram(
    "pipeline_diagnostics_detect_latency_seconds",
    "silence seconds of a stuck shape when its case is first opened",
    labelnames=["stuck_type", "hostname"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 21600, 86400, float("inf")),
)


def record_scan_report(report):
    """扫描结果的统一出口：一行结构化日志加指标。预演只打日志，不污染线上指标。"""
    try:
        logger.info(
            "[pipeline_diagnostics_scan] scanner=%s rows=%s candidates=%s hits=%s cases=%s lag=%s capped=%s "
            "dry_run=%s outcomes=%s",
            report.scanner,
            report.rows,
            report.candidates,
            len(report.hits),
            report.cases,
            report.cursor_lag_seconds,
            report.capped,
            report.dry_run,
            report.outcomes,
        )
        if report.dry_run:
            return
        DIAGNOSTICS_SCAN_ROWS.labels(scanner=report.scanner, hostname=HOST_NAME).inc(report.rows)
        lag = report.cursor_lag_seconds
        if lag is None:
            lag = report.outcomes.get("id_lag")
        if lag is not None:
            DIAGNOSTICS_SCAN_CURSOR_LAG.labels(scanner=report.scanner, hostname=HOST_NAME).set(lag)
        for _root_id, _node_id, hit in report.hits:
            DIAGNOSTICS_SCAN_HITS.labels(scanner=report.scanner, stuck_type=hit.type, hostname=HOST_NAME).inc()
    except Exception:
        logger.exception("[pipeline_diagnostics_scan] record report failed: %s", getattr(report, "scanner", ""))


def observe_hit(stuck_type, silent_seconds):
    try:
        DIAGNOSTICS_DETECT_LATENCY.labels(stuck_type=stuck_type, hostname=HOST_NAME).observe(max(silent_seconds, 0))
    except Exception:
        logger.exception("[pipeline_diagnostics_scan] observe hit failed: %s", stuck_type)


DIAGNOSTICS_RECOVERY = Counter(
    "pipeline_diagnostics_recovery",
    "diagnostics replays and their settled results",
    labelnames=["stuck_type", "trigger", "result", "hostname"],
)


def record_recovery(stuck_type, trigger, result):
    try:
        DIAGNOSTICS_RECOVERY.labels(stuck_type=stuck_type, trigger=trigger, result=result, hostname=HOST_NAME).inc()
    except Exception:
        logger.exception("[pipeline_diagnostics_recovery] record metric failed: %s", stuck_type)
