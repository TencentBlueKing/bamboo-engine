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

import logging
from typing import Optional

from bamboo_engine import metrics
from bamboo_engine.eri import ExecuteInterruptPoint, NodeType, ProcessInfo
from bamboo_engine.handler import ExecuteResult, NodeHandler, register_handler
from bamboo_engine.interrupt import ExecuteKeyPoint

logger = logging.getLogger("bamboo_engine")


@register_handler(NodeType.SubCanvas)
class SubCanvasHandler(NodeHandler):
    def execute(
        self,
        process_info: ProcessInfo,
        loop: int,
        inner_loop: int,
        version: str,
        recover_point: Optional[ExecuteInterruptPoint] = None,
    ) -> ExecuteResult:
        """
        子画布节点的 execute 处理逻辑

        :param process_info: 进程信息
        :type process_info: ProcessInfo
        :param loop: 重入次数
        :param inner_loop: 当前流程重入次数
        :param version: 执行版本
        :param recover_point: 恢复点
        :return: 执行结果
        :rtype: ExecuteResult
        """

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_PRE_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            top_pipeline_id = process_info.top_pipeline_id
            self.runtime.reset_children_state_inner_loop(self.node.id)

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_POST_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            # update subprocess context, inject subprocess data
            self.runtime.copy_context_values_to_new_pipeline(top_pipeline_id, self.node.id)
            if not recover_point or not recover_point.handler_data.pipeline_stack_setted:
                process_info.pipeline_stack.append(self.node.id)
                self.runtime.set_pipeline_stack(process_info.process_id, process_info.pipeline_stack)
            self.interrupter.check_and_set(
                ExecuteKeyPoint.SP_SET_PIPELINE_STACK_DONE, pipeline_stack_setted=True, from_handler=True
            )

            return ExecuteResult(
                should_sleep=False,
                schedule_ready=False,
                schedule_type=None,
                schedule_after=-1,
                dispatch_processes=[],
                next_node_id=self.node.start_event_id,
            )
