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

import mock
from mock.mock import MagicMock

from bamboo_engine import states
from bamboo_engine.utils.string import unique_id
from django.test import TestCase
from django.utils import timezone

from pipeline.contrib.rollback import api
from pipeline.contrib.rollback.handler import RollBackHandler
from pipeline.core.constants import PE
from pipeline.eri.models import Process, State, Node

forced_fail_activity_mock = MagicMock()
forced_fail_activity_mock.result = True


class TestRollBackBase(TestCase):

    def setUp(self) -> None:
        self.started_time = timezone.now()
        self.archived_time = timezone.now()

    @mock.patch("bamboo_engine.api.forced_fail_activity", MagicMock(return_value=forced_fail_activity_mock))
    @mock.patch("pipeline.eri.runtime.BambooDjangoRuntime.execute", MagicMock())
    def test_rollback(self):
        pipeline_id = unique_id("n")
        State.objects.create(
            node_id=pipeline_id,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.FINISHED,
            version=unique_id("v"),
            started_time=self.started_time,
            archived_time=self.archived_time,
        )

        node_id_1 = unique_id("n")
        node_id_2 = unique_id("n")
        State.objects.create(
            node_id=node_id_1,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.RUNNING,
            version=unique_id("v"),
            started_time=self.started_time,
            archived_time=self.archived_time,
        )

        State.objects.create(
            node_id=node_id_2,
            root_id=pipeline_id,
            parent_id=pipeline_id,
            name=states.RUNNING,
            version=unique_id("v"),
            started_time=self.started_time,
            archived_time=self.archived_time,
        )

        node_id_1_detail = {
            "id": "n0be4eaa13413f9184863776255312f1",
            "type": PE.ParallelGateway,
            "targets": {
                "l7895e18cd7c33b198d56534ca332227": node_id_2
            },
            "root_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "parent_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "can_skip": True,
            "code": "bk_display",
            "version": "v1.0",
            "error_ignorable": True,
            "can_retry": True
        }

        Node.objects.create(
            node_id=node_id_1,
            detail=json.dumps(node_id_1_detail)
        )

        node_id_2_detail = {
            "id": "n0be4eaa13413f9184863776255312f1",
            "type": PE.ParallelGateway,
            "targets": {
                "l7895e18cd7c33b198d56534ca332227": unique_id("n")
            },
            "root_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "parent_pipeline_id": "n3369d7ce884357f987af1631bda69cb",
            "can_skip": True,
            "code": "bk_display",
            "version": "v1.0",
            "error_ignorable": True,
            "can_retry": True
        }

        Node.objects.create(
            node_id=node_id_2,
            detail=json.dumps(node_id_2_detail)
        )

        # pipeline_id 非running的情况下会异常
        message = "rollback failed: the task of non-running state is not allowed to roll back, pipeline_id={}".format(
            pipeline_id)
        result = api.rollback(pipeline_id, pipeline_id)
        self.assertFalse(result.result)
        self.assertEqual(str(result.exc), message)

        State.objects.filter(node_id=pipeline_id).update(name=states.RUNNING)
        # pipeline_id 非running的情况下会异常
        message = "rollback failed: only allows rollback to ServiceActivity type nodes"
        result = api.rollback(pipeline_id, node_id_1)
        self.assertFalse(result.result)
        self.assertEqual(str(result.exc), message)

        node_id_1_detail["type"] = PE.ServiceActivity
        Node.objects.filter(node_id=node_id_1).update(detail=json.dumps(node_id_1_detail))

        message = "rollback failed: only allows rollback to finished node"
        result = api.rollback(pipeline_id, node_id_1)
        self.assertFalse(result.result)
        self.assertEqual(str(result.exc), message)
        State.objects.filter(node_id=node_id_1).update(name=states.FINISHED)

        p = Process.objects.create(
            root_pipeline_id=pipeline_id,
            parent_id=-1,
            current_node_id=node_id_2,
            pipeline_stack=json.dumps([pipeline_id]),
            priority=1
        )

        result = api.rollback(pipeline_id, node_id_1)
        self.assertTrue(result.result)

        p.refresh_from_db()
        self.assertEqual(p.current_node_id, node_id_1)
        # 验证Node2 是不是被删除了
        self.assertFalse(State.objects.filter(node_id=node_id_2).exists())

        state = State.objects.get(node_id=node_id_1)
        self.assertEqual(state.name, states.READY)

    def test_compute_validate_nodes(self):
        node_map = {
            "node_1": {
                "id": "node_1",
                "type": "EmptyStartEvent",
                "targets": {
                    "n": "node_2"
                },
            },
            "node_2": {
                "id": "node_2",
                "type": "ServiceActivity",
                "targets": {
                    "n": "node_3"
                },
            },
            "node_3": {
                "id": "node_3",
                "type": "ServiceActivity",
                "targets": {
                    "n": "node_4"
                },
            },
            "node_4": {
                "id": "node_4",
                "type": "ParallelGateway",
                "targets": {
                    "n": "node_5",
                    "n1": "node_6"
                },
                "converge_gateway_id": "node_7"
            },
            "node_5": {
                "id": "node_5",
                "type": "ServiceActivity",
                "targets": {
                    "n": "node_7"
                },
            },
            "node_6": {
                "id": "node_6",
                "type": "ServiceActivity",
                "targets": {
                    "n": "node_7"
                },
            },
            "node_7": {
                "id": "node_7",
                "type": "ConvergeGateway",
                "targets": {
                    "n": "node_8"
                },
            },
            "node_8": {
                "id": "node_8",
                "type": "ExclusiveGateway",
                "targets": {
                    "n1": "node_13",
                    "n2": "node_9",
                    "n3": "node_3"
                },
            },
            "node_9": {
                "id": "node_9",
                "type": "ServiceActivity",
                "targets": {
                    "n": "node_10"
                },
            },
            "node_10": {
                "id": "node_10",
                "type": "ExclusiveGateway",
                "targets": {
                    "n": "node_11",
                    "n2": "node_12"
                },
            }
        }
        node_id = 'node_1'

        nodes = RollBackHandler("p", node_map)._compute_validate_nodes(node_id, node_map)
        self.assertListEqual(nodes, ['node_2', 'node_3', 'node_9'])
