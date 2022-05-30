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

import json
from typing import Optional

from celery import task

from bamboo_engine.eri import ExecuteInterruptPoint, ScheduleInterruptPoint
from bamboo_engine.engine import Engine
from bamboo_engine.interrupt import (
    ExecuteInterrupter,
    ExecuteKeyPoint,
    ScheduleInterrupter,
    ScheduleKeyPoint,
)

from .runtime import ChoasBambooDjangoRuntime


@task(ignore_result=True)
def chaos_execute(
    process_id: int,
    node_id: str,
    root_pipeline_id: str = None,
    parent_pipeline_id: str = None,
    recover_point: str = None,
    execute_choas_plans: str = "[]",
    execute_plan_index: int = 0,
    schedule_choas_plans: str = "[]",
    schedule_plan_index: int = 0,
    headers: dict = None,
):
    runtime = ChoasBambooDjangoRuntime(
        stage="execute",
        execute_choas_plans=json.loads(execute_choas_plans),
        execute_plan_index=execute_plan_index,
        schedule_choas_plans=json.loads(schedule_choas_plans),
        schedule_plan_index=schedule_plan_index,
    )
    recover_point = ExecuteInterruptPoint.from_json(recover_point)
    interrupter = ExecuteInterrupter(
        runtime=runtime,
        current_node_id=node_id,
        process_id=process_id,
        parent_pipeline_id=parent_pipeline_id,
        root_pipeline_id=root_pipeline_id,
        check_point=ExecuteInterruptPoint(name=ExecuteKeyPoint.ENTRY),
        recover_point=recover_point,
        headers=headers or {},
    )

    Engine(runtime).execute(
        process_id=process_id,
        node_id=node_id,
        root_pipeline_id=root_pipeline_id,
        parent_pipeline_id=parent_pipeline_id,
        interrupter=interrupter,
        headers=headers or {},
    )


@task(ignore_result=True)
def chaos_schedule(
    process_id: int,
    node_id: str,
    schedule_id: str,
    callback_data_id: Optional[int],
    recover_point: str = None,
    execute_choas_plans: str = "[]",
    execute_plan_index: int = 0,
    schedule_choas_plans: str = "[]",
    schedule_plan_index: int = 0,
    headers: dict = None,
):
    runtime = ChoasBambooDjangoRuntime(
        stage="schedule",
        execute_choas_plans=json.loads(execute_choas_plans),
        execute_plan_index=execute_plan_index,
        schedule_choas_plans=json.loads(schedule_choas_plans),
        schedule_plan_index=schedule_plan_index,
    )
    recover_point = ScheduleInterruptPoint.from_json(recover_point)
    interrupter = ScheduleInterrupter(
        runtime=runtime,
        process_id=process_id,
        current_node_id=node_id,
        schedule_id=schedule_id,
        callback_data_id=callback_data_id,
        check_point=ScheduleInterruptPoint(name=ScheduleKeyPoint.ENTRY),
        recover_point=recover_point,
        headers=headers or {},
    )
    Engine(runtime).schedule(
        process_id=process_id,
        node_id=node_id,
        schedule_id=schedule_id,
        interrupter=interrupter,
        callback_data_id=callback_data_id,
        headers=headers or {},
    )
