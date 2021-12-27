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

from mock import MagicMock, patch
from django.test import TestCase

from bamboo_engine.eri.models import (
    ExclusiveGateway,
    ConditionalParallelGateway,
    ParallelGateway,
    ServiceActivity,
    NodeType,
)
from pipeline.eri.models import Node
from pipeline.eri.doctor import AsleepProcessFinishedStateDoctor


class AsleepProcessFinishedStateDoctorTestCase(TestCase):
    def setUp(self) -> None:
        self.doctor = AsleepProcessFinishedStateDoctor(
            MagicMock(id=1, current_node_id="n1", root_pipeline_id="root_pipeline", pipeline_stack='["root_pipeline"]'),
            MagicMock(node_id="n1"),
        )

    def test_advice__current_node_does_not_exist(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(side_effect=Node.DoesNotExist)
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.assertEqual(self.doctor.advice(), "current node detail not exist, can't not give any advice")

        runtime.get_node.assert_called_once_with("n1")

    def test_advice__current_node_is_parallel_gateway(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ParallelGateway(
                id="n1",
                type=NodeType.ParallelGateway,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                converge_gateway_id="cg",
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.assertEqual(self.doctor.advice(), "process and node state is healthy")

        runtime.get_node.assert_called_once_with("n1")

    def test_advice__current_node_is_conditional_parallel_gateway(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ConditionalParallelGateway(
                id="n1",
                type=NodeType.ConditionalParallelGateway,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                conditions=[],
                converge_gateway_id="cg",
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.assertEqual(self.doctor.advice(), "process and node state is healthy")

        runtime.get_node.assert_called_once_with("n1")

    def test_advice__current_node_is_exclusive_gateway(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ExclusiveGateway(
                id="n1",
                type=NodeType.ExclusiveGateway,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                conditions=[],
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.assertEqual(self.doctor.advice(), "current node is exclusive gateway, execute it again")

        runtime.get_node.assert_called_once_with("n1")

    def test_advice__current_node_is_else(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ServiceActivity(
                id="n1",
                type=NodeType.ServiceActivity,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                code="",
                version="",
                timeout="",
                error_ignorable=False,
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.assertEqual(self.doctor.advice(), "execute next node")

        runtime.get_node.assert_called_once_with("n1")

    def test_heal__current_node_is_parallel_gateway(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ParallelGateway(
                id="n1",
                type=NodeType.ParallelGateway,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                converge_gateway_id="cg",
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.doctor.heal()

        runtime.get_node.assert_called_once_with("n1")

    def test_heal__current_node_is_conditional_parallel_gateway(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ParallelGateway(
                id="n1",
                type=NodeType.ParallelGateway,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                converge_gateway_id="cg",
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.doctor.heal()

        runtime.get_node.assert_called_once_with("n1")

    def test_heal__current_node_is_exclusive_gateway(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ExclusiveGateway(
                id="n1",
                type=NodeType.ExclusiveGateway,
                target_flows=[],
                target_nodes=[],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                conditions=[],
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)
        MockState = MagicMock()

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            with patch("pipeline.eri.doctor.State", MockState):
                self.doctor.heal()

        runtime.get_node.assert_called_once_with("n1")
        MockState.objects.filter(node_id="n1").update.assert_called_once_with(name="READY")
        runtime.execute.assert_called_once_with(
            process_id=1, node_id="n1", root_pipeline_id="root_pipeline", parent_pipeline_id="root_pipeline"
        )

    def test_heal__current_node_is_else(self):
        runtime = MagicMock()
        runtime.get_node = MagicMock(
            return_value=ServiceActivity(
                id="n1",
                type=NodeType.ServiceActivity,
                target_flows=[],
                target_nodes=["n2"],
                targets={},
                root_pipeline_id="root_pipeline",
                parent_pipeline_id="root_pipeline",
                code="",
                version="",
                timeout="",
                error_ignorable=False,
            )
        )
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)

        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.doctor.heal()

        runtime.get_node.assert_called_once_with("n1")
        runtime.execute.assert_called_once_with(
            process_id=1, node_id="n2", root_pipeline_id="root_pipeline", parent_pipeline_id="root_pipeline"
        )
