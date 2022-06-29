# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_single_node_rerun():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_2 = ServiceActivity(component_code="loop_count_node")
    eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
    end = EmptyEndEvent()

    act_2.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

    start.extend(act_1).extend(act_2).extend(eg).connect(act_1, end)

    pipeline_data = Data()
    pipeline_data.inputs["${a_i}"] = NodeOutput(type=Var.SPLICE, source_act=act_2.id, source_key="_loop", value="")
    pipeline_data.inputs["${input_a}"] = Var(type=Var.SPLICE, value='${l.split(",")[a_i]}')
    pipeline_data.inputs["${l}"] = Var(type=Var.PLAIN, value="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="4")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(act_1.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(eg.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(act_2.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 4, "_inner_loop": 4},
                "outputs": {"_loop": 4, "_inner_loop": 4, "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 4, "_inner_loop": 4, "input_a": "e"},
                "outputs": {"_loop": 4, "_inner_loop": 4, "loop": 4, "input_a": "e", "_result": True},
            },
        }
    )

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 3
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "_result": True}
    assert histories[1].loop == 2
    assert histories[2].inputs == {"_loop": 3, "_inner_loop": 3}
    assert histories[2].outputs == {"_loop": 3, "_inner_loop": 3, "_result": True}
    assert histories[2].loop == 3

    histories = runtime.get_histories(act_2.id)
    assert len(histories) == 3
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b"}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "loop": 1, "input_a": "b", "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2, "input_a": "c"}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "loop": 2, "input_a": "c", "_result": True}
    assert histories[1].loop == 2
    assert histories[2].inputs == {"_loop": 3, "_inner_loop": 3, "input_a": "d"}
    assert histories[2].outputs == {"_loop": 3, "_inner_loop": 3, "loop": 3, "input_a": "d", "_result": True}
    assert histories[2].loop == 3


def test_subprocess_rerun():
    start_sub = EmptyStartEvent()
    act_1_sub = ServiceActivity(component_code="debug_node")
    end_sub = EmptyEndEvent()

    act_1_sub.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

    start_sub.extend(act_1_sub).extend(end_sub)

    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_2 = SubProcess(
        start=start_sub,
        data={
            "inputs": {
                "${input_a}": {"type": "splice", "value": '${l.split(",")[a_i]}'},
                "${a_i}": {"type": "plain", "value": "", "is_param": True},
                "${l}": {"type": "plain", "value": "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t"},
                "${output_a}": {"type": "splice", "source_act": act_1_sub.id, "source_key": "input_a"},
            },
            "outputs": ["${output_a}"],
        },
        params={"${a_i}": {"type": "splice", "value": "${s_i}"}},
    )
    eg = ExclusiveGateway(conditions={0: "${s_i} < 4", 1: "${s_i} >= 4"})

    end = EmptyEndEvent()

    start.extend(act_1).extend(act_2).extend(eg).connect(act_2, end)

    pipeline_data = Data()
    pipeline_data.inputs["${s_i}"] = NodeOutput(type=Var.SPLICE, source_act=act_2.id, source_key="_loop", value="")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(start_sub.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(act_1_sub.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(end_sub.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(end_sub.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(act_2.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(eg.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    assert_exec_data_equal(
        {
            act_1_sub.id: {
                "inputs": {"_loop": 4, "_inner_loop": 1, "input_a": "e"},
                "outputs": {"_loop": 4, "_inner_loop": 1, "input_a": "e", "_result": True},
            },
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1},
                "outputs": {"_loop": 1, "_inner_loop": 1, "_result": True},
            },
            act_2.id: {"inputs": {"${a_i}": 4}, "outputs": {"${output_a}": "e", "_loop": 4, "_inner_loop": 4}},
        }
    )

    histories = runtime.get_histories(act_1_sub.id)
    assert len(histories) == 3
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b"}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b", "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 1, "input_a": "c"}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 1, "input_a": "c", "_result": True}
    assert histories[1].loop == 2
    assert histories[2].inputs == {"_loop": 3, "_inner_loop": 1, "input_a": "d"}
    assert histories[2].outputs == {"_loop": 3, "_inner_loop": 1, "input_a": "d", "_result": True}
    assert histories[2].loop == 3

    histories = runtime.get_histories(act_2.id)
    assert len(histories) == 3
    assert histories[0].inputs == {"${a_i}": 1}
    assert histories[0].outputs == {"${output_a}": "b", "_loop": 1, "_inner_loop": 1}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"${a_i}": 2}
    assert histories[1].outputs == {"${output_a}": "c", "_loop": 2, "_inner_loop": 2}
    assert histories[1].loop == 2
    assert histories[2].inputs == {"${a_i}": 3}
    assert histories[2].outputs == {"${output_a}": "d", "_loop": 3, "_inner_loop": 3}
    assert histories[2].loop == 3


def test_parallel_gateway_rerun():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    pg = ParallelGateway()
    act_2 = ServiceActivity(component_code="loop_count_node")
    act_3 = ServiceActivity(component_code="loop_count_node")
    act_4 = ServiceActivity(component_code="loop_count_s_node")
    cg = ConvergeGateway()
    eg = ExclusiveGateway(
        conditions={
            0: "${a_i} < ${c} and ${b_i} < ${c} and ${c_i} < ${c} and ${d} < ${c}",
            1: "${a_i} >= ${c} and ${b_i} >= ${c} and ${c_i} >= ${c} and ${d} >= ${c}",
        }
    )
    end = EmptyEndEvent()

    act_2.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

    act_3.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_b}")

    act_4.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_c}")

    start.extend(act_1).extend(pg).connect(act_2, act_3, act_4).to(pg).converge(cg).extend(eg).connect(act_1, end)

    pipeline = build_tree(
        start,
        data={
            "inputs": {
                "${a_i}": {"source_act": act_2.id, "source_key": "_loop", "type": "splice", "value": ""},
                "${b_i}": {"source_act": act_3.id, "source_key": "_loop", "type": "splice", "value": ""},
                "${c_i}": {"source_act": act_4.id, "source_key": "_loop", "type": "splice", "value": ""},
                "${input_a}": {"type": "splice", "value": '${l.split(",")[a_i]}'},
                "${input_b}": {"type": "splice", "value": '${l.split(",")[b_i]}'},
                "${input_c}": {"type": "splice", "value": '${l.split(",")[c_i]}'},
                "${d}": {"type": "splice", "value": "${c_i}"},
                "${l}": {"type": "plain", "value": "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t"},
                "${c}": {"type": "plain", "value": "3"},
            },
            "outputs": [],
        },
    )
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(act_1.id)
    assert state.name == states.FINISHED
    assert state.loop == 3

    state = runtime.get_state(pg.id)
    assert state.name == states.FINISHED
    assert state.loop == 3

    state = runtime.get_state(act_2.id)
    assert state.name == states.FINISHED
    assert state.loop == 3

    state = runtime.get_state(act_3.id)
    assert state.name == states.FINISHED
    assert state.loop == 3

    state = runtime.get_state(act_4.id)
    assert state.name == states.FINISHED
    assert state.loop == 3

    state = runtime.get_state(eg.id)
    assert state.name == states.FINISHED
    assert state.loop == 3

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 3, "_inner_loop": 3},
                "outputs": {"_loop": 3, "_inner_loop": 3, "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 3, "_inner_loop": 3, "input_a": "d"},
                "outputs": {"_loop": 3, "_inner_loop": 3, "loop": 3, "input_a": "d", "_result": True},
            },
            act_3.id: {
                "inputs": {"_loop": 3, "_inner_loop": 3, "input_a": "d"},
                "outputs": {"_loop": 3, "_inner_loop": 3, "loop": 3, "input_a": "d", "_result": True},
            },
            act_4.id: {
                "inputs": {"_loop": 3, "_inner_loop": 3, "input_a": "d"},
                "outputs": {"count": 2, "_loop": 3, "_inner_loop": 3, "loop": 3, "input_a": "d", "_result": True},
            },
        }
    )

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 2
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "_result": True}
    assert histories[1].loop == 2

    histories = runtime.get_histories(act_2.id)
    assert len(histories) == 2
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b"}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "loop": 1, "input_a": "b", "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2, "input_a": "c"}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "loop": 2, "input_a": "c", "_result": True}
    assert histories[1].loop == 2

    histories = runtime.get_histories(act_3.id)
    assert len(histories) == 2
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b"}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "loop": 1, "input_a": "b", "_result": True}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2, "input_a": "c"}
    assert histories[1].outputs == {"_loop": 2, "_inner_loop": 2, "loop": 2, "input_a": "c", "_result": True}
    assert histories[1].loop == 2

    histories = runtime.get_histories(act_4.id)
    assert len(histories) == 2
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "input_a": "b"}
    assert histories[0].outputs == {
        "count": 2,
        "_loop": 1,
        "_inner_loop": 1,
        "loop": 1,
        "input_a": "b",
        "_result": True,
    }
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 2, "_inner_loop": 2, "input_a": "c"}
    assert histories[1].outputs == {
        "count": 2,
        "_loop": 2,
        "_inner_loop": 2,
        "loop": 2,
        "input_a": "c",
        "_result": True,
    }
    assert histories[1].loop == 2


def test_rerun_in_branch():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    pg = ParallelGateway()

    # branch 1

    act_2 = ServiceActivity(component_code="loop_count_node")
    eg_1 = ExclusiveGateway(conditions={0: "${l_2} < 2", 1: "${l_2} >= 2"})

    # branch 2

    act_3 = ServiceActivity(component_code="loop_count_node")
    act_4 = ServiceActivity(component_code="loop_count_node")
    eg_2 = ExclusiveGateway(conditions={0: "${l_3} < 2", 1: "${l_3} >= 2"})

    # branch 3

    act_5 = ServiceActivity(component_code="loop_count_node")

    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(act_1).extend(pg).connect(act_2, act_3, act_5)

    act_2.extend(eg_1).connect(act_2, cg)

    act_3.extend(act_4).extend(eg_2).connect(act_3, cg)

    act_5.extend(cg).extend(end)

    pipeline = build_tree(
        start,
        data={
            "inputs": {
                "${l_2}": {"source_act": act_2.id, "source_key": "_loop", "type": "splice", "value": ""},
                "${l_3}": {"source_act": act_3.id, "source_key": "_loop", "type": "splice", "value": ""},
            },
            "outputs": [],
        },
    )
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(act_2.id)
    assert state.name == states.FINISHED
    assert state.loop == 2

    state = runtime.get_state(act_3.id)
    assert state.name == states.FINISHED
    assert state.loop == 2

    state = runtime.get_state(act_4.id)
    assert state.name == states.FINISHED
    assert state.loop == 2

    state = runtime.get_state(eg_1.id)
    assert state.name == states.FINISHED
    assert state.loop == 2

    state = runtime.get_state(eg_2.id)
    assert state.name == states.FINISHED
    assert state.loop == 2


def test_retry_rerun():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="fail_at_second_node")
    eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
    end = EmptyEndEvent()

    act_1.component.inputs.key_1 = Var(type=Var.PLAIN, value="val_1")
    act_1.component.inputs.key_2 = Var(type=Var.PLAIN, value="val_2")

    start.extend(act_1).extend(eg).connect(act_1, end)

    pipeline = build_tree(
        start,
        data={
            "inputs": {
                "${a_i}": {"source_act": act_1.id, "source_key": "_loop", "type": "splice", "value": ""},
                "${c}": {"type": "plain", "value": "4"},
            },
            "outputs": [],
        },
    )
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_failed([act_1.id])

    engine.retry_node(act_1.id, {})

    assert_all_failed([act_1.id])

    engine.retry_node(act_1.id, {"can_go": True})

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(act_1.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(eg.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 4, "_inner_loop": 4, "can_go": True},
                "outputs": {"loop": 4, "_loop": 4, "_inner_loop": 4, "can_go": True, "_result": True},
            }
        }
    )

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 5
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "key_1": "val_1", "key_2": "val_2"}
    assert histories[0].outputs == {"_loop": 1, "_inner_loop": 1, "_result": False}
    assert histories[0].retry == 0
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 1, "_inner_loop": 1}
    assert histories[1].outputs == {"_loop": 1, "_inner_loop": 1, "_result": False}
    assert histories[1].retry == 1
    assert histories[1].loop == 1
    assert histories[2].inputs == {"_loop": 1, "_inner_loop": 1, "can_go": True}
    assert histories[2].outputs == {"loop": 1, "_loop": 1, "_inner_loop": 1, "can_go": True, "_result": True}
    assert histories[2].retry == 2
    assert histories[2].loop == 1
    assert histories[3].inputs == {"_loop": 2, "_inner_loop": 2, "can_go": True}
    assert histories[3].outputs == {"loop": 2, "_loop": 2, "_inner_loop": 2, "can_go": True, "_result": True}
    assert histories[3].loop == 2
    assert histories[4].inputs == {"_loop": 3, "_inner_loop": 3, "can_go": True}
    assert histories[4].outputs == {"loop": 3, "_loop": 3, "_inner_loop": 3, "can_go": True, "_result": True}
    assert histories[4].loop == 3


def test_skip_rerun():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="fail_at_second_node")
    eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
    end = EmptyEndEvent()

    act_1.component.inputs.key_1 = Var(type=Var.PLAIN, value="val_1")
    act_1.component.inputs.key_2 = Var(type=Var.PLAIN, value="val_2")

    start.extend(act_1).extend(eg).connect(act_1, end)

    pipeline = build_tree(
        start,
        data={
            "inputs": {
                "${a_i}": {"source_act": act_1.id, "source_key": "_loop", "type": "splice", "value": ""},
                "${c}": {"type": "plain", "value": "4"},
            },
            "outputs": [],
        },
    )
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_failed([act_1.id])

    engine.skip_node(act_1.id)

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(act_1.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    state = runtime.get_state(eg.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 4, "_inner_loop": 4, "key_1": "val_1", "key_2": "val_2"},
                "outputs": {
                    "loop": 4,
                    "_loop": 4,
                    "_inner_loop": 4,
                    "key_1": "val_1",
                    "key_2": "val_2",
                    "_result": True,
                },
            }
        }
    )

    histories = runtime.get_histories(act_1.id)
    assert len(histories) == 4
    assert histories[0].inputs == {"_loop": 1, "_inner_loop": 1, "key_1": "val_1", "key_2": "val_2"}
    assert histories[0].skip is False
    assert histories[0].outputs == {"_result": False, "_inner_loop": 1, "_loop": 1}
    assert histories[0].loop == 1
    assert histories[1].inputs == {"_loop": 1, "_inner_loop": 1, "key_1": "val_1", "key_2": "val_2"}
    assert histories[1].skip is True
    assert histories[1].outputs == {"_result": False, "_inner_loop": 1, "_loop": 1}
    assert histories[1].loop == 1
    assert histories[2].inputs == {"_loop": 2, "_inner_loop": 2, "key_1": "val_1", "key_2": "val_2"}
    assert histories[2].outputs == {
        "loop": 2,
        "_loop": 2,
        "_inner_loop": 2,
        "key_1": "val_1",
        "key_2": "val_2",
        "_result": True,
    }
    assert histories[2].skip is False
    assert histories[2].loop == 2
    assert histories[3].inputs == {"_loop": 3, "_inner_loop": 3, "key_1": "val_1", "key_2": "val_2"}
    assert histories[3].outputs == {
        "loop": 3,
        "_loop": 3,
        "_inner_loop": 3,
        "key_1": "val_1",
        "key_2": "val_2",
        "_result": True,
    }
    assert histories[3].skip is False
    assert histories[3].loop == 3
