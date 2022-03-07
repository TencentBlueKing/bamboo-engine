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

from bamboo_engine import states
from bamboo_engine.eri import ProcessInfo, NodeType, ExecuteInterruptPoint
from bamboo_engine.handler import register_handler, NodeHandler, ExecuteResult
from bamboo_engine.interrupt import ExecuteKeyPoint


@register_handler(NodeType.ParallelGateway)
class ParallelGatewayHandler(NodeHandler):
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

        from_to = {}
        for target in self.node.target_nodes:
            from_to[target] = self.node.converge_gateway_id

        # try to recover forked processes
        if recover_point and recover_point.handler_data.dispatch_processes:
            dispatch_processes = recover_point.handler_data.dispatch_processes
        else:
            dispatch_processes = self.runtime.fork(
                parent_id=process_info.process_id,
                root_pipeline_id=process_info.root_pipeline_id,
                pipeline_stack=process_info.pipeline_stack,
                from_to=from_to,
            )
        self.interrupter.check_and_set(
            ExecuteKeyPoint.PG_PROCESS_FORK_DONE, dispatch_processes=dispatch_processes, from_handler=True
        )

        self.runtime.set_state(
            node_id=self.node.id,
            version=version,
            to_state=states.FINISHED,
            set_archive_time=True,
            ignore_boring_set=recover_point is not None,
        )

        return ExecuteResult(
            should_sleep=True,
            schedule_ready=False,
            schedule_type=None,
            schedule_after=-1,
            dispatch_processes=dispatch_processes,
            next_node_id=None,
        )
