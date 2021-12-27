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

from pipeline.eri.doctor import SuspendedProcessRunningStateDoctor


class SuspendedProcessRunningStateDoctorTestCase(TestCase):
    def setUp(self) -> None:
        self.doctor = SuspendedProcessRunningStateDoctor(
            MagicMock(id=1, current_node_id="n1", root_pipeline_id="root_pipeline", pipeline_stack='["root_pipeline"]'),
            MagicMock(),
        )

    def test_advice(self):
        self.assertEqual(self.doctor.advice(), "continue execute current node")

    def test_heal(self):
        runtime = MagicMock()
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)
        MockState = MagicMock()
        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            with patch("pipeline.eri.doctor.State", MockState):
                self.doctor.heal()

        runtime.resume.assert_called_once_with(1)
        runtime.sleep.assert_called_once_with(1)
        runtime.execute.assert_called_once_with(
            process_id=1, node_id="n1", root_pipeline_id="root_pipeline", parent_pipeline_id="root_pipeline"
        )
        MockState.objects.filter(node_id="n1").update.assert_called_once_with(name="READY")