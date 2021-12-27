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

from pipeline.eri.doctor import AsleepProcessSuspendedStateDoctor


class AsleepProcessSuspendedStateDoctorTestCase(TestCase):
    def setUp(self) -> None:
        self.doctor = AsleepProcessSuspendedStateDoctor(
            MagicMock(id=1, current_node_id="n1", root_pipeline_id="root_pipeline", pipeline_stack='["root_pipeline"]'),
            MagicMock(node_id="n1"),
        )

    def test_advice(self):
        self.assertEqual(self.doctor.advice(), "node suspended, make process suspended")

    def test_heal(self):
        runtime = MagicMock()
        MockBambooDjangoRuntime = MagicMock(return_value=runtime)
        with patch("pipeline.eri.doctor.BambooDjangoRuntime", MockBambooDjangoRuntime):
            self.doctor.heal()

        runtime.wake_up.assert_called_once_with(1)
        runtime.suspend.assert_called_once_with(1, "n1")
