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
    return _get_setting("APPLY_ENABLED", True)


def batch_operation_enabled():
    return _get_setting("BATCH_OPERATION_ENABLED", False)


def event_retention_days():
    return _get_setting("EVENT_RETENTION_DAYS", 30)


def case_retention_days():
    return _get_setting("CASE_RETENTION_DAYS", 365)


def audit_retention_days():
    return _get_setting("AUDIT_RETENTION_DAYS", 365)
