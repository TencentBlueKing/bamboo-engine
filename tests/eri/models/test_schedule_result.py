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

from bamboo_engine.eri.models.handler import ScheduleResult


def test_to_dict():
    result = ScheduleResult(has_next_schedule=True, schedule_after=2, schedule_done=False, next_node_id=None)

    assert result.to_dict() == {
        "has_next_schedule": True,
        "schedule_after": 2,
        "schedule_done": False,
        "next_node_id": None,
    }


def test_from_dict():
    result = ScheduleResult.from_dict(
        {
            "has_next_schedule": True,
            "schedule_after": 2,
            "schedule_done": False,
            "next_node_id": None,
        }
    )

    assert result.has_next_schedule is True
    assert result.schedule_after == 2
    assert result.schedule_done is False
    assert result.next_node_id is None
