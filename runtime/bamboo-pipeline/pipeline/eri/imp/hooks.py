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

from typing import Optional

from pipeline.conf import default_settings
from pipeline.eri.models import LogEntry
from pipeline.eri.signals import pipeline_event

from bamboo_engine.eri import ExecutionData


class PipelineEvent:
    def __init__(self, event_type, data):
        self.event_type = event_type
        self.data = data

    def as_dict(self):
        return {
            "event_type": self.event_type,
            "data": self.data,
        }


class HooksMixin:
    def _send_event(self, event: PipelineEvent):
        if not default_settings.ENABLE_PIPELINE_EVENT_SIGNALS:
            return

        pipeline_event.send(sender=HooksMixin, event=event)

    def pre_prepare_run_pipeline(
        self, pipeline: dict, root_pipeline_data: dict, root_pipeline_context: dict, subprocess_context: dict, **options
    ):
        """
        调用 pre_prepare_run_pipeline 前执行的钩子

        :param pipeline: 流程描述对象
        :type pipeline: dict
        :param root_pipeline_data 根流程数据
        :type root_pipeline_data: dict
        :param root_pipeline_context 根流程上下文
        :type root_pipeline_context: dict
        :param subprocess_context 子流程预置流程上下文
        :type subprocess_context: dict
        """
        self._send_event(
            PipelineEvent(
                event_type="pre_prepare_run_pipeline",
                data={
                    "pipeline": pipeline,
                    "root_pipeline_data": root_pipeline_data,
                    "root_pipeline_context": root_pipeline_context,
                    "subprocess_context": subprocess_context,
                },
            )
        )

    def post_prepare_run_pipeline(
        self, pipeline: dict, root_pipeline_data: dict, root_pipeline_context: dict, subprocess_context: dict, **options
    ):
        """
        调用 pre_prepare_run_pipeline 后执行的钩子

        :param pipeline: 流程描述对象
        :type pipeline: dict
        :param root_pipeline_data 根流程数据
        :type root_pipeline_data: dict
        :param root_pipeline_context 根流程上下文
        :type root_pipeline_context: dict
        :param subprocess_context 子流程预置流程上下文
        :type subprocess_context: dict
        """
        self._send_event(
            PipelineEvent(
                event_type="post_prepare_run_pipeline",
                data={
                    "pipeline": pipeline,
                    "root_pipeline_data": root_pipeline_data,
                    "root_pipeline_context": root_pipeline_context,
                    "subprocess_context": subprocess_context,
                },
            )
        )

    def pre_pause_pipeline(self, pipeline_id: str):
        """
        暂停 pipeline 前执行的钩子

        :param pipeline_id: 流程 ID
        :type pipeline_id: str
        """
        self._send_event(PipelineEvent(event_type="pre_pause_pipeline", data={"pipeline_id": pipeline_id}))

    def post_pause_pipeline(self, pipeline_id: str):
        """
        暂停 pipeline 后执行的钩子

        :param pipeline_id: 流程 ID
        :type pipeline_id: str
        """
        self._send_event(PipelineEvent(event_type="post_pause_pipeline", data={"pipeline_id": pipeline_id}))

    def pre_revoke_pipeline(self, pipeline_id: str):
        """
        撤销 pipeline 前执行的钩子

        :param pipeline_id: 流程 ID
        :type pipeline_id: str
        """
        self._send_event(PipelineEvent(event_type="pre_revoke_pipeline", data={"pipeline_id": pipeline_id}))

    def post_revoke_pipeline(self, pipeline_id: str):
        """
        撤销 pipeline 后执行的钩子

        :param pipeline_id: 流程 ID
        :type pipeline_id: str
        """
        self._send_event(PipelineEvent(event_type="post_revoke_pipeline", data={"pipeline_id": pipeline_id}))

    def pre_resume_pipeline(self, pipeline_id: str):
        """
        继续 pipeline 前执行的钩子

        :param pipeline_id: 流程 ID
        :type pipeline_id: str
        """
        self._send_event(PipelineEvent(event_type="pre_resume_pipeline", data={"pipeline_id": pipeline_id}))

    def post_resume_pipeline(self, pipeline_id: str):
        """
        继续 pipeline 后执行的钩子

        :param pipeline_id: 流程 ID
        :type pipeline_id: str
        """
        self._send_event(PipelineEvent(event_type="post_resume_pipeline", data={"pipeline_id": pipeline_id}))

    def pre_resume_node(self, node_id: str):
        """
        继续节点后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        """
        self._send_event(PipelineEvent(event_type="post_resume_pipeline", data={"node_id": node_id}))

    def post_resume_node(self, node_id: str):
        """
        继续节点后执行的钩子

        :param node_id: [description]节点 ID
        :type node_id: str
        """
        self._send_event(PipelineEvent(event_type="post_resume_node", data={"node_id": node_id}))

    def pre_pause_node(self, node_id: str):
        """
        暂停节点前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        """
        self._send_event(PipelineEvent(event_type="pre_pause_node", data={"node_id": node_id}))

    def post_pause_node(self, node_id: str):
        """
        暂停节点后执行的钩子

        :param node_id: [description]节点 ID
        :type node_id: str
        """
        self._send_event(PipelineEvent(event_type="post_pause_node", data={"node_id": node_id}))

    def pre_retry_node(self, node_id: str, data: Optional[dict]):
        """
        重试节点前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param data: 重试时使用的节点执行输入
        :type data: Optional[dict]
        """
        self._send_event(PipelineEvent(event_type="pre_retry_node", data={"node_id": node_id}))

    def post_retry_node(self, node_id: str, data: Optional[dict]):
        """
        重试节点后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param data: 重试时使用的节点执行输入
        :type data: Optional[dict]
        """
        self._send_event(PipelineEvent(event_type="post_retry_node", data={"node_id": node_id, "data": data}))

    def pre_skip_node(self, node_id: str):
        """
        跳过节点前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        """
        self._send_event(
            PipelineEvent(
                event_type="pre_skip_node",
                data={
                    "node_id": node_id,
                },
            )
        )

    def post_skip_node(self, node_id: str):
        """
        跳过节点后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        """
        self._send_event(
            PipelineEvent(
                event_type="post_skip_node",
                data={
                    "node_id": node_id,
                },
            )
        )

    def pre_skip_exclusive_gateway(self, node_id: str, flow_id: str):
        """
        跳过分支网关前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param flow_id: 跳过后选择的目标流 ID
        :type flow_id: str
        """
        self._send_event(
            PipelineEvent(event_type="pre_skip_exclusive_gateway", data={"node_id": node_id, "flow_id": flow_id})
        )

    def post_skip_exclusive_gateway(self, node_id: str, flow_id: str):
        """
        跳过分支网关后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param flow_id: 跳过后选择的目标流 ID
        :type flow_id: str
        """
        self._send_event(
            PipelineEvent(event_type="post_skip_exclusive_gateway", data={"node_id": node_id, "flow_id": flow_id})
        )

    def pre_skip_conditional_parallel_gateway(self, node_id: str, flow_ids: list, converge_gateway_id: str):
        """
        跳过条件并行网关前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param flow_ids: 跳过后选择的目标流 ID 列表
        :type flow_ids: list
        :param converge_gateway_id: 目标汇聚网关 ID
        :type converge_gateway_id: str
        """
        self._send_event(
            PipelineEvent(
                event_type="pre_skip_conditional_parallel_gateway",
                data={"node_id": node_id, "flow_ids": flow_ids, "converge_gateway_id": converge_gateway_id},
            )
        )

    def post_skip_conditional_parallel_gateway(self, node_id: str, flow_ids: list, converge_gateway_id: str):
        """
        跳过条件并行网关后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param flow_ids: 跳过后选择的目标流 ID 列表
        :type flow_ids: list
        :param converge_gateway_id: 目标汇聚网关 ID
        :type converge_gateway_id: str
        """
        self._send_event(
            PipelineEvent(
                event_type="post_skip_conditional_parallel_gateway",
                data={"node_id": node_id, "flow_ids": flow_ids, "converge_gateway_id": converge_gateway_id},
            )
        )

    def pre_forced_fail_activity(self, node_id: str, ex_data: str):
        """
        强制失败节点前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param ex_data: 写入节点执行数据的失败信息
        :type ex_data: str
        """
        self._send_event(
            PipelineEvent(
                event_type="pre_forced_fail_activity",
                data={
                    "node_id": node_id,
                    "ex_data": ex_data,
                },
            )
        )

    def post_forced_fail_activity(self, node_id: str, ex_data: str, old_version: str, new_version: str):
        """
        强制失败节点后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param ex_data: 写入节点执行数据的失败信息
        :type ex_data: str
        :param old_version: 强制失败前的节点版本
        :type old_version: str
        :param new_version: 强制失败后的节点版本
        :type new_version: str
        """
        # 在强制失败刷新版本后更新已经记录的日志的版本
        LogEntry.objects.filter(node_id=node_id, version=old_version).update(version=new_version)
        self._send_event(
            PipelineEvent(
                event_type="post_forced_fail_activity",
                data={"node_id": node_id, "ex_data": ex_data, "old_version": old_version, "new_version": new_version},
            )
        )

    def pre_callback(self, node_id: str, version: str, data: str):
        """
        回调节点前执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param version: 节点执行版本
        :type version: str
        :param data: 回调数据
        :type data: str
        """
        self._send_event(
            PipelineEvent(event_type="pre_callback", data={"node_id": node_id, "version": version, "data": data})
        )

    def post_callback(self, node_id: str, version: str, data: str):
        """
        回调节点后执行的钩子

        :param node_id: 节点 ID
        :type node_id: str
        :param version: 节点执行版本
        :type version: str
        :param data: 回调数据
        :type data: str
        """
        self._send_event(
            PipelineEvent(event_type="post_callback", data={"node_id": node_id, "version": version, "data": data})
        )

    def pre_retry_subprocess(self, node_id: str):
        """
        子流程重试前执行的钩子

        :param node_id: 子流程节点 ID
        :type node_id: str
        """
        self._send_event(PipelineEvent(event_type="pre_retry_subprocess", data={"node_id": node_id}))

    def post_retry_subprocess(self, node_id: str):
        """
        子流程重试后执行的钩子

        :param node_id: 子流程节点 ID
        :type node_id: str
        """
        self._send_event(PipelineEvent(event_type="post_retry_subprocess", data={"node_id": node_id}))

    def pre_execute_node(
        self, root_pipeline_id: str, node_id: str, data: ExecutionData, root_pipeline_data: ExecutionData
    ):
        """
        节点execute方法执行之前需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        :param data: 写入节点执行数据的失败信息
        :type data: ExecutionData
        :param root_pipeline_data: 写入节点执行数据的失败信息
        :type root_pipeline_data: ExecutionData
        """
        self._send_event(
            PipelineEvent(
                event_type="pre_execute_node",
                data={
                    "root_pipeline_id": root_pipeline_id,
                    "node_id": node_id,
                    "data": data,
                    "root_pipeline_data": root_pipeline_data,
                },
            )
        )

    def post_execute_node(
        self, root_pipeline_id: str, node_id: str, data: ExecutionData, root_pipeline_data: ExecutionData
    ):
        """
        节点execute方法执行之后需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        :param data: 写入节点执行数据的失败信息
        :type data: ExecutionData
        :param root_pipeline_data: 写入节点执行数据的失败信息
        :type root_pipeline_data: ExecutionData
        """
        self._send_event(
            PipelineEvent(
                event_type="post_execute_node",
                data={
                    "root_pipeline_id": root_pipeline_id,
                    "node_id": node_id,
                    "data": data,
                    "root_pipeline_data": root_pipeline_data,
                },
            )
        )

    def node_execute_fail(
        self, root_pipeline_id: str, node_id: str, data: ExecutionData, root_pipeline_data: ExecutionData, ex_data: str
    ):
        """
        节点execute方法异常需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        :param data: 写入节点执行数据的失败信息
        :type data: ExecutionData
        :param root_pipeline_data: 写入节点执行数据的失败信息
        :type root_pipeline_data: ExecutionData
        :param ex_data: 节点异常信息
        :type root_pipeline_data: str
        """
        self._send_event(
            PipelineEvent(
                event_type="node_execute_fail",
                data={
                    "root_pipeline_id": root_pipeline_id,
                    "node_id": node_id,
                    "data": data,
                    "root_pipeline_data": root_pipeline_data,
                    "ex_data": ex_data,
                },
            )
        )

    def pre_schedule_node(
        self, root_pipeline_id: str, node_id: str, data: ExecutionData, root_pipeline_data: ExecutionData
    ):
        """
        节点schedule方法执行之前需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        :param data: 写入节点执行数据的失败信息
        :type data: ExecutionData
        :param root_pipeline_data: 写入节点执行数据的失败信息
        :type root_pipeline_data: ExecutionData
        """
        self._send_event(
            PipelineEvent(
                event_type="pre_schedule_node",
                data={
                    "root_pipeline_id": root_pipeline_id,
                    "node_id": node_id,
                    "data": data,
                    "root_pipeline_data": root_pipeline_data,
                },
            )
        )

    def post_schedule_node(
        self, root_pipeline_id: str, node_id: str, data: ExecutionData, root_pipeline_data: ExecutionData
    ):
        """
        节点schedule方法执行之后需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        :param data: 写入节点执行数据的失败信息
        :type data: ExecutionData
        :param root_pipeline_data: 写入节点执行数据的失败信息
        :type root_pipeline_data: ExecutionData
        """
        self._send_event(
            PipelineEvent(
                event_type="post_schedule_node",
                data={
                    "root_pipeline_id": root_pipeline_id,
                    "node_id": node_id,
                    "data": data,
                    "root_pipeline_data": root_pipeline_data,
                },
            )
        )

    def node_schedule_fail(
        self, root_pipeline_id: str, node_id: str, data: ExecutionData, root_pipeline_data: ExecutionData, ex_data: str
    ):
        """
        节点schedule方法异常需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        :param data: 写入节点执行数据的失败信息
        :type data: ExecutionData
        :param root_pipeline_data: 写入节点执行数据的失败信息
        :type root_pipeline_data: ExecutionData
        :param ex_data: 节点异常信息
        :type root_pipeline_data: str
        """
        self._send_event(
            PipelineEvent(
                event_type="node_schedule_fail",
                data={
                    "root_pipeline_id": root_pipeline_id,
                    "node_id": node_id,
                    "data": data,
                    "root_pipeline_data": root_pipeline_data,
                    "ex_data": data,
                },
            )
        )

    def leave_node(self, root_pipeline_id: str, node_id: str):
        """
        离开节点需要执行的钩子
        :param root_pipeline_id: 任务ID
        :type node_id: str
        :param node_id: 节点ID
        :type node_id: str
        """
        self._send_event(
            PipelineEvent(event_type="leave_node", data={"root_pipeline_id": root_pipeline_id, "node_id": node_id})
        )
