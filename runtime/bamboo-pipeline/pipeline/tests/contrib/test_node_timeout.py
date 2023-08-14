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
import json
from mock import patch, MagicMock, call

from django.test import TestCase

from pipeline.contrib.node_timeout.handlers import node_timeout_handler
from pipeline.eri.models import Process, State

from pipeline.contrib.node_timeout.tasks import dispatch_timeout_nodes, execute_node_timeout_strategy
from pipeline.contrib.node_timeout.models import TimeoutNodeConfig, TimeoutNodesRecord


class NodeTimeoutTaskTestCase(TestCase):
    def setUp(self):
        self.node_id = "node_id"
        self.version = "version"
        self.action = "forced_fail"
        self.root_pipeline_id = "root_pipeline_id"
        self.mock_handler = MagicMock()
        self.mock_handler.deal_with_timeout_node = MagicMock(return_value={"result": True, "message": "success"})
        self.node_timeout_settings = {self.action: self.mock_handler}
        self.pipeline_tree = {}
        self.parsed_configs = [
            {"action": "forced_fail", "node_id": "act_1", "timeout": 2},
            {"action": "forced_fail_and_skip", "node_id": "act_2", "timeout": 2},
        ]

    def test_dispatch_timeout_nodes(self):
        mock_node_timeout_executor = MagicMock()
        mock_node_timeout_executor.apply_async = MagicMock()
        with patch("pipeline.contrib.node_timeout.tasks.execute_node_timeout_strategy", mock_node_timeout_executor):
            TimeoutNodesRecord.objects.create(id=1, timeout_nodes=json.dumps(["node1_version1", "node2_version2"]))
            dispatch_timeout_nodes(record_id=1)
            mock_node_timeout_executor.apply_async.assert_has_calls(
                [
                    call(
                        kwargs={"node_id": "node1", "version": "version1"},
                    ),
                    call(
                        kwargs={"node_id": "node2", "version": "version2"},
                    ),
                ]
            )

    def test_execute_node_timeout_strategy_success(self):
        TimeoutNodeConfig.objects.create(
            root_pipeline_id=self.root_pipeline_id, action=self.action, node_id=self.node_id, timeout=30
        )
        Process.objects.create(root_pipeline_id=self.root_pipeline_id, current_node_id=self.node_id, priority=1)
        State.objects.create(node_id=self.node_id, name="name", version=self.version)
        with patch("pipeline.contrib.node_timeout.tasks.node_timeout_settings.handler", self.node_timeout_settings):
            result = execute_node_timeout_strategy(self.node_id, self.version)
            self.assertEqual(result["result"], True)
            self.mock_handler.deal_with_timeout_node.assert_called_once_with(self.node_id)

    def test_execute_node_timeout_strategy_not_current_node(self):
        TimeoutNodeConfig.objects.create(
            root_pipeline_id=self.root_pipeline_id, action=self.action, node_id=self.node_id, timeout=30
        )
        Process.objects.create(root_pipeline_id=self.root_pipeline_id, current_node_id="next_node", priority=1)
        State.objects.create(node_id=self.node_id, name="name", version=self.version)
        mock_handler = MagicMock()
        mock_handler.deal_with_timeout_node = MagicMock(return_value=True)
        with patch("pipeline.contrib.node_timeout.tasks.node_timeout_settings.handler", self.node_timeout_settings):
            result = execute_node_timeout_strategy(self.node_id, self.version)
            self.assertEqual(result["result"], False)
            self.mock_handler.deal_with_timeout_node.assert_not_called()

    def test_execute_node_timeout_strategy_not_current_version(self):
        TimeoutNodeConfig.objects.create(
            root_pipeline_id=self.root_pipeline_id, action=self.action, node_id=self.node_id, timeout=30
        )
        Process.objects.create(root_pipeline_id=self.root_pipeline_id, current_node_id=self.node_id, priority=1)
        State.objects.create(node_id=self.node_id, name="name", version="ano_version")

        with patch("pipeline.contrib.node_timeout.tasks.node_timeout_settings.handler", self.node_timeout_settings):
            result = execute_node_timeout_strategy(self.node_id, self.version)
            self.assertEqual(result["result"], False)
            self.mock_handler.deal_with_timeout_node.assert_not_called()

    def test_parse_node_timeout_configs_success(self):
        pipeline_tree = {
            "activities": {
                "act_1": {
                    "type": "ServiceActivity",
                    "timeout_config": {"enable": True, "seconds": 2, "action": "forced_fail"},
                },
                "act_2": {
                    "type": "ServiceActivity",
                    "timeout_config": {"enable": True, "seconds": 2, "action": "forced_fail_and_skip"},
                },
            }
        }
        parse_configs = [
            {"action": "forced_fail", "node_id": "act_1", "timeout": 2},
            {"action": "forced_fail_and_skip", "node_id": "act_2", "timeout": 2},
        ]
        parse_result = TimeoutNodeConfig.objects.parse_node_timeout_configs(pipeline_tree)
        self.assertEqual(parse_result["result"], True)
        self.assertEqual(parse_result["data"], parse_configs)

    def test_parse_node_timeout_configs_fail_and_ignore(self):
        pipeline_tree = {
            "activities": {
                "act_1": {
                    "type": "ServiceActivity",
                    "timeout_config": {"enable": True, "seconds": "test_fail", "action": "forced_fail"},
                },
                "act_2": {
                    "type": "ServiceActivity",
                    "timeout_config": {"enable": True, "seconds": 2, "action": "forced_fail_and_skip"},
                },
            }
        }
        parse_configs = [{"action": "forced_fail_and_skip", "node_id": "act_2", "timeout": 2}]
        parse_result = TimeoutNodeConfig.objects.parse_node_timeout_configs(pipeline_tree)
        self.assertEqual(parse_result["result"], True)
        self.assertEqual(parse_result["data"], parse_configs)

    def test_batch_create_node_time_config_success(self):
        config_parse_result = {"result": True, "data": self.parsed_configs, "message": ""}
        with patch(
            "pipeline.contrib.node_timeout.models.TimeoutNodeConfig.objects.parse_node_timeout_configs",
            MagicMock(return_value=config_parse_result),
        ):
            TimeoutNodeConfig.objects.batch_create_node_timeout_config(self.root_pipeline_id, self.pipeline_tree)
            config_count = len(TimeoutNodeConfig.objects.all())
            self.assertEqual(config_count, 2)

    def test_batch_create_node_time_config_fail(self):
        config_parse_result = {"result": False, "data": "", "message": "test fail"}
        with patch(
            "pipeline.contrib.node_timeout.models.TimeoutNodeConfig.objects.parse_node_timeout_configs",
            MagicMock(return_value=config_parse_result),
        ):
            TimeoutNodeConfig.objects.batch_create_node_timeout_config(self.root_pipeline_id, self.pipeline_tree)
            config_count = TimeoutNodeConfig.objects.count()
            self.assertEqual(config_count, 0)

    def test_forced_fail_strategy(self):
        bamboo_engine_api = MagicMock()
        result = MagicMock()
        result.result = True
        bamboo_engine_api.forced_fail_activity = MagicMock(return_value=result)
        node_id = "node_id"
        handler = node_timeout_handler["forced_fail"]
        with patch("pipeline.contrib.node_timeout.handlers.bamboo_engine_api", bamboo_engine_api):
            result = handler.deal_with_timeout_node(node_id)
            self.assertEqual(result["result"], True)

    def test_forced_fail_and_skip_strategy_failed(self):
        bamboo_engine_api = MagicMock()
        result = MagicMock()
        result.result = False
        bamboo_engine_api.forced_fail_activity = MagicMock(return_value=result)
        node_id = "node_id"
        handler = node_timeout_handler["forced_fail_and_skip"]
        with patch("pipeline.contrib.node_timeout.handlers.bamboo_engine_api", bamboo_engine_api):
            result = handler.deal_with_timeout_node(node_id)
            self.assertEqual(result["result"], False)

    def test_forced_fail_and_skip_strategy_success(self):
        bamboo_engine_api = MagicMock()
        result = MagicMock()
        result.result = True
        bamboo_engine_api.forced_fail_activity = MagicMock(return_value=result)
        bamboo_engine_api.skip_node = MagicMock(return_value=result)
        node_id = "node_id"
        handler = node_timeout_handler["forced_fail_and_skip"]
        with patch("pipeline.contrib.node_timeout.handlers.bamboo_engine_api", bamboo_engine_api):
            result = handler.deal_with_timeout_node(node_id)
            self.assertEqual(result["result"], True)
