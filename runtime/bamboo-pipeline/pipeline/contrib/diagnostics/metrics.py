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
