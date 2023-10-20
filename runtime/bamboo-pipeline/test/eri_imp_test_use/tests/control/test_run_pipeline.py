# -*- coding: utf-8 -*-
import time

import pytest
from pipeline.eri.models import State
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from bamboo_engine.engine import Engine


def test_run_pipeline_with_start_node_id():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, start_node_id=act_1.id)

    time.sleep(3)

    with pytest.raises(State.DoesNotExist):
        # 由于直接跳过了开始节点，此时应该抛异常
        runtime.get_state(start.id)

    state = runtime.get_state(act_1.id)

    assert state.name == "RUNNING"

    engine.callback(act_1.id, state.version, {})

    time.sleep(2)

    state = runtime.get_state(act_1.id)

    assert state.name == "FINISHED"

    pipeline_state = runtime.get_state(pipeline["id"])

    assert pipeline_state.name == "FINISHED"
