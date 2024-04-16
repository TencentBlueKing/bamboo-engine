# -*- coding: utf-8 -*-
import json
import logging

from celery import current_app
from django.conf import settings
from django.db import transaction
from pipeline.conf.default_settings import ROLLBACK_QUEUE
from pipeline.contrib.rollback import constants
from pipeline.contrib.rollback.models import (
    RollbackNodeSnapshot,
    RollbackPlan,
    RollbackSnapshot,
)
from pipeline.eri.models import CallbackData
from pipeline.eri.models import ExecutionData as DBExecutionData
from pipeline.eri.models import (
    ExecutionHistory,
    LogEntry,
    Node,
    Process,
    Schedule,
    State,
)
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine import states
from bamboo_engine.eri import ExecutionData
from bamboo_engine.utils.graph import RollbackGraph

logger = logging.getLogger("celery")


class RollbackCleaner:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def _clear_node_reserve_flag(self, node_id):
        node = Node.objects.get(node_id=node_id)
        node_detail = json.loads(node.detail)
        node_detail["reserve_rollback"] = False
        node.detail = json.dumps(node_detail)
        node.save()

    def clear_data(self):
        # 节点快照需要全部删除，可能会有下一次的回滚
        RollbackNodeSnapshot.objects.filter(root_pipeline_id=self.snapshot.root_pipeline_id).delete()
        # 回滚快照需要置为已过期
        RollbackSnapshot.objects.filter(root_pipeline_id=self.snapshot.root_pipeline_id).update(is_expired=True)
        # 预约计划需要修改为已过期
        RollbackPlan.objects.filter(
            root_pipeline_id=self.snapshot.root_pipeline_id, start_node_id=self.snapshot.start_node_id
        ).update(is_expired=True)
        # 节点的预约信息需要清理掉
        self._clear_node_reserve_flag(self.snapshot.start_node_id)
        # 需要删除该节点的进程信息/非主进程的，防止网关再分支处回滚时，仍然有正在运行的process得不到清理
        Process.objects.filter(
            root_pipeline_id=self.snapshot.root_pipeline_id, current_node_id=self.snapshot.start_node_id
        ).exclude(parent_id=-1).delete()

        graph = json.loads(self.snapshot.graph)
        need_clean_node_id_list = graph["nodes"] + json.loads(self.snapshot.other_nodes)
        # 清理状态信息
        State.objects.filter(root_id=self.snapshot.root_pipeline_id, node_id__in=need_clean_node_id_list).delete()
        # 清理Schedule 信息
        Schedule.objects.filter(node_id__in=need_clean_node_id_list).delete()
        # 清理日志信息
        LogEntry.objects.filter(node_id__in=need_clean_node_id_list).delete()
        ExecutionHistory.objects.filter(node_id__in=need_clean_node_id_list).delete()
        DBExecutionData.objects.filter(node_id__in=need_clean_node_id_list).delete()
        CallbackData.objects.filter(node_id__in=need_clean_node_id_list).delete()


class TokenRollbackTaskHandler:
    def __init__(self, snapshot_id, node_id, retry, retry_data):
        self.snapshot_id = snapshot_id
        self.node_id = node_id
        self.retry_data = retry_data
        self.retry = retry
        self.runtime = BambooDjangoRuntime()

    def set_state(self, node_id, state):
        logger.info("[TokenRollbackTaskHandler][set_state] set node_id state to {}".format(state))
        # 开始和结束节点直接跳过回滚
        if node_id in [constants.END_FLAG, constants.START_FLAG]:
            return
        self.runtime.set_state(
            node_id=node_id,
            to_state=state,
        )

    def execute_rollback(self):
        """
        执行回滚的操作
        """
        if self.node_id in [constants.END_FLAG, constants.START_FLAG]:
            return True

        # 获取节点快照，可能会有多多份快照，需要多次回滚
        node_snapshots = RollbackNodeSnapshot.objects.filter(node_id=self.node_id, rolled_back=False).order_by("-id")
        for node_snapshot in node_snapshots:
            service = self.runtime.get_service(code=node_snapshot.code, version=node_snapshot.version)
            data = ExecutionData(inputs=node_snapshot.inputs, outputs=node_snapshot.outputs)
            parent_data = ExecutionData(inputs=node_snapshot.context_values, outputs={})
            result = service.service.rollback(data, parent_data, self.retry_data)
            node_snapshot.rolled_back = True
            node_snapshot.save()
            if not result:
                return False

        return True

    def start_pipeline(self, root_pipeline_id, target_node_id):
        """
        启动pipeline
        """
        # 将当前住进程的正在运行的节点指向目标ID
        main_process = Process.objects.get(root_pipeline_id=root_pipeline_id, parent_id=-1)
        main_process.current_node_id = target_node_id
        main_process.save()

        # 重置该节点的状态信息
        self.runtime.set_state(
            node_id=target_node_id,
            to_state=states.READY,
            is_retry=True,
            refresh_version=True,
            clear_started_time=True,
            clear_archived_time=True,
        )

        process_info = self.runtime.get_process_info(main_process.id)
        # 设置pipeline的状态
        self.runtime.set_state(
            node_id=root_pipeline_id,
            to_state=states.READY,
        )

        # 如果开启了流程自动回滚，则会开启到目标节点之后自动开始
        if getattr(settings, "PIPELINE_ENABLE_AUTO_EXECUTE_WHEN_ROLL_BACKED", True):
            self.runtime.set_state(
                node_id=root_pipeline_id,
                to_state=states.RUNNING,
            )
        else:
            # 流程设置为暂停状态，需要用户点击才可以继续开始
            self.runtime.set_state(
                node_id=root_pipeline_id,
                to_state=states.SUSPENDED,
            )

        self.runtime.execute(
            process_id=process_info.process_id,
            node_id=target_node_id,
            root_pipeline_id=process_info.root_pipeline_id,
            parent_pipeline_id=process_info.top_pipeline_id,
        )

    def rollback(self):
        with transaction.atomic():
            rollback_snapshot = RollbackSnapshot.objects.select_for_update().get(id=self.snapshot_id, is_expired=False)
            node_access_record = json.loads(rollback_snapshot.node_access_record)
            # 只有非重试状态下才需要记录访问
            if not self.retry:
                node_access_record[self.node_id] += 1
                rollback_snapshot.node_access_record = json.dumps(node_access_record)
                rollback_snapshot.save()

        graph = json.loads(rollback_snapshot.graph)
        target_node_id = rollback_snapshot.target_node_id
        rollback_graph = RollbackGraph(nodes=graph["nodes"], flows=graph["flows"])
        skip_rollback_nodes = json.loads(rollback_snapshot.skip_rollback_nodes)
        in_degrees = rollback_graph.in_degrees()

        clearner = RollbackCleaner(rollback_snapshot)

        if node_access_record[self.node_id] >= in_degrees[self.node_id]:
            # 对于不需要跳过的节点才会执行具体的回滚行为
            if self.node_id not in skip_rollback_nodes:
                try:
                    # 设置节点状态为回滚中
                    self.set_state(self.node_id, states.ROLLING_BACK)
                    # 执行同步回滚的操作
                    result = self.execute_rollback()
                except Exception as e:
                    logger.error(
                        "[TokenRollbackTaskHandler][rollback] execute rollback error,"
                        "snapshot_id={}, node_id={}, err={}".format(self.snapshot_id, self.node_id, e)
                    )
                    # 节点和流程重置为回滚失败的状态
                    self.set_state(rollback_snapshot.root_pipeline_id, states.ROLL_BACK_FAILED)
                    # 回滚失败的节点将不再向下执行
                    self.set_state(self.node_id, states.ROLL_BACK_FAILED)
                    return

                # 节点回滚成功
                if result:
                    self.set_state(self.node_id, states.ROLL_BACK_SUCCESS)
                else:
                    logger.info(
                        "[TokenRollbackTaskHandler][rollback], execute rollback failed, "
                        "result=False, snapshot_id={}, node_id={}".format(self.snapshot_id, self.node_id)
                    )
                    self.set_state(self.node_id, states.ROLL_BACK_FAILED)
                    # 回滚失败的节点将不再向下执行
                    self.set_state(rollback_snapshot.root_pipeline_id, states.ROLL_BACK_FAILED)
                    return

            next_node = rollback_graph.next(self.node_id)
            if list(next_node)[0] == constants.END_FLAG:
                self.set_state(rollback_snapshot.root_pipeline_id, states.ROLL_BACK_SUCCESS)
                try:
                    clearner.clear_data()
                    self.start_pipeline(
                        root_pipeline_id=rollback_snapshot.root_pipeline_id, target_node_id=target_node_id
                    )
                except Exception as e:
                    logger.error("[TokenRollbackTaskHandler][rollback] start_pipeline failed, err={}".format(e))
                    return
                return

            for node in next_node:
                token_rollback.apply_async(
                    kwargs={
                        "snapshot_id": self.snapshot_id,
                        "node_id": node,
                    },
                    queue=ROLLBACK_QUEUE,
                )


class AnyRollbackHandler:
    def __init__(self, snapshot_id):
        self.snapshot_id = snapshot_id
        self.runtime = BambooDjangoRuntime()

    def start_pipeline(self, root_pipeline_id, target_node_id):
        """
        启动pipeline
        """

        main_process = Process.objects.get(root_pipeline_id=root_pipeline_id, parent_id=-1)
        main_process.current_node_id = target_node_id
        main_process.save()

        # 重置该节点的状态信息
        self.runtime.set_state(
            node_id=target_node_id,
            to_state=states.READY,
            is_retry=True,
            refresh_version=True,
            clear_started_time=True,
            clear_archived_time=True,
        )

        process_info = self.runtime.get_process_info(main_process.id)

        # 如果PIPELINE_ENABLE_AUTO_EXECUTE_WHEN_ROLL_BACKED为False, 那么则会重制流程为暂停状态
        if not getattr(settings, "PIPELINE_ENABLE_AUTO_EXECUTE_WHEN_ROLL_BACKED", True):
            self.runtime.set_state(
                node_id=root_pipeline_id,
                to_state=states.SUSPENDED,
            )

        self.runtime.execute(
            process_id=process_info.process_id,
            node_id=target_node_id,
            root_pipeline_id=process_info.root_pipeline_id,
            parent_pipeline_id=process_info.top_pipeline_id,
        )

    def rollback(self):
        with transaction.atomic():
            rollback_snapshot = RollbackSnapshot.objects.get(id=self.snapshot_id, is_expired=False)
            clearner = RollbackCleaner(rollback_snapshot)
            try:
                clearner.clear_data()
                self.start_pipeline(
                    root_pipeline_id=rollback_snapshot.root_pipeline_id, target_node_id=rollback_snapshot.target_node_id
                )
            except Exception as e:
                logger.error(
                    "rollback failed: start pipeline, pipeline_id={}, target_node_id={}, error={}".format(
                        rollback_snapshot.root_pipeline_id, rollback_snapshot.target_node_id, str(e)
                    )
                )
                raise e


@current_app.task
def token_rollback(snapshot_id, node_id, retry=False, retry_data=None):
    """
    snapshot_id 本次回滚的快照id
    node_id  当前要回滚的节点id
    """
    TokenRollbackTaskHandler(snapshot_id=snapshot_id, node_id=node_id, retry=retry, retry_data=retry_data).rollback()


@current_app.task
def any_rollback(snapshot_id):
    AnyRollbackHandler(snapshot_id=snapshot_id).rollback()
