# -*- coding: utf-8 -*-
import json

from celery import task
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
from bamboo_engine.utils.graph import Graph


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

        graph = json.loads(self.snapshot.graph)
        need_clean_node_id_list = graph["nodes"]
        # 清理状态信息
        State.objects.filter(root_id=self.snapshot.root_pipeline_id, node_id__in=need_clean_node_id_list).delete()
        # 清理Schedule 信息
        Schedule.objects.filter(node_id__in=need_clean_node_id_list).delete()
        # 清理日志信息
        LogEntry.objects.filter(node_id__in=need_clean_node_id_list).delete()
        ExecutionHistory.objects.filter(node_id__in=need_clean_node_id_list).delete()
        DBExecutionData.objects.filter(node_id__in=need_clean_node_id_list).delete()
        CallbackData.objects.filter(node_id__in=need_clean_node_id_list).delete()


class RollbackTaskHandler:
    def __init__(self, snapshot_id, node_id, retry, retry_data):
        self.snapshot_id = snapshot_id
        self.node_id = node_id
        self.retry_data = retry_data
        self.retry = retry
        self.runtime = BambooDjangoRuntime()

    def set_state(self, node_id, state):
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

        try:
            # 获取节点快照，可能会有多多份快照，需要多次回滚
            node_snapshots = RollbackNodeSnapshot.objects.filter(node_id=self.node_id, rolled_back=False).order_by(
                "-id"
            )
            for node_snapshot in node_snapshots:
                service = self.runtime.get_service(code=node_snapshot.code, version=node_snapshot.version)
                data = ExecutionData(inputs=json.loads(node_snapshot.inputs), outputs=json.loads(node_snapshot.outputs))
                parent_data = ExecutionData(inputs=json.loads(node_snapshot.context_values), outputs={})
                result = service.service.rollback(data, parent_data, self.retry_data)
                node_snapshot.rolled_back = True
                node_snapshot.save()
                if not result:
                    return False
        except Exception:
            return False

        return True

    def start_pipeline(self, root_pipeline_id, target_node_id):
        """
        启动pipeline
        """
        try:
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
            self.runtime.execute(
                process_id=process_info.process_id,
                node_id=target_node_id,
                root_pipeline_id=process_info.root_pipeline_id,
                parent_pipeline_id=process_info.top_pipeline_id,
            )
            # 设置pipeline的状态
            self.runtime.set_state(
                node_id=root_pipeline_id,
                to_state=states.READY,
            )
            self.runtime.set_state(
                node_id=root_pipeline_id,
                to_state=states.RUNNING,
            )
        except Exception as e:
            raise Exception("rollback failed: rollback to node error, error={}".format(str(e)))

    def rollback(self):
        with transaction.atomic():
            rollback_snapshot = RollbackSnapshot.objects.select_for_update().get(id=self.snapshot_id)
            node_access_record = json.loads(rollback_snapshot.node_access_record)
            # 只有非重试状态下才需要记录访问
            if not self.retry:
                node_access_record[self.node_id] += 1
                rollback_snapshot.node_access_record = json.dumps(node_access_record)
                rollback_snapshot.save()

        graph = json.loads(rollback_snapshot.graph)
        target_node_id = rollback_snapshot.target_node_id
        rollback_graph = Graph(nodes=graph["nodes"], flows=graph["flows"])
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
                except Exception:
                    # 节点和流程重置为回滚失败的状态
                    self.set_state(rollback_snapshot.root_pipeline_id, states.ROLL_BACK_FAILED)
                    # 回滚失败的节点将不再向下执行
                    self.set_state(self.node_id, states.ROLL_BACK_FAILED)
                    return

                # 节点回滚成功
                if result:
                    self.set_state(self.node_id, states.ROLL_BACK_SUCCESS)
                else:
                    self.set_state(self.node_id, states.ROLL_BACK_FAILED)
                    # 回滚失败的节点将不再向下执行
                    self.set_state(rollback_snapshot.root_pipeline_id, states.ROLL_BACK_FAILED)
                    return

            next_node = rollback_graph.next(self.node_id)
            if list(next_node)[0] == constants.END_FLAG:
                self.set_state(rollback_snapshot.root_pipeline_id, states.ROLL_BACK_SUCCESS)
                # 清理数据
                clearner.clear_data()
                self.start_pipeline(root_pipeline_id=rollback_snapshot.root_pipeline_id, target_node_id=target_node_id)
            for node in next_node:
                rollback.apply_async(
                    kwargs={
                        "snapshot_id": self.snapshot_id,
                        "node_id": node,
                    },
                    queue=ROLLBACK_QUEUE,
                )


@task
def rollback(snapshot_id, node_id, retry=False, retry_data=None):
    """
    snapshot_id 本次回滚的快照id
    node_id  当前要回滚的节点id
    """
    RollbackTaskHandler(snapshot_id=snapshot_id, node_id=node_id, retry=retry, retry_data=retry_data).rollback()
