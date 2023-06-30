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

import json
import re

from django.db import transaction

from pipeline.eri.models import State
from pipeline.eri.models import ContextValue
from pipeline.eri.models import ExecutionData as DBExecutionData
from bamboo_engine import states, api
from bamboo_engine.eri import ContextValue as ContextValueInfo, ContextValueType

from pipeline.contrib.exceptions import UpdatePipelineContextException

from pipeline.eri.runtime import BambooDjangoRuntime

FORMATTED_KEY_PATTERN = re.compile(r"^\${(.*?)}$")


class MockHandler:

    def __init__(self, root_pipeline_id, node_id, context_values):
        self.root_pipeline_id = root_pipeline_id
        self.node_id = node_id
        self.context_values = context_values

    def update_node_outputs(self):
        """
        批量修改任务某个节点的输出和上下文
        :param root_pipeline_id: pipeline的id
        :param node_id: 节点id
        :param context_values: {
            "${code}": 200
        }
        :return:
        """

        pipeline_state = State.objects.filter(node_id=self.root_pipeline_id).first()
        if not pipeline_state:
            raise UpdatePipelineContextException(
                "update context values failed: pipeline state not exist, root_pipeline_id={}".format(
                    self.root_pipeline_id))

        if pipeline_state.name != states.RUNNING:
            raise UpdatePipelineContextException(
                "update context values failed: the task of non-running state is not allowed update, "
                "root_pipeline_id={}".format(self.root_pipeline_id))

        node_state = State.objects.filter(node_id=self.node_id).first()
        if not node_state:
            raise UpdatePipelineContextException(
                "update context values failed: node state not exist, root_pipeline_id={}".format(self.root_pipeline_id))

        if node_state.name != states.FAILED:
            raise UpdatePipelineContextException(
                "update context values failed: the task of non-failed state is not allowed to update, node_id={}"
                .format(self.node_id))

        if "${_system}" in self.context_values.keys():
            raise UpdatePipelineContextException("${_system} is built-in variable that is not allowed to be updated")

        # 获取流程内满足上下文的key
        context_value_queryset = ContextValue.objects.filter(pipeline_id=self.root_pipeline_id,
                                                             key__in=self.context_values.keys())
        context_value_list = []

        for context_value in context_value_queryset:
            if context_value.key in self.context_values.keys():
                context_value_list.append(
                    ContextValueInfo(key=context_value.key, type=ContextValueType(context_value.type),
                                     value=self.context_values.get(context_value.key),
                                     code=context_value.code))

        with transaction.atomic():
            try:
                runtime = BambooDjangoRuntime()
                api.update_context_values(runtime, self.root_pipeline_id, context_value_list)
            except Exception as e:
                raise UpdatePipelineContextException("update context value failed, please check it, error={}".format(e))

            outputs = {}
            try:
                for key, value in self.context_values.items():
                    if FORMATTED_KEY_PATTERN.match(key):
                        key = key[2:-1]
                    outputs[key] = value
                execution_data = DBExecutionData.objects.get(node_id=self.node_id)
                detail = json.loads(execution_data.outputs)
                detail.update(outputs)
                execution_data.outputs = json.dumps(detail)
                execution_data.save()

            except Exception as e:
                raise UpdatePipelineContextException(
                    "update node outputs value failed, please check it,outputs={}, error={}".format(outputs, e))
