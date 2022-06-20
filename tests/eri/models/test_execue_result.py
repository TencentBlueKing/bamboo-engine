# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bamboo_engine.eri.models.handler import ExecuteResult
from bamboo_engine.eri.models.runtime import DispatchProcess, ScheduleType


def test_to_dict():
    result = ExecuteResult(
        should_sleep=True,
        schedule_ready=False,
        schedule_type=ScheduleType.POLL,
        schedule_after=2,
        dispatch_processes=[DispatchProcess(process_id=1, node_id="1"), DispatchProcess(process_id=2, node_id="2")],
        next_node_id=None,
        should_die=False,
    )

    assert result.to_dict() == {
        "should_sleep": True,
        "schedule_ready": False,
        "schedule_type": ScheduleType.POLL.value,
        "schedule_after": 2,
        "dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}],
        "next_node_id": None,
        "should_die": False,
    }


def test_from_dict():
    result = ExecuteResult.from_dict(
        {
            "should_sleep": True,
            "schedule_ready": False,
            "schedule_type": ScheduleType.POLL.value,
            "schedule_after": 2,
            "dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}],
            "next_node_id": None,
            "should_die": False,
        }
    )

    assert result.should_sleep is True
    assert result.schedule_ready is False
    assert result.schedule_type == ScheduleType.POLL
    assert result.schedule_after == 2
    assert result.dispatch_processes[0].process_id == 1
    assert result.dispatch_processes[0].node_id == "1"
    assert result.dispatch_processes[1].process_id == 2
    assert result.dispatch_processes[1].node_id == "2"
    assert result.next_node_id is None
    assert result.should_die is False
