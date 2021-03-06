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
import copy
import logging
import traceback
from typing import Optional

from bamboo_engine import states, metrics
from bamboo_engine.eri import ProcessInfo, NodeType, ExecuteInterruptPoint
from bamboo_engine.handler import register_handler, ExecuteResult
from bamboo_engine.interrupt import ExecuteKeyPoint

from .empty_end_event import EmptyEndEventHandler

logger = logging.getLogger("bamboo_engine")


@register_handler(NodeType.ExecutableEndEvent)
class ExecutableEndEventHandler(EmptyEndEventHandler):
    def execute(
        self,
        process_info: ProcessInfo,
        loop: int,
        inner_loop: int,
        version: str,
        recover_point: Optional[ExecuteInterruptPoint] = None,
    ) -> ExecuteResult:
        """
        节点的 execute 处理逻辑

        :param runtime: 引擎运行时实例
        :type runtime: EngineRuntimeInterface
        :param process_info: 进程信息
        :type process_id: ProcessInfo
        :return: 执行结果
        :rtype: ExecuteResult
        """

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_PRE_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            logger.info(
                "root_pipeline[%s] node(%s) executable end event: %s",
                process_info.root_pipeline_id,
                self.node.id,
                self.node,
            )
            event = self.runtime.get_executable_end_event(code=self.node.code)

        execute_fail = False
        ex_data = ""
        if recover_point and recover_point.handler_data.end_event_executed:
            execute_fail = recover_point.handler_data.end_event_execute_fail
            ex_data = recover_point.handler_data.end_event_execute_ex_data
        else:
            try:
                event.execute(
                    pipeline_stack=copy.copy(process_info.pipeline_stack),
                    root_pipeline_id=process_info.root_pipeline_id,
                )
            except Exception:
                execute_fail = True
                ex_data = traceback.format_exc()
                logger.warning(
                    "root_pipeline[%s] node(%s) executable end event execute raise: %s",
                    process_info.root_pipeline_id,
                    self.node.id,
                    ex_data,
                )
        self.interrupter.check_and_set(
            ExecuteKeyPoint.EXEC_EE_EVENT_EXECUTE_DONE,
            end_event_executed=True,
            end_event_execute_fail=execute_fail,
            end_event_execute_ex_data=ex_data,
            from_handler=True,
        )

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_POST_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            if execute_fail:
                self.runtime.set_execution_data_outputs(node_id=self.node.id, outputs={"ex_data": ex_data})

                self.runtime.set_state(
                    node_id=self.node.id,
                    version=version,
                    to_state=states.FAILED,
                    set_archive_time=True,
                    ignore_boring_set=recover_point is not None,
                )

                return ExecuteResult(
                    should_sleep=True,
                    schedule_ready=False,
                    schedule_type=None,
                    schedule_after=-1,
                    dispatch_processes=[],
                    next_node_id=None,
                )

        return super().execute(
            process_info=process_info, loop=loop, inner_loop=inner_loop, version=version, recover_point=recover_point
        )
