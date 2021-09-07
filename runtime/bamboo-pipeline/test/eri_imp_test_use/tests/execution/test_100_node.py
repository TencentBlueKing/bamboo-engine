# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_execution():
    start = EmptyStartEvent()
    acts = [ServiceActivity(component_code="debug_node") for act in range(100)]
    end = EmptyEndEvent()

    tail = start
    for a in acts:
        tail = tail.extend(a)

    acts[-1].extend(end)

    pipeline = build_tree(start)

    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(10)

    node_id_list = [pipeline["id"], start.id, end.id]
    act_id_list = [a.id for a in acts]
    node_id_list.extend(act_id_list)

    node_data_dict = {
        a.id: {"inputs": {"_loop": 1, "_inner_loop": 1}, "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True}}
        for a in acts
    }
    node_data_dict[pipeline["id"]] = {"inputs": {}, "outputs": {}}

    assert_all_finish(node_id_list)
    assert_exec_data_equal(node_data_dict)
    for a in acts:
        assert_schedule_finish(a.id, times=1)
