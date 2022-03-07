# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_execution():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)

    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    
    assert_all_finish([start.id, act_1.id, end.id, pipeline["id"]])
    assert_exec_data_equal(
        {
            pipeline["id"]: {"inputs": {}, "outputs": {}},
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
            },
        }
    )
    assert_schedule_finish(act_1.id, times=1)
