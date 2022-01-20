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

from typing import Optional

from celery import current_app
from bamboo_engine.eri.models import ExecuteInterruptPoint, ScheduleInterruptPoint

from pipeline.eri.celery.queues import QueueResolver

from pipeline.eri.models import Process


def _retry_once(action: callable):
    try:
        action()
    except Exception:
        try:
            action()
        except Exception as e:
            raise e


class TaskMixin:
    def _get_task_route_params(self, task_name: str, process_id: int):
        process = Process.objects.filter(id=process_id).only("priority", "queue").first()
        resolver = QueueResolver(process.queue)
        queue, routing_key = resolver.resolve_task_queue_and_routing_key(task_name)
        return {
            "queue": queue,
            "priority": process.priority,
            "routing_key": routing_key,
        }

    def execute(
        self,
        process_id: int,
        node_id: str,
        root_pipeline_id: str,
        parent_pipeline_id: str,
        recover_point: Optional[ExecuteInterruptPoint] = None,
    ):
        """
        派发执行任务，执行任务被拉起执行时应该调用 Engine 实例的 execute 方法

        :param process_id: 进程 ID
        :type process_id: int
        :param node_id: 节点 ID
        :type node_id: str
        """
        task_name = "pipeline.eri.celery.tasks.execute"
        route_params = self._get_task_route_params(task_name, process_id)

        def action():
            current_app.tasks[task_name].apply_async(
                kwargs={
                    "process_id": process_id,
                    "node_id": node_id,
                    "root_pipeline_id": root_pipeline_id,
                    "parent_pipeline_id": parent_pipeline_id,
                    "recover_point": "{}" if not recover_point else recover_point.to_json(),
                },
                **route_params,
            )

        _retry_once(action=action)

    def schedule(
        self,
        process_id: int,
        node_id: str,
        schedule_id: str,
        callback_data_id: Optional[int] = None,
        recover_point: Optional[ScheduleInterruptPoint] = None,
    ):
        """
        派发调度任务，调度任务被拉起执行时应该调用 Engine 实例的 schedule 方法

        :param process_id: 进程 ID
        :type process_id: int
        :param node_id: 节点 ID
        :type node_id: str
        :param schedule_id: 调度 ID
        :type schedule_id: str
        """
        task_name = "pipeline.eri.celery.tasks.schedule"
        route_params = self._get_task_route_params(task_name, process_id)

        def action():
            current_app.tasks[task_name].apply_async(
                kwargs={
                    "process_id": process_id,
                    "node_id": node_id,
                    "schedule_id": schedule_id,
                    "callback_data_id": callback_data_id,
                    "recover_point": "{}" if not recover_point else recover_point.to_json(),
                },
                **route_params,
            )

        _retry_once(action=action)

    def set_next_schedule(
        self,
        process_id: int,
        node_id: str,
        schedule_id: str,
        schedule_after: int,
        callback_data_id: Optional[int] = None,
    ):
        """
        设置下次调度时间，调度倒数归零后应该执行 Engine 实例的 schedule 方法

        :param process_id: 进程 ID
        :type process_id: int
        :param node_id: 节点 ID
        :type node_id: str
        :param schedule_id: 调度 ID
        :type schedule_id: str
        :param schedule_after: 调度倒数
        :type schedule_after: int
        """
        task_name = "pipeline.eri.celery.tasks.schedule"
        route_params = self._get_task_route_params(task_name, process_id)

        def action():
            current_app.tasks[task_name].apply_async(
                kwargs={
                    "process_id": process_id,
                    "node_id": node_id,
                    "schedule_id": schedule_id,
                    "callback_data_id": callback_data_id,
                    "recover_point": "{}",
                },
                countdown=schedule_after,
                **route_params,
            )

        _retry_once(action=action)
