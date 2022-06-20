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

from django.utils.module_loading import import_string

from pipeline.conf import settings


def get_periodic_task_root_pipeline_context(root_pipeline_data: dict):
    try:
        provider = import_string(settings.BAMBOO_PERIODIC_TASK_ROOT_PIPELINE_CONTEXT_PROVIER)
    except ImportError:
        return {}

    return provider(root_pipeline_data)


def get_periodic_task_subprocess_context(root_pipeline_data: dict):
    try:
        provider = import_string(settings.BAMBOO_PERIODIC_TASK_SUBPROCESS_CONTEXT_PROVIER)
    except ImportError:
        return {}

    return provider(root_pipeline_data)
