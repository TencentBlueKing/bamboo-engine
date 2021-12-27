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

from pipeline.eri.doctor import Decision

class DecisionTestCase(TestCase):
    def test_init(self):
        decision = Decision(asleep=True, suspended=False, state_name="RUNNING")
        self.assertEqual(decision.asleep, True)
        self.assertEqual(decision.suspended, False)
        self.assertEqual(decision.state_name, "RUNNING")

    def test_eq(self):
        decision1 = Decision(asleep=True, suspended=False, state_name="RUNNING")
        decision2 = Decision(asleep=True, suspended=False, state_name="RUNNING")
        decision3 = Decision(asleep=False, suspended=False, state_name="RUNNING")

        self.assertTrue(decision1 == decision2)
        self.assertFalse(decision1 == decision3)
    
    def test_hash(self):
        decision = Decision(asleep=True, suspended=False, state_name="RUNNING")

        d = {decision: "token"}

        self.assertEqual(d[Decision(asleep=True, suspended=False, state_name="RUNNING")], "token")
        self.assertIsNone(d.get(Decision(asleep=True, suspended=True, state_name="RUNNING")))