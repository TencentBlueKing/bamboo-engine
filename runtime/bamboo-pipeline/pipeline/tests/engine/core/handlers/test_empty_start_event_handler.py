# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.test import TestCase

from pipeline.core.data import var
from pipeline.core.flow.event import EmptyStartEvent
from pipeline.engine.core import handlers
from pipeline.engine.models import Status
from pipeline.tests.mock import *  # noqa
from pipeline.tests.mock_settings import *  # noqa

handlers.empty_start_event_handler = handlers.EmptyStartEventHandler()


class EmptyStartEventHandlerTestCase(TestCase):
    def test_element_cls(self):
        self.assertEqual(handlers.EmptyStartEventHandler.element_cls(), EmptyStartEvent)

    @patch(PIPELINE_STATUS_FINISH, MagicMock())
    def test_handle(self):
        context_variables = {"${pre_render_key}": var.PlainVariable(name="pre_render_key", value="test pre_render_key")}
        process = MockPipelineProcess(top_pipeline_context=MockContext(variables=context_variables))
        start_event = StartEventObject(data=MockData(get_inputs_return={"pre_render_keys": ["${pre_render_key}"]}))

        hdl_result = handlers.empty_start_event_handler(process, start_event, MockStatus())

        Status.objects.finish.assert_called_once_with(start_event)

        self.assertEqual(hdl_result.next_node, start_event.next())
        self.assertFalse(hdl_result.should_sleep)
        self.assertFalse(hdl_result.should_return)
        self.assertEqual(process.top_pipeline.context.variables["${pre_render_key}"], "test pre_render_key")
