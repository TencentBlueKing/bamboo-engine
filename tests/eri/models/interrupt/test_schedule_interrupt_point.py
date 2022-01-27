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


from bamboo_engine.eri.models.handler import ScheduleResult
from bamboo_engine.eri.models.interrupt import HandlerScheduleData, ScheduleInterruptPoint


def test_to_json():
    point = ScheduleInterruptPoint(
        name="n1",
        version=1,
        version_mismatch=False,
        lock_get=True,
        schedule_result=ScheduleResult(
            has_next_schedule=True, schedule_after=2, schedule_done=False, next_node_id=None
        ),
        lock_released=True,
        handler_data=HandlerScheduleData(
            service_scheduled=True,
            service_schedule_fail=True,
            is_schedule_done=False,
            schedule_times_added=False,
            schedule_serialize_outputs="{}",
            schedule_outputs_serializer="json",
        ),
    )

    assert (
        point.to_json()
        == '{"name": "n1", "version": 1, "version_mismatch": false, "node_not_running": null, "lock_get": true, "schedule_result": {"has_next_schedule": true, "schedule_after": 2, "schedule_done": false, "next_node_id": null}, "lock_released": true, "handler_data": {"service_scheduled": true, "service_schedule_fail": true, "is_schedule_done": false, "schedule_times_added": false, "schedule_serialize_outputs": "{}", "schedule_outputs_serializer": "json"}}'
    )  # noqa


def test_from_json():
    point = ScheduleInterruptPoint.from_json(
        '{"name": "n1", "version": 1, "version_mismatch": false, "node_not_running": null, "lock_get": true, "schedule_result": {"has_next_schedule": true, "schedule_after": 2, "schedule_done": false, "next_node_id": null}, "lock_released": true, "handler_data": {"service_scheduled": true, "service_schedule_fail": true, "is_schedule_done": false, "schedule_times_added": false, "schedule_serialize_outputs": "{}", "schedule_outputs_serializer": "json"}}'
    )  # noqa

    assert ScheduleInterruptPoint.from_json(None) is None
    assert ScheduleInterruptPoint.from_json("null") is None

    assert point.schedule_result.has_next_schedule is True
    assert point.schedule_result.schedule_after == 2
    assert point.schedule_result.schedule_done is False
    assert point.schedule_result.next_node_id is None
    assert point.handler_data.service_scheduled is True
    assert point.handler_data.service_schedule_fail is True
    assert point.handler_data.is_schedule_done is False
    assert point.handler_data.schedule_times_added is False
    assert point.handler_data.schedule_serialize_outputs == "{}"
    assert point.handler_data.schedule_outputs_serializer == "json"
    assert point.name == "n1"
    assert point.version == 1
    assert point.version_mismatch is False
    assert point.lock_get is True
    assert point.node_not_running is None
    assert point.lock_released is True
