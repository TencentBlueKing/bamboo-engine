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

from django.contrib import admin

from .models import DiagnosticCase, DiagnosticEvent, DiagnosticOperationAudit


@admin.register(DiagnosticEvent)
class DiagnosticEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "root_pipeline_id",
        "node_id",
        "process_id",
        "version",
        "schedule_id",
        "callback_data_id",
        "result",
        "created_at",
    )
    search_fields = ("event_type", "root_pipeline_id", "node_id", "reason")
    list_filter = ("event_type", "result", "engine_version")


@admin.register(DiagnosticCase)
class DiagnosticCaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "root_pipeline_id",
        "node_id",
        "stuck_type",
        "severity",
        "confidence",
        "status",
        "hit_count",
        "last_seen_at",
    )
    search_fields = ("root_pipeline_id", "node_id", "stuck_type", "message")
    list_filter = ("stuck_type", "status", "severity")


@admin.register(DiagnosticOperationAudit)
class DiagnosticOperationAuditAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "operation_type", "operator", "mode", "risk_level", "created_at")
    search_fields = ("operator", "case__root_pipeline_id", "case__node_id")
    list_filter = ("operation_type", "mode", "risk_level")
