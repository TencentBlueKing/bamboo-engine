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
import logging
import traceback
from typing import Optional
from contextlib import contextmanager

from bamboo_engine.eri.models import ScheduleInterruptPoint

from .eri import EngineRuntimeInterface, InterruptPoint, ExecuteInterruptPoint, HandlerExecuteData

logger = logging.getLogger("bamboo_engine")


class InterruptException(Exception):
    pass


class ExecuteKeyPoint:
    ENTRY = "ENTRY"
    START_PUSH_NODE = "START_PUSH_NODE"
    SET_NODE_RUNNING_PRE_CHECK_DONE = "SET_NODE_RUNNING_PRE_CHECK_DONE"
    SET_NODE_RUNNING_DONE = "SET_NODE_RUNNING_DONE"
    # after handler
    EXECUTE_NODE_DONE = "EXECUTE_NODE_DONE"
    EXECUTE_DONE_SET_SCHEDULE_DONE = "EXECUTE_DONE_SET_SCHEDULE_DONE"
    # conditional parallel gateway
    CPG_PROCESS_FORK_DONE = "CPG_PROCESS_FORK_DONE"
    # executeable end event
    EXEC_EE_EVENT_EXECUTE_DONE = "EXEC_EE_EVENT_EXECUTE_DONE"
    # parallel gateway
    PG_PROCESS_FORK_DONE = "PG_PROCESS_FORK_DONE"
    # service activity
    SA_SERVICE_EXECUTE_DONE = "SA_SERVICE_EXECUTE_DONE"
    # subprocess
    SP_SET_PIPELINE_STACK_DONE = "SP_SET_PIPELINE_STACK_DONE"


class Interrupter:
    def __init__(
        self,
        runtime: EngineRuntimeInterface,
        process_id: int,
        current_node_id: str,
        check_point: InterruptPoint,
        recover_point: Optional[InterruptPoint],
    ) -> None:
        self.runtime = runtime
        self.process_id = process_id
        self.current_node_id = current_node_id
        self.check_point = check_point
        self.recover_point = recover_point

    def _update_check_point_version(self):
        self.check_point.version += 1

        if not self.recover_point:
            return

        if self.check_point.version < self.recover_point.version and self.check_point.name == self.recover_point.name:
            self.check_point.version = self.recover_point.version

    def check(self, name: str):
        self.check_point.name = name
        self._update_check_point_version()

    def check_and_set(self, name: str, from_handler: bool = False, **kwargs):
        self.check_point.name = name
        target = self.check_point.handler_data if from_handler else self.check_point
        for attr, value in kwargs.items():
            setattr(target, attr, value)
        self._update_check_point_version()

    @property
    def check_point_string(self) -> str:
        return "[check_point: {}] [recover_point: {}]".format(
            self.check_point.to_json(), self.recover_point.to_json() if self.recover_point else "None"
        )

    @property
    def latest_recover_point(self) -> InterruptPoint:
        # send check_point if recover_point is None
        # compare check_point version and recover_point version and send the latest one
        if self.recover_point and self.recover_point.version > self.check_point.version:
            return self.recover_point
        else:
            return self.check_point


class ExecuteInterrupter(Interrupter):
    def __init__(
        self,
        runtime: EngineRuntimeInterface,
        current_node_id: str,
        process_id: int,
        parent_pipeline_id: str,
        root_pipeline_id: str,
        check_point: ExecuteInterruptPoint,
        recover_point: Optional[ExecuteInterruptPoint],
    ) -> None:
        super().__init__(
            runtime=runtime,
            process_id=process_id,
            current_node_id=current_node_id,
            check_point=check_point,
            recover_point=recover_point,
        )
        self.parent_pipeline_id = parent_pipeline_id
        self.root_pipeline_id = root_pipeline_id

    def to_node(self, node_id: str):
        self.current_node_id = node_id
        self.check_point.state_already_exist = False
        self.check_point.running_node_version = None
        self.check_point.execute_result = None
        self.check_point.set_schedule_done = False
        self.check_point.handler_data = HandlerExecuteData()
        self.recover_point = None

    @contextmanager
    def __call__(self):
        try:
            yield
        except Exception as e:
            if not isinstance(e, self.runtime.interrupt_errors()):
                logger.exception(
                    "[interrupt({})] execute catch unexpect error with {}".format(
                        self.current_node_id, self.check_point_string
                    )
                )
                raise e

            recover_point = self.latest_recover_point
            self.runtime.execute(
                process_id=self.process_id,
                node_id=self.current_node_id,
                root_pipeline_id=self.root_pipeline_id,
                parent_pipeline_id=self.parent_pipeline_id,
                recover_point=recover_point,
            )
            logger.error(
                "[interrupt({})] execute interrupt with point({}), trying to recover, {}".format(
                    self.current_node_id, recover_point.to_json(), traceback.format_exc()
                )
            )

            raise InterruptException()


class ScheduleKeyPoint:
    ENTRY = "ENTRY"
    VERSION_MISMATCH_CHECKED = "VERSION_MISMATCH_CHECKED"
    NODE_NOT_RUNNING_CHECKED = "NODE_NOT_RUNNING_CHECKED"
    APPLY_LOCK_DONE = "APPLY_LOCK_DONE"
    SCHEDULE_NODE_DONE = "SCHEDULE_NODE_DONE"
    RELEASE_LOCK_DONE = "RELEASE_LOCK_DONE"
    # service_activity
    SA_SERVICE_SCHEDULE_DONE = "SA_SERVICE_SCHEDULE_DONE"
    SA_SERVICE_SCHEDULE_TIME_ADDED = "SA_SERVICE_SCHEDULE_TIME_ADDED"


class ScheduleInterrupter(Interrupter):
    def __init__(
        self,
        runtime: EngineRuntimeInterface,
        process_id: int,
        current_node_id: str,
        schedule_id: int,
        callback_data_id: Optional[int],
        check_point: ScheduleInterruptPoint,
        recover_point: Optional[ScheduleInterruptPoint],
    ) -> None:
        super().__init__(
            runtime=runtime,
            process_id=process_id,
            current_node_id=current_node_id,
            check_point=check_point,
            recover_point=recover_point,
        )
        self.schedule_id = schedule_id
        self.callback_data_id = callback_data_id

    @contextmanager
    def __call__(self):
        try:
            yield
        except Exception as e:
            if not isinstance(e, self.runtime.interrupt_errors()):
                logger.exception(
                    "[interrupt({})] schedule catch unexpect error with {}".format(
                        self.current_node_id, self.check_point_string
                    )
                )
                raise e

            recover_point = self.latest_recover_point
            self.runtime.schedule(
                process_id=self.process_id,
                node_id=self.current_node_id,
                schedule_id=self.schedule_id,
                callback_data_id=self.callback_data_id,
                recover_point=recover_point,
            )
            logger.error(
                "[interrupt({})] schedule interrupt with point({}), trying to recover, {}".format(
                    self.current_node_id, recover_point.to_json(), traceback.format_exc()
                )
            )

            raise InterruptException()
