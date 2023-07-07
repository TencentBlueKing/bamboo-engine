# -*- coding: utf-8 -*-
import time

from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine import Engine, states
from bamboo_engine.builder import *  # noqa


def test_rollback_node_success():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="rollback_node")
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()
    start.extend(act_0).extend(act_1).extend(end)
    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    time.sleep(3)

    rollback_data = {"bit": 1}

    state = runtime.get_state(act_0.id)
    engine.rollback(node_id=act_0.id, version=state.version, rollback_data=rollback_data)
    time.sleep(3)

    # 此时节点会变成回滚成功状态
    state = runtime.get_state(act_0.id)
    assert state.name == states.ROLLBACK_SUCCESS


def test_rollback_node_failed_and_retry():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="rollback_node")
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()
    start.extend(act_0).extend(act_1).extend(end)
    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    time.sleep(3)

    rollback_data = {"bit": 0}

    state = runtime.get_state(act_0.id)
    engine.rollback(node_id=act_0.id, version=state.version, rollback_data=rollback_data)
    time.sleep(3)

    # 此时节点会变成回滚成功状态
    state = runtime.get_state(act_0.id)
    assert state.name == states.ROLLBACK_FAILED

    rollback_data = {"bit": 1}
    engine.rollback(node_id=act_0.id, version=state.version, rollback_data=rollback_data)
    time.sleep(3)
    state = runtime.get_state(act_0.id)
    assert state.name == states.ROLLBACK_SUCCESS


def test_rollback_node_validate():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="rollback_node")
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()
    start.extend(act_0).extend(act_1).extend(end)
    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    time.sleep(3)

    rollback_data = {"bit": 0}

    state = runtime.get_state(act_1.id)
    try:
        engine.rollback(node_id=act_1.id, version=state.version, rollback_data=rollback_data)
    except Exception as e:
        assert str(e) == "rollback only support finished and rollback_failed state"
