# -*- coding: utf-8 -*-
import json

from django.db import transaction
from pipeline.core.constants import PE
from pipeline.eri.models import Process, ExecutionHistory, ExecutionData, CallbackData
from bamboo_engine import api
from bamboo_engine import states
from pipeline.eri.models import State
from pipeline.eri.models import Node
from pipeline.eri.models import Schedule
from pipeline.eri.models import LogEntry
from pipeline.eri.runtime import BambooDjangoRuntime

from pipeline.contrib.exceptions import RollBackException


def compute_validate_nodes(node_id, nodes, node_map):
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
        compute_validate_nodes(target, nodes, node_map)

    return nodes


def clean_engine_data(runtime, pipeline_id, target_state):
    """
    执行清理工作
    """
    # 获取当前正在运行的节点
    state_list = State.objects.filter(root_id=pipeline_id, name=states.RUNNING).exclude(node_id=pipeline_id)
    for state in state_list:
        # 强制失败这些节点
        result = api.forced_fail_activity(runtime, node_id=state.node_id, ex_data="")
        if not result.result:
            raise RollBackException(
                "rollback failed: forced_fail_activity failed, node_id={}, message={}".format(target_state.node_id,
                                                                                              result.message))

    # 之后清理多余的进程信息
    Process.objects.filter(root_pipeline_id=pipeline_id).exclude(parent_id=-1).delete()

    # 查询到所有在该节点之后创建的状态信息
    need_clean_node_id_list = list(State.objects.filter(root_id=pipeline_id,
                                                        created_time__gt=target_state.created_time).values_list(
        "node_id",
        flat=True))
    # 同时清理掉目标节点的信息
    need_clean_node_id_list.append(target_state.node_id)
    clean_node_data(pipeline_id, node_ids=need_clean_node_id_list)


def clean_node_data(pipeline_id, node_ids):
    # 清理状态信息
    State.objects.filter(root_id=pipeline_id, node_id__in=node_ids).delete()
    # 清理Schedule 信息
    Schedule.objects.filter(node_id__in=node_ids).delete()
    # 清理日志信息
    LogEntry.objects.filter(node_id__in=node_ids).delete()
    ExecutionHistory.objects.filter(node_id__in=node_ids).delete()
    ExecutionData.objects.filter(node_id__in=node_ids).delete()
    CallbackData.objects.filter(node_id__in=node_ids).delete()


def rollback(pipeline_id: str, node_id: str):
    """
    :param pipeline_id: pipeline id
    :param node_id: 节点 id
    :return: True or False

    回退的思路是，先搜索计算出来当前允许跳过的节点，在计算的过程中网关节点会合并成一个节点
    只允许回退到已经执行过的节点
    """

    runtime = BambooDjangoRuntime()
    pipeline_state = State.objects.filter(node_id=pipeline_id).first()
    if not pipeline_state:
        raise RollBackException("rollback failed: pipeline state not exist, pipeline_id={}".format(pipeline_id))

    if pipeline_state.name != states.RUNNING:
        raise RollBackException(
            "rollback failed: the task of non-running state is not allowed to roll back, pipeline_id={}".format(
                pipeline_id))

    node = Node.objects.filter(node_id=node_id).first()
    if node is None:
        raise RollBackException("rollback failed: node not exist, node={}".format(node_id))

    node_detail = json.loads(node.detail)
    if node_detail["type"] != "ServiceActivity":
        raise RollBackException("rollback failed: only allows rollback to ServiceActivity type nodes")

    target_node_state = State.objects.filter(node_id=node_id).first()

    if target_node_state is None:
        raise RollBackException("rollback failed: node state not exist, node={}".format(node_id))

    if target_node_state.name != states.FINISHED:
        raise RollBackException("rollback failed: only allows rollback to finished node")

    # 不需要遍历整颗树，获取到现在已经执行成功的所有列表
    finished_node_id_list = State.objects.filter(root_id=pipeline_id, name="FINISHED").exclude(
        node_id=pipeline_id).values_list("node_id", flat=True)

    # 获取到除pipeline节点之外第一个被创建的节点
    start_node_state = State.objects.filter(root_id=pipeline_id).exclude(node_id=pipeline_id).order_by(
        "created_time").first()

    # 获取到所有当前已经运行完节点的详情
    node_detail_list = Node.objects.filter(node_id__in=finished_node_id_list)
    # 获取node_id 到 node_detail的映射
    node_map = {n.node_id: json.loads(n.detail) for n in node_detail_list}
    # 计算当前允许跳过的合法的节点
    validate_nodes_list = compute_validate_nodes(start_node_state.node_id, [], node_map)

    if node_id not in validate_nodes_list:
        raise RollBackException("rollback failed: node is not allow to rollback, node={}".format(node_id))

    with transaction.atomic():
        try:
            clean_engine_data(runtime, pipeline_id, target_node_state)
        except Exception as e:
            raise RollBackException("rollback failed: clean engine data error, error={}".format(str(e)))

        try:
            # 将当前住进程的正在运行的节点指向目标ID
            main_process = Process.objects.get(root_pipeline_id=pipeline_id, parent_id=-1)
            main_process.current_node_id = node_id
            main_process.save()

            # 重置该节点的状态信息
            runtime.set_state(
                node_id=node_id,
                to_state=states.READY,
                is_retry=True,
                refresh_version=True,
                clear_started_time=True,
                clear_archived_time=True,
            )
            process_info = runtime.get_process_info(main_process.id)
            runtime.execute(
                process_id=process_info.process_id,
                node_id=node_id,
                root_pipeline_id=process_info.root_pipeline_id,
                parent_pipeline_id=process_info.top_pipeline_id,
            )
        except Exception as e:
            raise RollBackException("rollback failed: rollback to node error, error={}".format(str(e)))
