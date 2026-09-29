# -*- coding: utf-8 -*-

import json
from datetime import timedelta

from django.utils import timezone

from bamboo_engine.eri import ScheduleType

from pipeline.eri.models import CallbackData, Node, Process, Schedule, State

ROOT = "root-1"
POLL = ScheduleType.POLL.value
CALLBACK = ScheduleType.CALLBACK.value
MULTIPLE_CALLBACK = ScheduleType.MULTIPLE_CALLBACK.value


def ago(seconds):
    return timezone.now() - timedelta(seconds=seconds)


def make_process(root=ROOT, node="n1", beat=None, **fields):
    values = {
        "root_pipeline_id": root,
        "current_node_id": node,
        "destination_id": "",
        "priority": 1,
        "queue": "diagnostics",
        "pipeline_stack": "[]",
        "asleep": True,
    }
    values.update(fields)
    process = Process.objects.create(**values)
    if beat is not None:
        # last_heartbeat 是 auto_now_add，只能建完再改
        Process.objects.filter(id=process.id).update(last_heartbeat=beat)
        process.refresh_from_db()
    return process


def make_state(node_id, name="RUNNING", version="v1", root=ROOT, started=None, archived=None):
    return State.objects.create(
        node_id=node_id,
        root_id=root,
        name=name,
        version=version,
        started_time=started,
        archived_time=archived,
    )


def make_schedule(
    process,
    node_id,
    version="v1",
    schedule_type=CALLBACK,
    finished=False,
    expired=False,
    scheduling=False,
    schedule_times=0,
):
    return Schedule.objects.create(
        process_id=process.id,
        node_id=node_id,
        version=version,
        type=schedule_type,
        finished=finished,
        expired=expired,
        scheduling=scheduling,
        schedule_times=schedule_times,
    )


def make_node(node_id, node_type="ServiceActivity", targets=None, **detail):
    values = {
        "type": node_type,
        "targets": {"f-" + node_id: node_id + "-next"} if targets is None else targets,
        "root_pipeline_id": ROOT,
        "parent_pipeline_id": ROOT,
        "can_skip": True,
        "can_retry": True,
    }
    values.update(detail)
    return Node.objects.create(node_id=node_id, detail=json.dumps(values))


def make_callback(node_id, version="v1", data="{}"):
    return CallbackData.objects.create(node_id=node_id, version=version, data=data)


def running_root(root=ROOT):
    return make_state(root, name="RUNNING", version="root-v", root=root)


def s1_shape(node="a", beat=900, archived=600, root=ROOT):
    """调度已把节点置为完成、后继执行消息未被消费的进程。"""
    process = make_process(root=root, node=node, beat=ago(beat))
    make_node(node)
    make_state(node, name="FINISHED", version="v1", root=root, started=ago(beat), archived=ago(archived))
    return process


def poll_shape(node="p", beat=400, times=0, code="demo_poll", root=ROOT):
    process = make_process(root=root, node=node, beat=ago(beat))
    make_node(node, code=code)
    make_state(node, name="RUNNING", version="v1", root=root, started=ago(beat))
    make_schedule(process, node, version="v1", schedule_type=POLL, schedule_times=times)
    return process


def fork_parent(need_ack, node="pg", converge="cg", root=ROOT):
    """睡在并行网关上的父进程。"""
    parent = make_process(root=root, node=node, beat=ago(1200), need_ack=need_ack, ack_num=0)
    make_node(node, node_type="ParallelGateway", targets={"f1": "b1", "f2": "b2"}, converge_gateway_id=converge)
    make_state(node, name="FINISHED", version="v1", root=root, archived=ago(1199))
    return parent


def callback_shape(node="cb", schedule_type=CALLBACK, finished=False, root=ROOT):
    """回调已落库、同版本调度的状态由参数决定。返回 (process, schedule, callback)。"""
    process = make_process(root=root, node=node, beat=ago(600))
    make_state(node, name="RUNNING", version="v1", root=root, started=ago(600))
    schedule = make_schedule(process, node, version="v1", schedule_type=schedule_type, finished=finished)
    callback = make_callback(node, version="v1")
    return process, schedule, callback
