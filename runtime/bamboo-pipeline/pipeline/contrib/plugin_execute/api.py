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

from pipeline.contrib.plugin_execute.handler import PluginExecuteHandler
from pipeline.contrib.utils import ensure_return_pipeline_contrib_api_result


@ensure_return_pipeline_contrib_api_result
def run(component_code: str, version: str, inputs: dict, contexts: dict, runtime_attrs: dict = None):
    task_id = PluginExecuteHandler.run(component_code, version, inputs, contexts, runtime_attrs)
    return task_id


@ensure_return_pipeline_contrib_api_result
def get_state(task_id: int):
    return PluginExecuteHandler.get_state(task_id)


@ensure_return_pipeline_contrib_api_result
def callback(task_id: int, callback_data: dict = None):
    PluginExecuteHandler.callback(task_id, callback_data)


@ensure_return_pipeline_contrib_api_result
def forced_fail(task_id):
    PluginExecuteHandler.forced_fail(task_id)


@ensure_return_pipeline_contrib_api_result
def retry(task_id: int, inputs: dict = None, contexts: dict = None, runtime_attrs: dict = None):
    PluginExecuteHandler.retry_node(task_id, inputs, contexts, runtime_attrs)
