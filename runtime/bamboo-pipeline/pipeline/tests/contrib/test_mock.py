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

from bamboo_engine import states
from bamboo_engine.utils.string import unique_id
from django.test import TestCase

from pipeline.eri.imp.context import ContextMixin
from pipeline.eri.models import ContextValue, ExecutionData, State
from pipeline.contrib.mock import api


class TestMockNodeOutPutDataBase(TestCase):

    def assert_exception(self, pipeline_id, node_id, context_values, message):
        try:
            api.update_node_outputs(pipeline_id, node_id, context_values=context_values)
        except Exception as e:
            self.assertEqual(str(e), message)

    def test_update_node_data(self):
        pipeline_id = unique_id("n")
        node_id = unique_id("n")

        context_values = {
            "${code}": 2
        }

        message = "update context values failed: pipeline state not exist, root_pipeline_id={}".format(pipeline_id)
        self.assert_exception(pipeline_id, node_id, context_values, message)

        pipeline_state = State.objects.create(
            node_id=pipeline_id,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.FINISHED,
            version=unique_id("v")
        )

        message = "update context values failed: the task of non-running state is not allowed update, " \
                  "root_pipeline_id={}".format(pipeline_id)
        self.assert_exception(pipeline_id, node_id, context_values, message)

        node_state = State.objects.create(
            node_id=node_id,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.FINISHED,
            version=unique_id("v")
        )

        pipeline_state.name = states.RUNNING
        pipeline_state.save()

        message = "update context values failed: the task of non-failed state is not allowed to update, node_id={}" \
            .format(node_id)
        self.assert_exception(pipeline_id, node_id, context_values, message)

        node_state.name = states.FAILED
        node_state.save()

        pipeline_state.name = states.RUNNING
        pipeline_state.save()

        cv = ContextValue.objects.create(
            pipeline_id=pipeline_id,
            key="${code}",
            type=1,
            serializer=ContextMixin.JSON_SERIALIZER,
            code="cv",
            value=json.dumps("1"),
        )

        ed = ExecutionData.objects.create(
            node_id=node_id,
            inputs=json.dumps({}),
            inputs_serializer=ContextMixin.JSON_SERIALIZER,
            outputs=json.dumps({"code": 1}),
            outputs_serializer=ContextMixin.JSON_SERIALIZER,
        )

        api.update_node_outputs(pipeline_id, node_id, context_values={
            "${code}": 2
        })

        cv.refresh_from_db()
        ed.refresh_from_db()
        self.assertEqual(cv.value, "2")
        self.assertEqual(ed.outputs, json.dumps({"code": 2}))
