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

from bamboo_engine.eri.models import DispatchProcess
from bamboo_engine.eri.models.interrupt import HandlerExecuteData


def test_to_dict():
    data = HandlerExecuteData(
        dispatch_processes=[DispatchProcess(process_id=1, node_id="1"), DispatchProcess(process_id=2, node_id="2")],
        end_event_executed=False,
        end_event_execute_fail=False,
        end_event_execute_ex_data="",
        service_executed=True,
        service_execute_fail=True,
        execute_serialize_outputs="{}",
        execute_outputs_serializer="json",
        pipeline_stack_setted=True,
    )

    assert data.to_dict() == {
        "dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}],
        "end_event_executed": False,
        "end_event_execute_fail": False,
        "end_event_execute_ex_data": "",
        "service_executed": True,
        "service_execute_fail": True,
        "execute_serialize_outputs": "{}",
        "execute_outputs_serializer": "json",
        "pipeline_stack_setted": True,
    }


def test_from_dict():
    data = HandlerExecuteData.from_dict(
        {
            "dispatch_processes": [{"process_id": 1, "node_id": "1"}, {"process_id": 2, "node_id": "2"}],
            "end_event_executed": False,
            "end_event_execute_fail": False,
            "end_event_execute_ex_data": "",
            "service_executed": True,
            "service_execute_fail": True,
            "execute_serialize_outputs": "{}",
            "execute_outputs_serializer": "json",
            "pipeline_stack_setted": True,
        }
    )

    assert data.dispatch_processes[0].process_id == 1
    assert data.dispatch_processes[0].node_id == "1"
    assert data.dispatch_processes[1].process_id == 2
    assert data.dispatch_processes[1].node_id == "2"
    assert data.end_event_executed is False
    assert data.end_event_execute_fail is False
    assert data.end_event_execute_ex_data == ""
    assert data.service_executed is True
    assert data.service_execute_fail is True
    assert data.execute_serialize_outputs == "{}"
    assert data.execute_outputs_serializer == "json"
    assert data.pipeline_stack_setted is True
