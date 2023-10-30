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
import copy
import datetime
import json
from typing import Any, Dict, List

from django.test import TestCase
from mock import MagicMock, call, patch
from pipeline.contrib.node_timer_event import constants, types, utils
from pipeline.contrib.node_timer_event.models import (
    ExpiredNodesRecord,
    NodeTimerEventConfig,
)
from pipeline.contrib.node_timer_event.tasks import (
    dispatch_expired_nodes,
    execute_node_timer_event_action,
)
from pipeline.eri.models import Process, State

from bamboo_engine.eri import DataInput, ExecutionData


class ParseTimerDefinedTestCase(TestCase):

    TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    def test_time_cycle(self):

        start: datetime.datetime = datetime.datetime.strptime("2022-01-01 00:00:00", self.TIME_FORMAT)
        cases: List[Dict[str, Any]] = [
            {
                "defined": "R5/PT10S",
                "repetitions": 5,
                "timestamp": (start + datetime.timedelta(seconds=10)).timestamp(),
            },
            {"defined": "R1/P1D", "repetitions": 1, "timestamp": (start + datetime.timedelta(days=1)).timestamp()},
        ]

        for case in cases:
            time_defined: types.TimeDefined = utils.parse_timer_defined(
                timer_type=constants.TimerType.TIME_CYCLE.value, defined=case["defined"], start=start
            )
            self.assertEqual(time_defined["repetitions"], case["repetitions"])
            self.assertEqual(time_defined["timestamp"], case["timestamp"])

    def test_time_duration(self):
        start: datetime.datetime = datetime.datetime.strptime("2022-01-01 00:00:00", self.TIME_FORMAT)
        cases: List[Dict[str, Any]] = [
            {
                "defined": "P14DT1H30M",
                "timestamp": (start + datetime.timedelta(days=14, hours=1, minutes=30)).timestamp(),
            },
            {"defined": "P14D", "timestamp": (start + datetime.timedelta(days=14)).timestamp()},
            {
                "defined": "P14DT1H30M",
                "timestamp": (start + datetime.timedelta(days=14, hours=1, minutes=30)).timestamp(),
            },
            {"defined": "PT15S", "timestamp": (start + datetime.timedelta(seconds=15)).timestamp()},
        ]

        for case in cases:
            time_defined: types.TimeDefined = utils.parse_timer_defined(
                timer_type=constants.TimerType.TIME_DURATION.value, defined=case["defined"], start=start
            )
            self.assertEqual(time_defined["repetitions"], 1)
            self.assertEqual(time_defined["timestamp"], case["timestamp"])

    def test_time_date(self):
        start: datetime.datetime = datetime.datetime.strptime("2022-01-01 00:00:00", self.TIME_FORMAT)
        cases: List[Dict[str, Any]] = [
            {"defined": "2019-10-01T12:00:00Z", "timestamp": 1569931200.0},
            {"defined": "2019-10-02T08:09:40+02:00", "timestamp": 1569996580.0},
            {"defined": "2019-10-02T08:09:40+02:00[Europe/Berlin]", "timestamp": 1569996580.0},
        ]

        for case in cases:
            time_defined: types.TimeDefined = utils.parse_timer_defined(
                timer_type=constants.TimerType.TIME_DATE.value, defined=case["defined"], start=start
            )
            self.assertEqual(time_defined["repetitions"], 1)
            self.assertEqual(time_defined["timestamp"], case["timestamp"])


class NodeTimerEventTestCase(TestCase):
    def setUp(self):
        self.node_id = "node_id"
        self.version = "version"
        self.action = "example"
        self.root_pipeline_id = "root_pipeline_id"
        self.pipeline_tree = {}
        self.timer_events = [
            {
                "index": 1,
                "action": self.action,
                "timer_type": constants.TimerType.TIME_CYCLE.value,
                "repetitions": 5,
                "defined": "R5/PT10S",
            },
            {
                "index": 2,
                "action": self.action,
                "timer_type": constants.TimerType.TIME_DATE.value,
                "repetitions": 1,
                "defined": "2019-10-01T12:00:00Z",
            },
        ]
        self.timer_events_in_tree = [
            {
                "enable": True,
                "action": self.action,
                "timer_type": constants.TimerType.TIME_CYCLE.value,
                "defined": "R5/PT10S",
            },
            {
                "enable": True,
                "action": self.action,
                "timer_type": constants.TimerType.TIME_DATE.value,
                "defined": "2019-10-01T12:00:00Z",
            },
        ]
        runtime = MagicMock()
        runtime.get_execution_data = MagicMock(
            return_value=ExecutionData({"key": "value", "from": "node"}, {"key": "value"})
        )
        runtime.get_data_inputs = MagicMock(return_value={"key": DataInput(need_render=False, value=1)})
        self.runtime = runtime
        self.mock_runtime = MagicMock(return_value=runtime)

    def test_dispatch_expired_nodes(self):
        mock_execute_node_timer_event_strategy = MagicMock()
        mock_execute_node_timer_event_strategy.apply_async = MagicMock()
        with patch(
            "pipeline.contrib.node_timer_event.tasks.execute_node_timer_event_action",
            mock_execute_node_timer_event_strategy,
        ):
            ExpiredNodesRecord.objects.create(
                id=1,
                nodes=json.dumps(
                    [
                        "bamboo:v1:node_timer_event:node:node1:version:version1:index:1",
                        "bamboo:v1:node_timer_event:node:node2:version:version2:index:1",
                    ]
                ),
            )

            dispatch_expired_nodes(record_id=1)
            mock_execute_node_timer_event_strategy.apply_async.assert_has_calls(
                [
                    call(kwargs={"node_id": "node1", "version": "version1", "index": 1}),
                    call(kwargs={"node_id": "node2", "version": "version2", "index": 1}),
                ]
            )

    def execute_node_timeout_action_success_test_helper(self, index: int):
        NodeTimerEventConfig.objects.create(
            root_pipeline_id=self.root_pipeline_id, node_id=self.node_id, events=json.dumps(self.timer_events)
        )
        Process.objects.create(root_pipeline_id=self.root_pipeline_id, current_node_id=self.node_id, priority=1)
        State.objects.create(node_id=self.node_id, name="name", version=self.version)

        redis_inst = MagicMock()
        redis_inst.incr = MagicMock(return_value=b"2")
        redis_inst.zadd = MagicMock(return_value=b"1")

        key: str = f"bamboo:v1:node_timer_event:node:{self.node_id}:version:{self.version}:index:{index}"
        with patch("pipeline.contrib.node_timer_event.handlers.BambooDjangoRuntime", self.mock_runtime):
            with patch("pipeline.contrib.node_timer_event.models.node_timer_event_settings.redis_inst", redis_inst):
                result = execute_node_timer_event_action(self.node_id, self.version, index=index)
                self.assertEqual(result["result"], True)
                self.runtime.get_execution_data.assert_called_once_with(self.node_id)
                self.runtime.get_data_inputs.assert_called_once_with(self.root_pipeline_id)
                redis_inst.incr.assert_called_once_with(key, 1)
                if index == 1:
                    redis_inst.zadd.assert_called_once()
                else:
                    redis_inst.zadd.assert_not_called()

    def test_execute_node_timer_event_action_success__time_cycle(self):
        """测试时间循环：成功调度时，投递下一个节点"""
        self.execute_node_timeout_action_success_test_helper(index=1)

    def test_execute_node_timer_event_action_success__time_date(self):
        """测试具体时间日期：无需进行下次调度"""
        self.execute_node_timeout_action_success_test_helper(index=2)

    def test_execute_node_timer_event_action_not_current_node(self):
        NodeTimerEventConfig.objects.create(
            root_pipeline_id=self.root_pipeline_id, node_id=self.node_id, events=json.dumps(self.timer_events)
        )
        Process.objects.create(root_pipeline_id=self.root_pipeline_id, current_node_id="next_node", priority=1)
        State.objects.create(node_id=self.node_id, name="name", version=self.version)
        with patch("pipeline.contrib.node_timer_event.handlers.BambooDjangoRuntime", self.mock_runtime):
            result = execute_node_timer_event_action(self.node_id, self.version, index=1)
            self.assertEqual(result["result"], False)
            self.runtime.get_data_inputs.assert_not_called()
            self.runtime.get_execution_data.assert_not_called()

    def test_execute_node_timer_event_action_not_current_version(self):
        NodeTimerEventConfig.objects.create(
            root_pipeline_id=self.root_pipeline_id, node_id=self.node_id, events=json.dumps(self.timer_events)
        )
        Process.objects.create(root_pipeline_id=self.root_pipeline_id, current_node_id=self.node_id, priority=1)
        State.objects.create(node_id=self.node_id, name="name", version="ano_version")

        with patch("pipeline.contrib.node_timer_event.handlers.BambooDjangoRuntime", self.mock_runtime):
            result = execute_node_timer_event_action(self.node_id, self.version, index=1)
            self.assertEqual(result["result"], False)
            self.runtime.get_data_inputs.assert_not_called()
            self.runtime.get_execution_data.assert_not_called()

    def test_parse_node_timer_event_configs_success(self):
        pipeline_tree = {
            "activities": {
                "act_1": {"type": "ServiceActivity", "events": {"timer_events": self.timer_events_in_tree}},
                "act_2": {"type": "ServiceActivity", "events": {"timer_events": self.timer_events_in_tree}},
            }
        }

        parse_result = NodeTimerEventConfig.objects.parse_node_timer_event_configs(pipeline_tree)
        self.assertEqual(parse_result["result"], True)
        self.assertEqual(
            parse_result["data"],
            [{"node_id": "act_1", "events": self.timer_events}, {"node_id": "act_2", "events": self.timer_events}],
        )

    def test_parse_node_timer_event_configs_fail_and_ignore(self):

        timer_events_in_tree_act_1 = copy.deepcopy(self.timer_events_in_tree)
        timer_events_in_tree_act_1[1]["defined"] = "invalid defined"

        timer_events_in_tree_act_2 = copy.deepcopy(self.timer_events_in_tree)
        timer_events_in_tree_act_2[1]["timer_type"] = "invalid timer_type"

        pipeline_tree = {
            "activities": {
                "act_1": {"type": "ServiceActivity", "events": {"timer_events": timer_events_in_tree_act_1}},
                "act_2": {"type": "ServiceActivity", "events": {"timer_events": timer_events_in_tree_act_2}},
            }
        }
        parse_result = NodeTimerEventConfig.objects.parse_node_timer_event_configs(pipeline_tree)
        self.assertEqual(parse_result["result"], True)
        self.assertEqual(
            parse_result["data"],
            [
                {"node_id": "act_1", "events": [self.timer_events[0]]},
                {"node_id": "act_2", "events": [self.timer_events[0]]},
            ],
        )

    def test_batch_create_node_timer_config_success(self):
        config_parse_result = {
            "result": True,
            "data": [
                {"node_id": "act_1", "events": self.timer_events},
                {"node_id": "act_2", "events": self.timer_events},
            ],
            "message": "",
        }
        with patch(
            "pipeline.contrib.node_timer_event.models.NodeTimerEventConfig.objects.parse_node_timer_event_configs",
            MagicMock(return_value=config_parse_result),
        ):
            NodeTimerEventConfig.objects.batch_create_node_timer_event_config(self.root_pipeline_id, self.pipeline_tree)
            config_count = len(NodeTimerEventConfig.objects.all())
            self.assertEqual(config_count, 2)

    def test_batch_create_node_timer_config_fail(self):
        config_parse_result = {"result": False, "data": "", "message": "test fail"}
        with patch(
            "pipeline.contrib.node_timer_event.models.NodeTimerEventConfig.objects.parse_node_timer_event_configs",
            MagicMock(return_value=config_parse_result),
        ):
            NodeTimerEventConfig.objects.batch_create_node_timer_event_config(self.root_pipeline_id, self.pipeline_tree)
            config_count = NodeTimerEventConfig.objects.count()
            self.assertEqual(config_count, 0)
