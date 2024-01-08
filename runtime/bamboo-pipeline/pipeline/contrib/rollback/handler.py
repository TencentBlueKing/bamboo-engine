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
from django.db.models import Q
from pipeline.conf.default_settings import ROLLBACK_QUEUE
from pipeline.contrib.exceptions import RollBackException
from pipeline.contrib.rollback import constants
from pipeline.contrib.rollback.constants import ANY, TOKEN
from pipeline.contrib.rollback.graph import RollbackGraphHandler
from pipeline.contrib.rollback.models import (
    RollbackPlan,
    RollbackSnapshot,
    RollbackToken,
)
from pipeline.contrib.rollback.tasks import any_rollback, token_rollback
from pipeline.core.constants import PE
from pipeline.eri.models import Node, Process, State
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine import states


class RollbackValidator:
    @staticmethod
    def validate_pipeline(root_pipeline_id):
        pipeline_state = State.objects.filter(node_id=root_pipeline_id).first()
        if not pipeline_state:
            raise RollBackException(
                "rollback failed: pipeline state not exist, pipeline_id={}".format(root_pipeline_id)
            )

        if pipeline_state.name not in [states.RUNNING, states.ROLL_BACK_FAILED]:
            raise RollBackException(
                "rollback failed: the task of non-running state is not allowed to roll back, "
                "pipeline_id={}, state={}".format(root_pipeline_id, pipeline_state.name)
            )

    @staticmethod
    def validate_node(node_id, allow_failed=False):
        node = Node.objects.filter(node_id=node_id).first()
        if node is None:
            raise RollBackException("rollback failed: node not exist, node={}".format(node_id))

        node_detail = json.loads(node.detail)
        if node_detail["type"] not in [PE.ServiceActivity, PE.EmptyStartEvent]:
            raise RollBackException("rollback failed: only allows rollback to ServiceActivity type nodes")

        target_node_state = State.objects.filter(node_id=node_id).first()

        if target_node_state is None:
            raise RollBackException("rollback failed: node state not exist, node={}".format(node_id))

        allow_states = [states.FINISHED]
        if allow_failed:
            allow_states = [states.FINISHED, states.FAILED]
        if target_node_state.name not in allow_states:
            raise RollBackException(
                "rollback failed: only allows rollback to finished node, allowed states {}".format(allow_states)
            )

    @staticmethod
    def validate_token(root_pipeline_id, start_node_id, target_node_id):
        try:
            rollback_token = RollbackToken.objects.get(root_pipeline_id=root_pipeline_id)
        except RollbackToken.DoesNotExist:
            raise RollBackException(
                "rollback failed: pipeline token not exist, pipeline_id={}".format(root_pipeline_id)
            )

        tokens = json.loads(rollback_token.token)

        start_node_token = tokens.get(start_node_id)
        target_node_token = tokens.get(target_node_id)

        if start_node_token is None or target_node_token is None:
            raise RollBackException("rollback failed: token not found, pipeline_id={}".format(root_pipeline_id))

        if start_node_token != target_node_token:
            raise RollBackException(
                "rollback failed: start node token must equal target node, pipeline_id={}".format(root_pipeline_id)
            )

    @staticmethod
    def validate_node_state(root_pipeline_id, start_node_id):
        """
        使用token模式下的回滚，相同token的节点不允许有正在运行的节点
        """
        try:
            rollback_token = RollbackToken.objects.get(root_pipeline_id=root_pipeline_id)
        except RollbackToken.DoesNotExist:
            raise RollBackException(
                "rollback failed: pipeline token not exist, pipeline_id={}".format(root_pipeline_id)
            )

        tokens = json.loads(rollback_token.token)
        start_token = tokens.get(start_node_id)
        if start_token is None:
            raise RollBackException("rollback failed: can't find the not token, node_id={}".format(start_node_id))

        node_id_list = []
        for node_id, token in node_id_list:
            if token == start_token:
                node_id_list.append(node_id)

        if State.objects.filter(node_id__in=node_id_list, name=states.RUNNING).exists():
            raise RollBackException(
                "rollback failed: there is currently the same node that the same token is running, node_id={}".format(
                    start_node_id
                )
            )

    @staticmethod
    def validate_start_node_id(root_pipeline_id, start_node_id):
        """
        回滚的开始节点必须是流程的末尾节点
        """
        if not Process.objects.filter(root_pipeline_id=root_pipeline_id, current_node_id=start_node_id).exists():
            raise RollBackException("rollback failed: The node to be rolled back must be the current node!")


class BaseRollbackHandler:
    mode = None

    def __init__(self, root_pipeline_id):
        self.root_pipeline_id = root_pipeline_id
        self.runtime = BambooDjangoRuntime()
        # 检查pipeline 回滚的合法性
        RollbackValidator.validate_pipeline(root_pipeline_id)

    def get_allowed_rollback_node_id_list(self, start_node_id, **options):
        """
        获取允许回滚的节点范围
        规则：token 一致的节点允许回滚
        """
        try:
            rollback_token = RollbackToken.objects.get(root_pipeline_id=self.root_pipeline_id)
        except RollbackToken.DoesNotExist:
            raise RollBackException(
                "rollback failed: pipeline token not exist, pipeline_id={}".format(self.root_pipeline_id)
            )
        node_map = self.get_allowed_rollback_node_map()
        service_activity_node_list = [
            node_id for node_id, node_detail in node_map.items() if node_detail["type"] == PE.ServiceActivity
        ]

        tokens = json.loads(rollback_token.token)
        start_token = tokens.get(start_node_id)
        if not start_token:
            return []

        nodes = []
        for node_id, token in tokens.items():
            if start_token == token and node_id != start_node_id and node_id in service_activity_node_list:
                nodes.append(node_id)

        return nodes

    def get_allowed_rollback_node_map(self):
        # 不需要遍历整颗树，获取到现在已经执行成功和失败节点的所有列表
        finished_node_id_list = (
            State.objects.filter(root_id=self.root_pipeline_id, name__in=[states.FINISHED, states.FAILED])
            .exclude(node_id=self.root_pipeline_id)
            .values_list("node_id", flat=True)
        )
        node_detail_list = Node.objects.filter(node_id__in=finished_node_id_list)
        # 获取node_id 到 node_detail的映射
        return {n.node_id: json.loads(n.detail) for n in node_detail_list}

    def _reserve(self, start_node_id, target_node_id, reserve_rollback=True, **options):
        # 节点预约 需要在 Node 里面 插入 reserve_rollback = True, 为 True的节点执行完将暂停
        RollbackValidator.validate_start_node_id(self.root_pipeline_id, start_node_id)
        RollbackValidator.validate_node(target_node_id)
        node = Node.objects.filter(node_id=start_node_id).first()
        if node is None:
            raise RollBackException("reserve rollback failed, the node is not exists, node_id={}".format(start_node_id))

        state = State.objects.filter(node_id=start_node_id).first()
        if state is None:
            raise RollBackException(
                "reserve rollback failed, the node state is not exists, node_id={}".format(start_node_id)
            )

        # 不在执行中的节点不允许预约
        if state.name != states.RUNNING:
            raise RollBackException(
                "reserve rollback failed, the node state is not Running, current state={},  node_id={}".format(
                    state.name, start_node_id
                )
            )

        with transaction.atomic():
            if reserve_rollback:
                # 一个流程只能同时拥有一个预约任务
                if RollbackPlan.objects.filter(root_pipeline_id=self.root_pipeline_id, is_expired=False).exists():
                    raise RollBackException("reserve rollback failed, there exists another unfinished rollback plan")
                RollbackPlan.objects.create(
                    root_pipeline_id=self.root_pipeline_id,
                    start_node_id=start_node_id,
                    target_node_id=target_node_id,
                    mode=self.mode,
                    options=options,
                )
            else:
                # 取消回滚，删除所有的任务
                RollbackPlan.objects.filter(root_pipeline_id=self.root_pipeline_id, start_node_id=start_node_id).update(
                    is_expired=True
                )

            node_detail = json.loads(node.detail)
            node_detail["reserve_rollback"] = reserve_rollback
            node.detail = json.dumps(node_detail)
            node.save()

    def reserve_rollback(self, start_node_id, target_node_id, **options):
        """
        预约回滚
        """
        RollbackValidator.validate_token(self.root_pipeline_id, start_node_id, target_node_id)
        self._reserve(start_node_id, target_node_id, **options)

    def cancel_reserved_rollback(self, start_node_id, target_node_id):
        """
        取消预约回滚
        """
        self._reserve(start_node_id, target_node_id, reserve_rollback=False)


class AnyRollbackHandler(BaseRollbackHandler):
    mode = ANY

    def get_allowed_rollback_node_id_list(self, start_node_id, **options):
        # 如果开启了token跳过检查这个选项，那么将返回所有运行过的节点作为回滚范围
        if options.get("skip_check_token", False):
            node_map = self.get_allowed_rollback_node_map()
            service_activity_node_list = [
                node_id
                for node_id, node_detail in node_map.items()
                if node_detail["type"] == PE.ServiceActivity and node_id != start_node_id
            ]
            return service_activity_node_list
        return super(AnyRollbackHandler, self).get_allowed_rollback_node_id_list(start_node_id, **options)

    def retry_rollback_failed_node(self, node_id, retry_data):
        """ """
        raise RollBackException("rollback failed: when mode is any, not support retry")

    def reserve_rollback(self, start_node_id, target_node_id, **options):
        """
        预约回滚
        """
        if not options.get("skip_check_token", False):
            RollbackValidator.validate_token(self.root_pipeline_id, start_node_id, target_node_id)
        self._reserve(start_node_id, target_node_id, **options)

    def rollback(self, start_node_id, target_node_id, skip_rollback_nodes=None, **options):
        RollbackValidator.validate_start_node_id(self.root_pipeline_id, start_node_id)
        RollbackValidator.validate_node(start_node_id, allow_failed=True)
        RollbackValidator.validate_node(target_node_id)
        if not options.get("skip_check_token", False):
            RollbackValidator.validate_token(self.root_pipeline_id, start_node_id, target_node_id)
            # 相同token回滚时，不允许同一token路径上有正在运行的节点
            RollbackValidator.validate_node_state(self.root_pipeline_id, start_node_id)

        node_map = self.get_allowed_rollback_node_map()
        rollback_graph = RollbackGraphHandler(node_map=node_map, start_id=start_node_id, target_id=target_node_id)

        graph, other_nodes = rollback_graph.build_rollback_graph()
        node_access_record = {node: 0 for node in graph.nodes}

        rollback_snapshot = RollbackSnapshot.objects.create(
            root_pipeline_id=self.root_pipeline_id,
            graph=json.dumps(graph.as_dict()),
            node_access_record=json.dumps(node_access_record),
            start_node_id=start_node_id,
            target_node_id=target_node_id,
            other_nodes=json.dumps(other_nodes),
            skip_rollback_nodes=json.dumps([]),
        )

        any_rollback.apply_async(
            kwargs={"snapshot_id": rollback_snapshot.id},
            queue=ROLLBACK_QUEUE,
        )


class TokenRollbackHandler(BaseRollbackHandler):
    mode = TOKEN

    def retry_rollback_failed_node(self, node_id, retry_data):
        """
        重试回滚失败的节点
        """
        pipeline_state = State.objects.filter(node_id=self.root_pipeline_id).first()
        if pipeline_state.name != states.ROLL_BACK_FAILED:
            raise RollBackException(
                "rollback failed: only retry the failed pipeline, current_status={}".format(pipeline_state.name)
            )
        node_state = State.objects.filter(node_id=node_id).first()
        if node_state.name != states.ROLL_BACK_FAILED:
            raise RollBackException(
                "rollback failed: only retry the failed node, current_status={}".format(node_state.name)
            )

        # 获取镜像
        try:
            rollback_snapshot = RollbackSnapshot.objects.get(root_pipeline_id=self.root_pipeline_id, is_expired=False)
        except RollbackSnapshot.DoesNotExist:
            raise RollBackException("rollback failed: the rollback snapshot is not exists, please check")
        except RollbackSnapshot.MultipleObjectsReturned:
            raise RollBackException("rollback failed: found multi not expired rollback snapshot, please check")

        # 重置pipeline的状态为回滚中
        self.runtime.set_state(
            node_id=self.root_pipeline_id,
            to_state=states.ROLLING_BACK,
        )

        # 驱动这个任务
        token_rollback.apply_async(
            kwargs={
                "snapshot_id": rollback_snapshot.id,
                "node_id": node_id,
                "retry": True,
                "retry_data": retry_data,
            },
            queue=ROLLBACK_QUEUE,
        )

    def _node_state_is_failed(self, node_id):
        """
        判断该节点是不是失败的状态
        """
        node_state = State.objects.filter(node_id=node_id).first()
        if node_state.name == states.FAILED:
            return True
        return False

    def _get_failed_skip_node_id_list(self, node_id_list):
        failed_skip_node_id_list = State.objects.filter(
            Q(Q(skip=True) | Q(error_ignored=True)) & Q(node_id__in=node_id_list)
        ).values_list("node_id", flat=True)
        return failed_skip_node_id_list

    def rollback(self, start_node_id, target_node_id, skip_rollback_nodes=None, **options):

        if skip_rollback_nodes is None:
            skip_rollback_nodes = []

        # 回滚的开始节点运行失败的情况
        RollbackValidator.validate_node(start_node_id, allow_failed=True)
        RollbackValidator.validate_node(target_node_id)
        # 相同token回滚时，不允许同一token路径上有正在运行的节点
        RollbackValidator.validate_node_state(self.root_pipeline_id, start_node_id)
        RollbackValidator.validate_token(self.root_pipeline_id, start_node_id, target_node_id)

        # 如果开始节点是失败的情况，则跳过该节点的回滚操作
        if self._node_state_is_failed(start_node_id):
            skip_rollback_nodes.append(start_node_id)

        node_map = self.get_allowed_rollback_node_map()
        rollback_graph = RollbackGraphHandler(node_map=node_map, start_id=start_node_id, target_id=target_node_id)

        runtime = BambooDjangoRuntime()

        graph, other_nodes = rollback_graph.build_rollback_graph()
        node_access_record = {node: 0 for node in graph.nodes}

        # 所有失败并跳过的节点不再参与回滚
        failed_skip_node_id_list = self._get_failed_skip_node_id_list(node_map.keys())
        skip_rollback_nodes.extend(list(failed_skip_node_id_list))

        rollback_snapshot = RollbackSnapshot.objects.create(
            root_pipeline_id=self.root_pipeline_id,
            graph=json.dumps(graph.as_dict()),
            node_access_record=json.dumps(node_access_record),
            start_node_id=start_node_id,
            target_node_id=target_node_id,
            other_nodes=json.dumps(other_nodes),
            skip_rollback_nodes=json.dumps(skip_rollback_nodes),
        )

        runtime.set_state(
            node_id=self.root_pipeline_id,
            to_state=states.ROLLING_BACK,
        )
        # 驱动这个任务
        token_rollback.apply_async(
            kwargs={
                "snapshot_id": rollback_snapshot.id,
                "node_id": constants.START_FLAG,
                "retry": False,
                "retry_data": None,
            },
            queue=ROLLBACK_QUEUE,
        )


class RollbackDispatcher:
    def __init__(self, root_pipeline_id, mode):
        if mode == ANY:
            self.handler = AnyRollbackHandler(root_pipeline_id)
        elif mode == TOKEN:
            self.handler = TokenRollbackHandler(root_pipeline_id)
        else:
            raise RollBackException("rollback failed: not support this mode, please check")

    def rollback(self, start_node_id: str, target_node_id: str, skip_rollback_nodes: list = None, **options):
        self.handler.rollback(start_node_id, target_node_id, skip_rollback_nodes, **options)

    def reserve_rollback(self, start_node_id: str, target_node_id: str, **options):
        self.handler.reserve_rollback(start_node_id, target_node_id, **options)

    def retry_rollback_failed_node(self, node_id: str, retry_data: dict = None):
        self.handler.retry_rollback_failed_node(node_id, retry_data)

    def cancel_reserved_rollback(self, start_node_id: str, target_node_id: str):
        self.handler.cancel_reserved_rollback(start_node_id, target_node_id)

    def get_allowed_rollback_node_id_list(self, start_node_id: str, **options):
        return self.handler.get_allowed_rollback_node_id_list(start_node_id, **options)
