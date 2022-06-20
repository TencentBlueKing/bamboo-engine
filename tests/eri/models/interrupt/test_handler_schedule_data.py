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


from bamboo_engine.eri.models.interrupt import HandlerScheduleData


def test_to_dict():
    data = HandlerScheduleData(
        service_scheduled=True,
        service_schedule_fail=True,
        is_schedule_done=False,
        schedule_times_added=False,
        schedule_serialize_outputs="{}",
        schedule_outputs_serializer="json",
    )

    assert data.to_dict() == {
        "service_scheduled": True,
        "service_schedule_fail": True,
        "is_schedule_done": False,
        "schedule_times_added": False,
        "schedule_serialize_outputs": "{}",
        "schedule_outputs_serializer": "json",
    }


def test_from_dict():
    data = HandlerScheduleData.from_dict(
        {
            "service_scheduled": True,
            "service_schedule_fail": True,
            "is_schedule_done": False,
            "schedule_times_added": False,
            "schedule_serialize_outputs": "{}",
            "schedule_outputs_serializer": "json",
        }
    )

    assert data.service_scheduled is True
    assert data.service_schedule_fail is True
    assert data.is_schedule_done is False
    assert data.schedule_times_added is False
    assert data.schedule_serialize_outputs == "{}"
    assert data.schedule_outputs_serializer == "json"
