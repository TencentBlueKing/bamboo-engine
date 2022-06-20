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
import json
import random
import logging
from typing import Any, Optional, List

from celery import current_app
from bamboo_engine.eri.models import ExecuteInterruptPoint, ScheduleInterruptPoint
from pipeline.eri.runtime import BambooDjangoRuntime

logger = logging.getLogger("bamboo_engine")


class ChoasBambooDjangoRuntime(BambooDjangoRuntime):

    CHOAS_METHOD_RANGE = {
        "add_schedule_times",
        "apply_schedule_lock",
        "batch_get_state_name",
        "beat",
        "child_process_finish",
        "die",
        "expire_schedule",
        "finish_schedule",
        "fork",
        "get_callback_data",
        "get_context_key_references",
        "get_context_outputs",
        "get_context_values",
        "get_data",
        "get_data_outputs",
        "get_execution_data",
        "get_execution_data_outputs",
        "get_node",
        "get_process_info",
        "get_schedule",
        "get_state",
        "get_state_or_none",
        "join",
        "node_rerun_limit",
        "release_schedule_lock",
        "reset_children_state_inner_loop",
        "set_current_node",
        "set_execution_data",
        "set_execution_data_outputs",
        "set_pipeline_stack",
        "set_schedule",
        "set_state",
        "set_state_root_and_parent",
        "sleep",
        "suspend",
        "upsert_plain_context_values",
        "wake_up",
    }

    VALID_STAGE = {"execute", "schedule"}

    def __init__(
        self,
        stage: str,
        execute_choas_plans: List[dict],
        schedule_choas_plans: List[dict],
        execute_plan_index: int = -1,
        schedule_plan_index: int = -1,
    ):
        self.stage = stage
        self.execute_choas_plans = execute_choas_plans
        self.execute_plan_index = execute_plan_index
        self.schedule_choas_plans = schedule_choas_plans
        self.schedule_plan_index = schedule_plan_index
        self.raise_call_times = {}
        super().__init__()

    def current_choas_plan(self, stage: str):
        if stage not in self.VALID_STAGE:
            return {}

        index = getattr(self, "{}_plan_index".format(stage))
        plans = getattr(self, "{}_choas_plans".format(stage))
        if index < 0 or index >= len(plans):
            return {}

        return plans[index]

    def _chaos_warp(self, runtime_method):
        def wrapper(*args, **kwargs):
            method_name = runtime_method.__name__
            plan = self.current_choas_plan(self.stage)
            raise_time = plan.get(method_name, {}).get("raise_time", "never")
            raise_call_time = plan.get(method_name, {}).get("raise_call_time", 1)
            should_raise = raise_time != "never" and self.raise_call_times.get(method_name, 1) == raise_call_time

            if should_raise:
                logger.warning(
                    "[choas]current_method: <{}>, current_stage: <{}>, current_plan: {}, raise_time: <{}>, raise_call_time<{}>".format(
                        method_name, self.stage, plan, raise_time, raise_call_time
                    )
                )

            if should_raise and raise_time == "pre":
                raise random.choice(self.interrupt_errors())("[pre]let's make some choas.")

            self.raise_call_times.setdefault(method_name, 1)
            self.raise_call_times[method_name] += 1
            result = runtime_method(*args, **kwargs)

            if should_raise and raise_time == "post":
                raise random.choice(self.interrupt_errors())("[after]let's make some choas.")

            return result

        return wrapper

    def __getattribute__(self, __name: str) -> Any:
        runtime_method = super().__getattribute__(__name)
        if __name in object.__getattribute__(self, "CHOAS_METHOD_RANGE"):
            return object.__getattribute__(self, "_chaos_warp")(runtime_method)
        return runtime_method

    # eri
    def node_rerun_limit(self, root_pipeline_id: str, node_id: str) -> int:
        return 5

    def execute(
        self,
        process_id: int,
        node_id: str,
        root_pipeline_id: str,
        parent_pipeline_id: str,
        recover_point: Optional[ExecuteInterruptPoint] = None,
        headers: Optional[dict] = None,
    ):
        """
        派发执行任务，执行任务被拉起执行时应该调用 Engine 实例的 execute 方法

        :param process_id: 进程 ID
        :type process_id: int
        :param node_id: 节点 ID
        :type node_id: str
        """
        task_name = "eri_chaos.celery_tasks.chaos_execute"

        current_app.tasks[task_name].apply_async(
            kwargs={
                "process_id": process_id,
                "node_id": node_id,
                "root_pipeline_id": root_pipeline_id,
                "parent_pipeline_id": parent_pipeline_id,
                "recover_point": "{}" if not recover_point else recover_point.to_json(),
                "execute_choas_plans": json.dumps(self.execute_choas_plans),
                "execute_plan_index": self.execute_plan_index + 1,
                "schedule_choas_plans": json.dumps(self.schedule_choas_plans),
                "schedule_plan_index": self.schedule_plan_index,
                "headers": headers,
            },
            **{
                "queue": "er_execute",
                "routing_key": "er_execute",
            },
        )

    def schedule(
        self,
        process_id: int,
        node_id: str,
        schedule_id: str,
        callback_data_id: Optional[int] = None,
        recover_point: Optional[ScheduleInterruptPoint] = None,
        headers: Optional[dict] = None,
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
        task_name = "eri_chaos.celery_tasks.chaos_schedule"

        current_app.tasks[task_name].apply_async(
            kwargs={
                "process_id": process_id,
                "node_id": node_id,
                "schedule_id": schedule_id,
                "callback_data_id": callback_data_id,
                "recover_point": "{}" if not recover_point else recover_point.to_json(),
                "execute_choas_plans": json.dumps(self.execute_choas_plans),
                "execute_plan_index": self.execute_plan_index,
                "schedule_choas_plans": json.dumps(self.schedule_choas_plans),
                "schedule_plan_index": self.schedule_plan_index + 1,
                "headers": headers,
            },
            **{
                "queue": "er_schedule",
                "routing_key": "er_schedule",
            },
        )

    def set_next_schedule(
        self,
        process_id: int,
        node_id: str,
        schedule_id: str,
        schedule_after: int,
        callback_data_id: Optional[int] = None,
        headers: Optional[dict] = None,
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
        task_name = "eri_chaos.celery_tasks.chaos_schedule"

        current_app.tasks[task_name].apply_async(
            kwargs={
                "process_id": process_id,
                "node_id": node_id,
                "schedule_id": schedule_id,
                "callback_data_id": callback_data_id,
                "recover_point": "{}",
                "execute_choas_plans": json.dumps(self.execute_choas_plans),
                "execute_plan_index": self.execute_plan_index,
                "schedule_choas_plans": json.dumps(self.schedule_choas_plans),
                "schedule_plan_index": self.schedule_plan_index + 1,
                "headers": headers,
            },
            countdown=schedule_after,
            **{
                "queue": "er_schedule",
                "routing_key": "er_schedule",
            },
        )
