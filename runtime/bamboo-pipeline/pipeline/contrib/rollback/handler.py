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

import json

from django.db import transaction
from pipeline.contrib.exceptions import RollBackException
from pipeline.core.constants import PE
from pipeline.eri.models import (
    CallbackData,
    ExecutionData,
    ExecutionHistory,
    LogEntry,
    Node,
    Process,
    Schedule,
    State,
)
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine import api, states


class RollBackHandler:
    def __init__(self, root_pipeline_id, node_id):
        self.root_pipeline_id = root_pipeline_id
        self.node_id = node_id
        self.runtime = BambooDjangoRuntime()

    def _compute_validate_nodes(self, node_id, node_map, nodes=None):
        """
        计算并得到一个允许回调的节点列表。
        该方法的实现思路如下，从开始节点开始遍历，通过每个节点的 targets 获取到该节点的下一个节点
        - 对于并行网关和条件并行网关将直接跳过
        - 对于分支网关，则会裁剪只保留执行的那条分支
        - node_map 记录了所有已经执行过的节点的信息，当遍历到node_map中不存在的节点时，意味着已经遍历到了当前未执行的节点
        此时会停止计算
        """

        if nodes is None:
            nodes = []
        node_detail = node_map.get(node_id)
        # 当搜索不到时，说明已经扫描了所有已经执行过的节点了，此时直接结束
        if node_detail is None:
            return nodes

        if node_detail["type"] == PE.ServiceActivity:
            nodes.append(node_id)

        # 对于并行网关，无法跳转到任何路径
        if node_detail["type"] in [PE.ParallelGateway, PE.ConditionalParallelGateway]:
            targets = [node_detail.get(PE.converge_gateway_id)]
        # 对于分支网关内的, 只允许跳转到已经执行过的路径
        elif node_detail["type"] == PE.ExclusiveGateway:
            targets = [target for target in node_detail.get("targets", {}).values() if target in node_map.keys()]
        else:
            targets = node_detail.get("targets", {}).values()

        for target in targets:
            # 如果目标节点已经出现在了node中，说明出现了环，跳过该分支
            if target in nodes:
                continue
            self._compute_validate_nodes(target, node_map, nodes)

        return nodes

    def _clean_engine_data(self, target_state):
        """
        执行清理工作
        """
        # 获取当前正在运行的节点
        state_list = State.objects.filter(root_id=self.root_pipeline_id, name=states.RUNNING).exclude(
            node_id=self.root_pipeline_id
        )
        for state in state_list:
            # 强制失败这些节点
            result = api.forced_fail_activity(self.runtime, node_id=state.node_id, ex_data="")
            if not result.result:
                raise RollBackException(
                    "rollback failed: forced_fail_activity failed, node_id={}, message={}".format(
                        target_state.node_id, result.message
                    )
                )

        # 之后清理多余的进程信息，只保留主process即可。
        Process.objects.filter(root_pipeline_id=self.root_pipeline_id).exclude(parent_id=-1).delete()

        # 查询到所有在该节点之后创建的状态信息
        need_clean_node_id_list = list(
            State.objects.filter(root_id=self.root_pipeline_id, created_time__gt=target_state.created_time).values_list(
                "node_id", flat=True
            )
        )
        # 同时清理掉目标节点的信息
        need_clean_node_id_list.append(target_state.node_id)

        # 清理状态信息
        State.objects.filter(root_id=self.root_pipeline_id, node_id__in=need_clean_node_id_list).delete()
        # 清理Schedule 信息
        Schedule.objects.filter(node_id__in=need_clean_node_id_list).delete()
        # 清理日志信息
        LogEntry.objects.filter(node_id__in=need_clean_node_id_list).delete()
        ExecutionHistory.objects.filter(node_id__in=need_clean_node_id_list).delete()
        ExecutionData.objects.filter(node_id__in=need_clean_node_id_list).delete()
        CallbackData.objects.filter(node_id__in=need_clean_node_id_list).delete()

    def get_allowed_rollback_node_id_list(self):
        """
        获取允许回退的节点id列表
        """
        # 不需要遍历整颗树，获取到现在已经执行成功的所有列表
        finished_node_id_list = (
            State.objects.filter(root_id=self.root_pipeline_id, name=states.FINISHED)
            .exclude(node_id=self.root_pipeline_id)
            .values_list("node_id", flat=True)
        )

        # 获取到除pipeline节点之外第一个被创建的节点，此时是开始节点
        start_node_state = (
            State.objects.filter(root_id=self.root_pipeline_id)
            .exclude(node_id=self.root_pipeline_id)
            .order_by("created_time")
            .first()
        )

        # 获取到所有当前已经运行完节点的详情
        node_detail_list = Node.objects.filter(node_id__in=finished_node_id_list)
        # 获取node_id 到 node_detail的映射
        node_map = {n.node_id: json.loads(n.detail) for n in node_detail_list}

        # 计算当前允许跳过的合法的节点
        validate_nodes_list = self._compute_validate_nodes(start_node_state.node_id, node_map)

        return validate_nodes_list

    def rollback(self):
        pipeline_state = State.objects.filter(node_id=self.root_pipeline_id).first()
        if not pipeline_state:
            raise RollBackException(
                "rollback failed: pipeline state not exist, pipeline_id={}".format(self.root_pipeline_id)
            )

        if pipeline_state.name != states.RUNNING:
            raise RollBackException(
                "rollback failed: the task of non-running state is not allowed to roll back, pipeline_id={}".format(
                    self.root_pipeline_id
                )
            )

        node = Node.objects.filter(node_id=self.node_id).first()
        if node is None:
            raise RollBackException("rollback failed: node not exist, node={}".format(self.node_id))

        node_detail = json.loads(node.detail)
        if node_detail["type"] not in [PE.ServiceActivity, PE.EmptyStartEvent]:
            raise RollBackException("rollback failed: only allows rollback to ServiceActivity type nodes")

        target_node_state = State.objects.filter(node_id=self.node_id).first()

        if target_node_state is None:
            raise RollBackException("rollback failed: node state not exist, node={}".format(self.node_id))

        if target_node_state.name != states.FINISHED:
            raise RollBackException("rollback failed: only allows rollback to finished node")

        validate_nodes_list = self.get_allow_rollback_node_id_list()

        if self.node_id not in validate_nodes_list:
            raise RollBackException("rollback failed: node is not allow to rollback, node={}".format(self.node_id))

        with transaction.atomic():
            try:
                self._clean_engine_data(target_node_state)
            except Exception as e:
                raise RollBackException("rollback failed: clean engine data error, error={}".format(str(e)))

            try:
                # 将当前住进程的正在运行的节点指向目标ID
                main_process = Process.objects.get(root_pipeline_id=self.root_pipeline_id, parent_id=-1)
                main_process.current_node_id = self.node_id
                main_process.save()

                # 重置该节点的状态信息
                self.runtime.set_state(
                    node_id=self.node_id,
                    to_state=states.READY,
                    is_retry=True,
                    refresh_version=True,
                    clear_started_time=True,
                    clear_archived_time=True,
                )
                process_info = self.runtime.get_process_info(main_process.id)
                self.runtime.execute(
                    process_id=process_info.process_id,
                    node_id=self.node_id,
                    root_pipeline_id=process_info.root_pipeline_id,
                    parent_pipeline_id=process_info.top_pipeline_id,
                )
            except Exception as e:
                raise RollBackException("rollback failed: rollback to node error, error={}".format(str(e)))
