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
from datetime import timedelta

from django.utils import timezone
from django.utils.module_loading import import_string

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.case_types import REPLAYABLE_CASE_TYPES
from pipeline.contrib.diagnostics.metrics import emit_alert_log, record_breaker_open, record_recovery
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticRecovery
from pipeline.contrib.diagnostics.recovery import (
    BLOCKER_IN_FLIGHT,
    apply_plan,
    plan_replay,
    record,
    settle_recoveries,
)

logger = logging.getLogger(__name__)

RECOVERY_MODE_APPLY = "apply"
REPORT_GROUPS = ("preview", "blockers", "settled", "apply", "auto_apply")

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


class AutoReplay(object):
    """一轮恢复任务里自动重放的范围与剩余额度。"""

    def __init__(self, types, resolver, budget):
        self.types = types
        self.resolver = resolver
        self.budget = budget
        self._scopes = {}

    def covers(self, case):
        if case.stuck_type not in self.types:
            return False
        root_id = case.root_pipeline_id
        if root_id not in self._scopes:
            try:
                self._scopes[root_id] = bool(self.resolver(root_id))
            except Exception:
                logger.exception("[pipeline_diagnostics_recovery] scope resolver failed: %s", root_id)
                self._scopes[root_id] = False
        return self._scopes[root_id]


def _scope_resolver():
    path = conf.recovery_scope_resolver()
    if not path:
        logger.warning("[pipeline_diagnostics_recovery] auto replay skipped: scope resolver is not configured")
        return None
    try:
        return import_string(path)
    except ImportError:
        logger.exception("[pipeline_diagnostics_recovery] auto replay skipped: cannot import %s", path)
        return None


def _breaker_open(now):
    window = conf.recovery_breaker_window_seconds()
    threshold = conf.recovery_breaker_threshold()
    opened = DiagnosticCase.objects.filter(
        stuck_type__in=list(REPLAYABLE_CASE_TYPES), created_at__gte=now - timedelta(seconds=window)
    ).count()
    if opened <= threshold:
        return False
    emit_alert_log(
        "recovery_breaker_open", "", payload={"cases": opened, "window_seconds": window, "threshold": threshold}
    )
    record_breaker_open()
    return True


def _auto_replay(now, outcomes):
    """本轮的自动重放范围：模式为 apply、形态开关非空、配置了范围判定且没有熔断，否则返回 None（只预演）。"""
    if conf.recovery_mode() != RECOVERY_MODE_APPLY:
        return None
    types = conf.auto_replay_types().intersection(REPLAYABLE_CASE_TYPES)
    if not types:
        return None
    resolver = _scope_resolver()
    if resolver is None:
        return None
    if _breaker_open(now):
        outcomes["breaker_open"] += 1
        return None
    return AutoReplay(types, resolver, conf.recovery_max_per_round())


def _manual_required(plan, attempts):
    case = plan.case
    trigger, status = DiagnosticRecovery.TRIGGER_AUTO, DiagnosticRecovery.STATUS_MANUAL_REQUIRED
    record(plan, trigger, DiagnosticRecovery.MODE_APPLY, status, detail={"attempts": attempts})
    record_recovery(case.stuck_type, trigger, status)
    payload = {"case_id": case.id, "stuck_type": case.stuck_type, "fingerprint": plan.fingerprint, "attempts": attempts}
    emit_alert_log("recovery_manual_required", case.root_pipeline_id, case.node_id, payload=payload)


def _replay(plan, auto, now, outcomes):
    """范围内的案例：有其他阻断时按预演记下原因；等复核、限次、间隔、每轮上限都满足才派发。"""
    if [blocker for blocker in plan.blockers if blocker != BLOCKER_IN_FLIGHT]:
        _preview(plan, outcomes)
        return
    if plan.blockers:
        outcomes["auto_waiting"] += 1
        return
    attempts = DiagnosticRecovery.objects.filter(
        case=plan.case,
        fingerprint=plan.fingerprint,
        trigger=DiagnosticRecovery.TRIGGER_AUTO,
        mode=DiagnosticRecovery.MODE_APPLY,
    )
    if attempts.filter(status=DiagnosticRecovery.STATUS_MANUAL_REQUIRED).exists():
        outcomes["auto_exhausted"] += 1
        return
    tried = list(attempts.values_list("created_at", flat=True))
    if len(tried) >= conf.recovery_max_attempts():
        _manual_required(plan, len(tried))
        outcomes[DiagnosticRecovery.STATUS_MANUAL_REQUIRED] += 1
        return
    if tried and max(tried) > now - timedelta(seconds=conf.recovery_settle_seconds()):
        outcomes["auto_waiting"] += 1
        return
    if auto.budget <= 0:
        outcomes["auto_deferred"] += 1
        return
    auto.budget -= 1
    _recovery, error = apply_plan(plan, DiagnosticRecovery.TRIGGER_AUTO)
    outcomes["auto_failed" if error else "auto_dispatched"] += 1


def run_recovery(now=None, force=False):
    """恢复任务的一轮：先复核到期的记录，再处理未关闭的可重放案例，自动重放范围内的派发，其余只预演。"""
    if not (force or conf.recovery_enabled()):
        return None
    now = now or timezone.now()
    outcomes = Counter(settle_recoveries(now=now))
    try:
        auto = _auto_replay(now, outcomes)
    except Exception:
        logger.exception("[pipeline_diagnostics_recovery] auto replay skipped: scope setup failed")
        auto = None
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
            elif auto is not None and auto.covers(case):
                _replay(plan, auto, now, outcomes)
            else:
                _preview(plan, outcomes)
        except Exception:
            logger.exception("[pipeline_diagnostics_recovery] case %s failed", case.id)
            outcomes["error"] += 1
    report = RecoveryReport(len(cases), dict(outcomes))
    logger.info("[pipeline_diagnostics_recovery] cases=%s outcomes=%s", report.cases, report.outcomes)
    return report


def recovery_report(since):
    """按形态汇总 since 之后的台账：预演结果、阻断原因、不重放也自愈的比例、执行结果（auto_apply 是其中自动重放的部分）。"""
    grouped = {}
    rows = DiagnosticRecovery.objects.filter(created_at__gte=since).values_list(
        "stuck_type", "trigger", "mode", "status", "message", "detail"
    )
    for stuck_type, trigger, mode, status, message, detail in rows.iterator():
        item = grouped.setdefault(stuck_type, {name: Counter() for name in REPORT_GROUPS})
        detail = detail or {}
        if mode == DiagnosticRecovery.MODE_APPLY:
            item["apply"][status] += 1
            if trigger == DiagnosticRecovery.TRIGGER_AUTO:
                item["auto_apply"][status] += 1
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
