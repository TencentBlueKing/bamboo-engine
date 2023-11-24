# # -*- coding: utf-8 -*-
# """
# Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
# Edition) available.
# Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://opensource.org/licenses/MIT
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
# """

from unittest import TestCase

from mock.mock import MagicMock
from pipeline.component_framework.library import ComponentLibrary
from pipeline.contrib.plugin_execute import api
from pipeline.contrib.plugin_execute.models import PluginExecuteTask
from pipeline.contrib.plugin_execute.tasks import execute, schedule
from pipeline.tests import mock
from pipeline_test_use.components.collections.atom import (
    DebugCallbackComponent,
    InterruptDummyExecuteComponent,
)

mock_execute = MagicMock()
mock_execute.apply_async = MagicMock(return_value=True)

mock_schedule = MagicMock()
mock_schedule.apply_async = MagicMock(return_value=True)


class TestPluginExecuteBase(TestCase):
    @mock.patch("pipeline.contrib.plugin_execute.handler.execute", MagicMock(return_value=mock_execute))
    def test_run(self):
        task_id = api.run("debug_callback_node", "legacy", {"hello": "world"}, {"hello": "world"}).data
        task = PluginExecuteTask.objects.get(id=task_id)
        self.assertEqual(task.state, "READY")
        self.assertDictEqual(task.callback_data, {})
        self.assertDictEqual(task.contexts, {"hello": "world"})
        self.assertDictEqual(task.inputs, {"hello": "world"})

    @mock.patch("pipeline.contrib.plugin_execute.handler.execute", MagicMock(return_value=mock_execute))
    def test_get_state(self):
        task_id = api.run("debug_callback_node", "legacy", {"hello": "world"}, {"hello": "world"}).data
        state = api.get_state(task_id).data
        self.assertEqual(state["state"], "READY")
        self.assertDictEqual(state["inputs"], {"hello": "world"})
        self.assertDictEqual(state["contexts"], {"hello": "world"})

    @mock.patch("pipeline.contrib.plugin_execute.handler.execute", MagicMock(return_value=mock_execute))
    def test_retry(self):
        task_id = api.run("debug_callback_node", "legacy", {"hello": "world"}, {"hello": "world"}).data
        task = PluginExecuteTask.objects.get(id=task_id)
        result = api.retry(task_id, {})

        self.assertFalse(result.result)

        task.state = "FAILED"
        task.save()

        result = api.retry(task_id, {"hello": "tim"}, {"hello": "jav"})
        self.assertEqual(result.result, True)

        task.refresh_from_db()

        self.assertEqual(task.state, "READY")
        self.assertDictEqual(task.inputs, {"hello": "tim"})
        self.assertDictEqual(task.contexts, {"hello": "jav"})

    @mock.patch("pipeline.contrib.plugin_execute.handler.schedule", MagicMock(return_value=mock_schedule))
    @mock.patch("pipeline.contrib.plugin_execute.handler.execute", MagicMock(return_value=mock_execute))
    def test_callback(self):
        task_id = api.run("debug_callback_node", "legacy", {"hello": "world"}, {"hello": "world"}).data
        task = PluginExecuteTask.objects.get(id=task_id)
        result = api.retry(task_id, {})

        self.assertFalse(result.result)

        task.state = "RUNNING"
        task.save()

        result = api.callback(task_id, {"hello": "sandri"})
        self.assertEqual(result.result, True)

        task.refresh_from_db()
        self.assertDictEqual(task.callback_data, {"hello": "sandri"})

    @mock.patch("pipeline.contrib.plugin_execute.handler.execute", MagicMock(return_value=mock_execute))
    def test_force_fail(self):
        task_id = api.run("debug_callback_node", "legacy", {"hello": "world"}, {"hello": "world"}).data
        task = PluginExecuteTask.objects.get(id=task_id)
        result = api.forced_fail(task_id)

        self.assertFalse(result.result)

        task.state = "RUNNING"
        task.save()

        result = api.forced_fail(task_id)
        self.assertEqual(result.result, True)

        task.refresh_from_db()
        self.assertEqual(task.state, "FAILED")

    def test_execute_task(self):
        task = PluginExecuteTask.objects.create(
            state="READY",
            inputs={"time": 1},
            version="legacy",
            component_code="interrupt_dummy_exec_node",
            contexts={},
            runtime_attrs={},
        )
        ComponentLibrary.register_component("interrupt_dummy_exec_node", "legacy", InterruptDummyExecuteComponent)
        execute(task.id)
        task.refresh_from_db()
        self.assertEqual(task.state, "FINISHED")
        self.assertDictEqual(task.outputs, {"execute_count": 1})

    def test_schedule_task(self):
        task = PluginExecuteTask.objects.create(
            state="READY",
            inputs={},
            version="legacy",
            component_code="debug_callback_node",
            contexts={},
            runtime_attrs={},
        )
        ComponentLibrary.register_component("debug_callback_node", "legacy", DebugCallbackComponent)
        task = PluginExecuteTask.objects.get(id=task.id)
        task.callback_data = {"bit": 1}
        task.save()
        execute(task.id)
        schedule(task.id)
        task.refresh_from_db()
        self.assertEqual(task.state, "FINISHED")
