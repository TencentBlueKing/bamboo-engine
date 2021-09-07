# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_retry_with_simple_pipeline():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="fail_ctrl_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    old_state = runtime.get_state(act_1.id)
    assert_all_failed([act_1.id])
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_result": False, "_loop": 1, "_inner_loop": 1},
            }
        }
    )

    engine.retry_node(act_1.id, {"bit": 1})

    sleep(1)

    assert_all_finish([start.id, act_1.id, end.id])
    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"bit": 1, "_loop": 1, "_inner_loop": 1},
                "outputs": {"_result": True, "_loop": 1, "_inner_loop": 1},
            }
        }
    )

    state = runtime.get_state(act_1.id)
    assert state.version != old_state.version
    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 1
    assert histories[0].node_id == act_1.id
    assert histories[0].loop == 1
    assert histories[0].retry == 0
    assert histories[0].skip is False
    assert histories[0].started_time is not None
    assert histories[0].archived_time is not None
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1}
    assert histories[0].outputs == {"_result": False, "_loop": 1, "_inner_loop": 1}
    assert histories[0].version == old_state.version


def test_retry_with_subprocess_has_parallel():
    parallel_count = 5
    start = EmptyStartEvent()
    pg_1 = ParallelGateway()
    pg_2 = ParallelGateway()

    acts_group_1 = [ServiceActivity(component_code="fail_ctrl_node") for _ in range(parallel_count)]
    acts_group_2 = [ServiceActivity(component_code="fail_ctrl_node") for _ in range(parallel_count)]
    cg_1 = ConvergeGateway()
    cg_2 = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(pg_1).connect(pg_2, *acts_group_1).to(pg_2).connect(*acts_group_2).converge(cg_1).to(pg_1).converge(
        cg_2
    ).extend(end)

    parent_start = EmptyStartEvent()
    subproc = SubProcess(start=start)
    parent_end = EmptyEndEvent()

    parent_start.extend(subproc).extend(parent_end)

    pipeline = build_tree(parent_start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    fail_nodes = []
    fail_nodes.extend(acts_group_1)
    fail_nodes.extend(acts_group_2)

    assert_all_failed([a.id for a in fail_nodes])
    assert_all_running([pipeline["id"], subproc.id])
    assert_not_executed([cg_1.id, cg_2.id, end.id, parent_end.id])

    for node in fail_nodes:
        engine.retry_node(node.id, {"bit": 1})

    sleep(1)
    node_id_list = [
        pipeline["id"],
        start.id,
        pg_1.id,
        pg_2.id,
        cg_1.id,
        cg_2.id,
        end.id,
        parent_start.id,
        subproc.id,
        parent_end.id,
    ]
    node_id_list.extend([a.id for a in acts_group_1])
    node_id_list.extend([a.id for a in acts_group_2])

    assert_all_finish(node_id_list)
