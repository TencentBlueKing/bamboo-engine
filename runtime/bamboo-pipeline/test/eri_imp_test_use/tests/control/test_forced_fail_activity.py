# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_forced_fail_schedule_node():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="sleep_timer")
    act_1.component.inputs.bk_timing = Var(type=Var.PLAIN, value=5)
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    engine.forced_fail_activity(act_1.id, "forced fail by test")
    data = runtime.get_execution_data(act_1.id)
    assert data.inputs == {"_loop": 1, "_inner_loop": 1, "bk_timing": 5}
    assert len(data.outputs) == 8
    assert data.outputs["ex_data"] == "forced fail by test"
    assert data.outputs["_forced_failed"] is True
    assert data.outputs["eta"] == "5"
    assert data.outputs["type"] == "countdown"
    assert data.outputs["timing_time"] is not None
    assert data.outputs["_result"] is True
    assert data.outputs["_loop"] == 1
    assert data.outputs["_inner_loop"] == 1

    sleep(5)

    assert_all_failed([act_1.id])
    assert_schedule_not_finish(act_1.id, expired=True)

    engine.skip_node(act_1.id)

    sleep(2)
    assert_all_finish([pipeline["id"], start.id, act_1.id, end.id])

    data = runtime.get_execution_data(act_1.id)
    assert data.inputs == {"_loop": 1, "_inner_loop": 1, "bk_timing": 5}
    assert len(data.outputs) == 8
    assert data.outputs["ex_data"] == "forced fail by test"
    assert data.outputs["_forced_failed"] is True
    assert data.outputs["eta"] == "5"
    assert data.outputs["type"] == "countdown"
    assert data.outputs["timing_time"] is not None
    assert data.outputs["_result"] is True
    assert data.outputs["_loop"] == 1
    assert data.outputs["_inner_loop"] == 1

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 1
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "bk_timing": 5}
    assert len(data.outputs) == 8
    assert histories[0].outputs["ex_data"] == "forced fail by test"
    assert histories[0].outputs["_forced_failed"] is True
    assert histories[0].outputs["eta"] == "5"
    assert histories[0].outputs["type"] == "countdown"
    assert histories[0].outputs["timing_time"] is not None
    assert histories[0].outputs["_result"] is True
    assert data.outputs["_loop"] == 1
    assert data.outputs["_inner_loop"] == 1


def test_forced_fail_not_schedule_node():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="dummy_exec_node")
    act_1.component.inputs.time = Var(type=Var.PLAIN, value=5)
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    engine.forced_fail_activity(act_1.id, "forced fail by test")
    data = runtime.get_execution_data(act_1.id)
    assert data.inputs == {}
    assert data.outputs == {"ex_data": "forced fail by test", "_forced_failed": True}

    sleep(5)

    assert_all_failed([act_1.id])

    engine.skip_node(act_1.id)

    sleep(2)
    assert_all_finish([pipeline["id"], start.id, act_1.id, end.id])

    data = runtime.get_execution_data(act_1.id)
    assert data.inputs == {}
    assert data.outputs == {"ex_data": "forced fail by test", "_forced_failed": True}

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 1
    assert histories[0].inputs == {}
    assert histories[0].outputs == {"ex_data": "forced fail by test", "_forced_failed": True}


def test_forced_fail_callback_node():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    engine.forced_fail_activity(act_1.id, "forced fail by test")
    data = runtime.get_execution_data(act_1.id)
    assert data.inputs == {"_loop": 1, "_inner_loop": 1}
    assert data.outputs == {
        "ex_data": "forced fail by test",
        "_forced_failed": True,
        "_result": True,
        "_inner_loop": 1,
        "_loop": 1,
    }

    sleep(2)

    assert_all_failed([act_1.id])
    assert_schedule_not_finish(act_1.id, times=0)

    engine.skip_node(act_1.id)

    sleep(2)
    assert_all_finish([pipeline["id"], start.id, act_1.id, end.id])

    data = runtime.get_execution_data(act_1.id)
    assert data.inputs == {"_loop": 1, "_inner_loop": 1}
    assert data.outputs == {
        "ex_data": "forced fail by test",
        "_forced_failed": True,
        "_result": True,
        "_loop": 1,
        "_inner_loop": 1,
    }

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 1
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1}
    assert histories[0].outputs == {
        "ex_data": "forced fail by test",
        "_forced_failed": True,
        "_result": True,
        "_loop": 1,
        "_inner_loop": 1,
    }
