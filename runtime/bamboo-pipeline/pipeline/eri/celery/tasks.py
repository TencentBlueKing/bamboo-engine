# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time
import logging
from typing import Optional

from celery import current_app
from celery.schedules import crontab
from pipeline.contrib.celery_tools.periodic import periodic_task
from django.conf import settings

from bamboo_engine import metrics
from bamboo_engine.utils.host import get_hostname
from bamboo_engine.eri import ExecuteInterruptPoint, ScheduleInterruptPoint
from bamboo_engine.engine import Engine
from bamboo_engine.interrupt import (
    ExecuteInterrupter,
    ExecuteKeyPoint,
    ScheduleInterrupter,
    ScheduleKeyPoint,
)

from pipeline.eri.models import LogEntry
from pipeline.eri.runtime import BambooDjangoRuntime


logger = logging.getLogger(__name__)


def _observe_message_delay(metric: metrics.Histogram, headers: dict):
    if not headers or "timestamp" not in headers:
        return

    try:
        metric.labels(hostname=get_hostname()).observe(time.time() - headers["timestamp"])
    except Exception:
        logger.exception("%s observe err" % metric)


@current_app.task(ignore_result=True)
def execute(
    process_id: int,
    node_id: str,
    root_pipeline_id: str = None,
    parent_pipeline_id: str = None,
    recover_point: str = None,
    headers: dict = None,
    **kwargs,
):
    logger.info(
        f"[eri_execute worker] received task with info "
        f"(process_id: {process_id}, node_id: {node_id}, root_pipeline_id: {root_pipeline_id}, headers: {headers})"
    )
    _observe_message_delay(metrics.ENGINE_RUNTIME_EXECUTE_TASK_CLAIM_DELAY, headers)

    runtime = BambooDjangoRuntime()
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


@current_app.task(ignore_result=True)
def schedule(
    process_id: int,
    node_id: str,
    schedule_id: str,
    callback_data_id: Optional[int],
    recover_point: str = None,
    headers: dict = None,
    **kwargs,
):
    logger.info(
        f"[eri_schedule worker] received task with info "
        f"(process_id: {process_id}, node_id: {node_id}, schedule_id: {schedule_id}, headers: {headers})"
    )
    _observe_message_delay(metrics.ENGINE_RUNTIME_SCHEDULE_TASK_CLAIM_DELAY, headers)

    runtime = BambooDjangoRuntime()
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


@periodic_task(run_every=(crontab(minute=0, hour=0)), ignore_result=True)
def clean_expired_log():
    expired_interval = getattr(settings, "LOG_PERSISTENT_DAYS", None)

    if expired_interval is None:
        expired_interval = 30
        logger.warning("LOG_PERSISTENT_DAYS are not found in settings, use default value: 30")

    del_num = LogEntry.objects.delete_expired_log(expired_interval)
    logger.info("%s log entry are deleted" % del_num)
