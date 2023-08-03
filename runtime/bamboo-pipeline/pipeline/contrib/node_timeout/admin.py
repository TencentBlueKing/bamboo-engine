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

from pipeline.contrib.node_timeout import models


@admin.register(models.TimeoutNodeConfig)
class TimeoutNodeConfigAdmin(admin.ModelAdmin):
    list_display = ["root_pipeline_id", "node_id", "timeout"]
    search_fields = ["root_pipeline_id__exact", "node_id__exact"]


@admin.register(models.TimeoutNodesRecord)
class TimeoutNodeRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "timeout_nodes"]
