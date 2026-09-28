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

from django.conf import settings


def _get_setting(name, default):
    return getattr(settings, "PIPELINE_DIAGNOSTICS_{}".format(name), default)


def event_enabled():
    return _get_setting("EVENT_ENABLED", True)


def scan_enabled():
    return _get_setting("SCAN_ENABLED", True)


def case_enabled():
    return _get_setting("CASE_ENABLED", True)


def alert_enabled():
    return _get_setting("ALERT_ENABLED", True)


def apply_enabled():
    return _get_setting("APPLY_ENABLED", False)  # M1: 默认关闭写操作


def stall_threshold_seconds():
    return _get_setting("STALL_THRESHOLD_SECONDS", 1800)


def scan_max_silent_seconds():
    """周期扫描的静默上界，超过该时长的 root 视为历史遗留，不再进入取样池。0 表示不设上界。"""
    return _get_setting("SCAN_MAX_SILENT_SECONDS", 7 * 24 * 3600)


def scan_batch():
    return _get_setting("SCAN_BATCH", 200)


def second_confirm_seconds():
    return _get_setting("SECOND_CONFIRM_SECONDS", 3)


def batch_operation_enabled():
    return _get_setting("BATCH_OPERATION_ENABLED", False)


def event_retention_days():
    return _get_setting("EVENT_RETENTION_DAYS", 30)


def case_retention_days():
    return _get_setting("CASE_RETENTION_DAYS", 365)


def audit_retention_days():
    return _get_setting("AUDIT_RETENTION_DAYS", 365)


def _split(value):
    if isinstance(value, str):
        value = value.split(",")
    return [str(item).strip() for item in (value or ()) if str(item).strip()]


def window_scan_enabled():
    return _get_setting("WINDOW_SCAN_ENABLED", False)


def window_tiers_seconds():
    """静默窗口扫描的阈值档位（秒），升序；接受元组、列表或逗号分隔的字符串。"""
    return tuple(sorted(int(item) for item in _split(_get_setting("WINDOW_TIERS", (3600, 86400)))))


def signature_scan_enabled():
    return _get_setting("SIGNATURE_SCAN_ENABLED", False)


def signature_fast_threshold_seconds():
    return _get_setting("SIGNATURE_FAST_THRESHOLD_SECONDS", 300)


def signature_slow_threshold_seconds():
    return _get_setting("SIGNATURE_SLOW_THRESHOLD_SECONDS", 1800)


def poll_exclude_codes():
    """轮询续派（S3）不检查的插件 code，例如轮询间隔天然很长的定时插件。"""
    return frozenset(_split(_get_setting("POLL_EXCLUDE_CODES", ())))


def signature_close_batch():
    return _get_setting("SIGNATURE_CLOSE_BATCH", 500)


def callback_scan_enabled():
    return _get_setting("CALLBACK_SCAN_ENABLED", False)


def callback_confirm_seconds():
    """回调持续未被消费多久才立案；要长于引擎回调锁重试的总时长（约 19 秒）。"""
    return _get_setting("CALLBACK_CONFIRM_SECONDS", 120)


def callback_pending_max_seconds():
    return _get_setting("CALLBACK_PENDING_MAX_SECONDS", 1800)


def callback_pending_limit():
    return _get_setting("CALLBACK_PENDING_LIMIT", 5000)


def callback_max_rows():
    return _get_setting("CALLBACK_MAX_ROWS", 5000)


def scan_page_size():
    return _get_setting("SCAN_PAGE_SIZE", 500)


def scan_max_rows():
    return _get_setting("SCAN_MAX_ROWS", 20000)


def window_max_roots():
    """静默窗口扫描每档每轮最多处理的静默 root 数；攒够就停在当前页末尾，剩下的行留给下一轮。"""
    return _get_setting("WINDOW_MAX_ROOTS", 1000)


def scan_initial_lookback_seconds():
    """水位表里还没有记录时，首轮只回看这么久；更早的存量用预演命令单独看。"""
    return _get_setting("SCAN_INITIAL_LOOKBACK_SECONDS", 3600)


def recovery_enabled():
    return _get_setting("RECOVERY_ENABLED", False)


def recovery_settle_seconds():
    """重放派发后等多久再复核形态；要长于执行、调度消息正常排队和处理的时长。"""
    return _get_setting("RECOVERY_SETTLE_SECONDS", 180)


def recovery_batch():
    """恢复任务每轮最多检查的案例数和复核的记录数。"""
    return _get_setting("RECOVERY_BATCH", 200)
