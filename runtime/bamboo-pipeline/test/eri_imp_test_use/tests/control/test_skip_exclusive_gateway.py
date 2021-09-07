# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_skip_exclusive_gateway():
    start = EmptyStartEvent()
    before_eg = ServiceActivity(component_code="debug_node")
    eg = ExclusiveGateway(conditions={0: "True == False", 1: "True == False"})
    act_executed_1 = ServiceActivity(component_code="debug_node")
    act_executed_2 = ServiceActivity(component_code="debug_node")
    act_will_not_executed = ServiceActivity(component_code="debug_node")
    converge = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(before_eg).extend(eg).connect(act_executed_1, act_will_not_executed).to(act_executed_1).connect(
        act_executed_2
    ).to(eg).converge(converge).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    assert_all_failed([eg.id])

    engine.skip_exclusive_gateway(eg.id, pipeline["activities"][act_executed_1.id]["incoming"][0])

    sleep(3)

    assert_all_finish(
        [pipeline["id"], start.id, before_eg.id, eg.id, act_executed_1.id, act_executed_2.id, converge.id, end.id]
    )

    assert_not_executed([act_will_not_executed.id])
