# -*- coding: utf-8 -*-
import time

from bamboo_engine import Engine

from bamboo_engine.builder import *  # noqa
from pipeline.engine import states
from pipeline.eri.models import Process, State
from pipeline.eri.runtime import BambooDjangoRuntime

from pipeline.contrib.rollback import api


def test_retry_with_simple_pipeline():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="callback_node")
    act_1 = ServiceActivity(component_code="callback_node")

    end = EmptyEndEvent()
    start.extend(act_0).extend(act_1).extend(end)
    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})
    time.sleep(3)

    state = runtime.get_state(act_0.id)
    engine.callback(act_0.id, state.version, {"bit": 1})
    pipeline_id = pipeline["id"]
    time.sleep(3)
    assert State.objects.filter(node_id=act_0.id, name=states.FINISHED).exists()
    api.rollback(pipeline_id=pipeline_id, node_id=act_0.id)
    time.sleep(3)
    process = Process.objects.get(root_pipeline_id=pipeline_id, parent_id=-1)
    # 此时最新进程被指向了最新的node_id
    assert process.current_node_id == act_0.id
    # 此时第一个节点重回RUNNING状态
    assert State.objects.filter(node_id=act_0.id, name=states.RUNNING).exists()
