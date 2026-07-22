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

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.models import DiagnosticEvent

logger = logging.getLogger(__name__)


def emit_event(
    event_type,
    root_pipeline_id,
    node_id="",
    version="",
    result="",
    reason="",
    payload=None,
    **kwargs
):
    if not conf.event_enabled():
        return None

    try:
        return DiagnosticEvent.objects.create(
            event_type=event_type,
            root_pipeline_id=root_pipeline_id,
            node_id=node_id,
            version=version,
            result=result,
            reason=reason,
            payload={} if payload is None else payload,
            process_id=kwargs.get("process_id"),
            schedule_id=kwargs.get("schedule_id"),
            callback_data_id=kwargs.get("callback_data_id"),
            duration=kwargs.get("duration"),
            engine_version=kwargs.get("engine_version", ""),
        )
    except Exception:
        logger.exception(
            "emit diagnostic event failed, event_type=%s, root_pipeline_id=%s, node_id=%s",
            event_type,
            root_pipeline_id,
            node_id,
        )
        return None
