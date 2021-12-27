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

from mock import patch, MagicMock, call
from django.test import TestCase

from bamboo_engine import states
from pipeline.eri.models import State
from pipeline.eri.doctor import (
    PipelineDoctor,
    Decision,
    RunningProcessReadyStateDoctor,
    HealthyDoctor,
    RunningProcessSuspendedStateDoctor,
    RunningProcessFailedStateDoctor,
    RunningProcessFinishedStateDoctor,
    AsleepProcessReadyStateDoctor,
    AsleepProcessSuspendedStateDoctor,
    AsleepProcessFinishedStateDoctor,
    SuspendedProcessReadyStateDoctor,
    SuspendedProcessRunningStateDoctor,
    SuspendedProcessFailedStateDoctor,
    SuspendedProcessFinishedStateDoctor,
)


class PipelineDoctorTestCase(TestCase):
    def setUp(self):
        self.pipeline_id = "pipeline_id"
        self.doctor_heal = PipelineDoctor(True)
        self.doctor_not_heal = PipelineDoctor(False)

    def test_decision_table(self):
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=False, state_name=states.READY))
            is RunningProcessReadyStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=False, state_name=states.RUNNING))
            is HealthyDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=False, state_name=states.SUSPENDED))
            is RunningProcessSuspendedStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=False, state_name=states.FAILED))
            is RunningProcessFailedStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=False, state_name=states.FINISHED))
            is RunningProcessFinishedStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=True, suspended=False, state_name=states.READY))
            is AsleepProcessReadyStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=True, suspended=False, state_name=states.RUNNING))
            is HealthyDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=True, suspended=False, state_name=states.SUSPENDED))
            is AsleepProcessSuspendedStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=True, suspended=False, state_name=states.FAILED))
            is HealthyDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=True, suspended=False, state_name=states.FINISHED))
            is AsleepProcessFinishedStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=True, state_name=states.READY))
            is SuspendedProcessReadyStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=True, state_name=states.RUNNING))
            is SuspendedProcessRunningStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=True, state_name=states.SUSPENDED))
            is HealthyDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=True, state_name=states.FAILED))
            is SuspendedProcessFailedStateDoctor
        )
        self.assertTrue(
            self.doctor_heal.DECISION_TABLE.get(Decision(asleep=False, suspended=True, state_name=states.FINISHED))
            is SuspendedProcessFinishedStateDoctor
        )

    def test_pipeline_state_does_not_exist(self):
        MockState = MagicMock()
        MockState.objects.get = MagicMock(side_effect=State.DoesNotExist)
        # prevent "catching classes that do not inherit from BaseException" exception raise after mock
        MockState.DoesNotExist = State.DoesNotExist

        with patch("pipeline.eri.doctor.State", MockState):
            summary = self.doctor_heal.dignose(self.pipeline_id)

        self.assertEqual(summary.logs, ["can not found state for pipeline: pipeline_id"])
        MockState.objects.get.assert_called_once_with(node_id=self.pipeline_id)

    def test_pipeline_state_is_not_running(self):
        state = MagicMock()
        state.name = "FINISHED"
        MockState = MagicMock()
        MockState.objects.get = MagicMock(return_value=state)

        with patch("pipeline.eri.doctor.State", MockState):
            summary = self.doctor_heal.dignose(self.pipeline_id)

        self.assertEqual(summary.logs, ["pipeline current state is FINISHED(expect: RUNNING), can not dignose"])
        MockState.objects.get.assert_called_once_with(node_id=self.pipeline_id)

    def test_realte_process_not_found(self):
        state = MagicMock()
        state.name = "RUNNING"
        MockState = MagicMock()
        MockState.objects.get = MagicMock(return_value=state)
        MockProcess = MagicMock()
        MockProcess.objects.filter = MagicMock(return_value=[])

        with patch("pipeline.eri.doctor.State", MockState):
            with patch("pipeline.eri.doctor.Process", MockProcess):
                summary = self.doctor_heal.dignose(self.pipeline_id)

        self.assertEqual(summary.logs, ["can not found related process for pipeline: pipeline_id"])
        MockState.objects.get.assert_called_once_with(node_id=self.pipeline_id)
        MockProcess.objects.filter.assert_called_once_with(root_pipeline_id=self.pipeline_id)

    def test_alive_process_not_found(self):
        state = MagicMock()
        state.name = "RUNNING"
        MockState = MagicMock()
        MockState.objects.get = MagicMock(return_value=state)
        process_1 = MagicMock(dead=True)
        process_2 = MagicMock(dead=True)
        process_3 = MagicMock(dead=True)
        MockProcess = MagicMock()
        MockProcess.objects.filter = MagicMock(return_value=[process_1, process_2, process_3])

        with patch("pipeline.eri.doctor.State", MockState):
            with patch("pipeline.eri.doctor.Process", MockProcess):
                summary = self.doctor_heal.dignose(self.pipeline_id)

        self.assertEqual(
            summary.logs,
            [
                "find 3 processes",
                "all related processes are daed, there seems to be no problem with the pipeline",
                "find 0 alive processes, 3 dead processes",
            ],
        )
        MockState.objects.get.assert_called_once_with(node_id=self.pipeline_id)
        MockProcess.objects.filter.assert_called_once_with(root_pipeline_id=self.pipeline_id)

    def test_heal_it(self):
        state_1 = MagicMock()
        state_1.name = "RUNNING"
        state_2 = MagicMock()
        state_2.name = "RUNNING"
        MockState = MagicMock()
        MockState.objects.get = MagicMock(side_effect=[state_1, state_2, State.DoesNotExist])
        # prevent "catching classes that do not inherit from BaseException" exception raise after mock
        MockState.DoesNotExist = State.DoesNotExist
        process_1 = MagicMock(id=1, dead=True, current_node_id="n1", asleep=False, suspended=False)
        process_2 = MagicMock(id=2, dead=False, current_node_id="n2", asleep=False, suspended=False)
        process_3 = MagicMock(id=3, dead=False, current_node_id="n3", asleep=False, suspended=False)
        MockProcess = MagicMock()
        MockProcess.objects.filter = MagicMock(return_value=[process_1, process_2, process_3])

        with patch("pipeline.eri.doctor.State", MockState):
            with patch("pipeline.eri.doctor.Process", MockProcess):
                summary = self.doctor_heal.dignose(self.pipeline_id)

        self.assertTrue(summary.healed)
        self.assertEqual(
            summary.logs,
            ["find 3 processes", "find 2 alive processes, 1 dead processes"],
        )
        self.assertEqual(
            summary.exception_cases,
            [
                "can not find state for process(id:3, asleep: False, suspended: False) current node: n3",
            ],
        )
        self.assertEqual(
            summary.advices,
            [
                "process 2 (asleep: False, suspended: False, state_name: RUNNING): process and node state is healthy",
            ],
        )
        MockState.objects.get.assert_has_calls(
            [
                call(node_id=self.pipeline_id),
                call(node_id=process_2.current_node_id),
                call(node_id=process_3.current_node_id),
            ]
        )
        MockProcess.objects.filter.assert_called_once_with(root_pipeline_id=self.pipeline_id)

    def test_not_heal_it(self):
        state_1 = MagicMock()
        state_1.name = "RUNNING"
        state_2 = MagicMock()
        state_2.name = "RUNNING"
        MockState = MagicMock()
        MockState.objects.get = MagicMock(side_effect=[state_1, state_2, State.DoesNotExist])
        # prevent "catching classes that do not inherit from BaseException" exception raise after mock
        MockState.DoesNotExist = State.DoesNotExist
        process_1 = MagicMock(id=1, dead=True, current_node_id="n1", asleep=False, suspended=False)
        process_2 = MagicMock(id=2, dead=False, current_node_id="n2", asleep=False, suspended=False)
        process_3 = MagicMock(id=3, dead=False, current_node_id="n3", asleep=False, suspended=False)
        MockProcess = MagicMock()
        MockProcess.objects.filter = MagicMock(return_value=[process_1, process_2, process_3])

        with patch("pipeline.eri.doctor.State", MockState):
            with patch("pipeline.eri.doctor.Process", MockProcess):
                summary = self.doctor_not_heal.dignose(self.pipeline_id)

        self.assertFalse(summary.healed)
        self.assertEqual(
            summary.logs,
            ["find 3 processes", "find 2 alive processes, 1 dead processes"],
        )
        self.assertEqual(
            summary.exception_cases,
            [
                "can not find state for process(id:3, asleep: False, suspended: False) current node: n3",
            ],
        )
        self.assertEqual(
            summary.advices,
            [
                "process 2 (asleep: False, suspended: False, state_name: RUNNING): process and node state is healthy",
            ],
        )
        MockState.objects.get.assert_has_calls(
            [
                call(node_id=self.pipeline_id),
                call(node_id=process_2.current_node_id),
                call(node_id=process_3.current_node_id),
            ]
        )
        MockProcess.objects.filter.assert_called_once_with(root_pipeline_id=self.pipeline_id)
