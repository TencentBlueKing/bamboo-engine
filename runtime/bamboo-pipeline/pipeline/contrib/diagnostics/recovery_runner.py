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
from collections import Counter, namedtuple

from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.case_types import REPLAYABLE_CASE_TYPES
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticRecovery
from pipeline.contrib.diagnostics.recovery import plan_replay, record, settle_recoveries

logger = logging.getLogger(__name__)

RecoveryReport = namedtuple("RecoveryReport", ["cases", "outcomes"])


def _preview(plan, outcomes):
    """同一案例同一指纹只记一行预演。"""
    seen = DiagnosticRecovery.objects.filter(
        case=plan.case, fingerprint=plan.fingerprint, mode=DiagnosticRecovery.MODE_PREVIEW
    ).exists()
    if seen:
        outcomes["seen"] += 1
        return
    status = DiagnosticRecovery.STATUS_BLOCKED if plan.blockers else DiagnosticRecovery.STATUS_PREVIEWED
    detail = {"blockers": list(plan.blockers)}
    record(plan, DiagnosticRecovery.TRIGGER_AUTO, DiagnosticRecovery.MODE_PREVIEW, status, detail=detail)
    outcomes[status] += 1


def run_recovery(now=None, force=False):
    """恢复任务的一轮：先复核到期的记录，再预演未关闭的可重放案例。"""
    if not (force or conf.recovery_enabled()):
        return None
    now = now or timezone.now()
    outcomes = Counter(settle_recoveries(now=now))
    cases = list(
        DiagnosticCase.objects.filter(
            status=DiagnosticCase.STATUS_OPEN, stuck_type__in=list(REPLAYABLE_CASE_TYPES)
        ).order_by("-first_seen_at", "-id")[: conf.recovery_batch()]
    )
    for case in cases:
        try:
            plan = plan_replay(case, trigger=DiagnosticRecovery.TRIGGER_AUTO, now=now)
            if not plan.fingerprint:
                outcomes["shape_gone"] += 1
                continue
            _preview(plan, outcomes)
        except Exception:
            logger.exception("[pipeline_diagnostics_recovery] case %s failed", case.id)
            outcomes["error"] += 1
    report = RecoveryReport(len(cases), dict(outcomes))
    logger.info("[pipeline_diagnostics_recovery] cases=%s outcomes=%s", report.cases, report.outcomes)
    return report


def recovery_report(since):
    """按形态汇总 since 之后的台账：预演结果、阻断原因、不重放也自愈的比例、执行结果。"""
    grouped = {}
    rows = DiagnosticRecovery.objects.filter(created_at__gte=since).values_list(
        "stuck_type", "mode", "status", "message", "detail"
    )
    for stuck_type, mode, status, message, detail in rows.iterator():
        item = grouped.setdefault(
            stuck_type, {"preview": Counter(), "blockers": Counter(), "settled": Counter(), "apply": Counter()}
        )
        detail = detail or {}
        if mode == DiagnosticRecovery.MODE_APPLY:
            item["apply"][status] += 1
            continue
        item["preview"][status] += 1
        item["blockers"].update(detail.get("blockers") or [])
        if message and "settled_holds" in detail:
            item["settled"]["holds" if detail["settled_holds"] else "healed"] += 1
    report = {}
    for stuck_type, item in grouped.items():
        settled = sum(item["settled"].values())
        report[stuck_type] = {name: dict(counter) for name, counter in item.items()}
        report[stuck_type]["self_heal_ratio"] = round(item["settled"]["healed"] / settled, 3) if settled else None
    return report
