# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_ref_constant():
    sub_start = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${sub_constant_1}")
    sub_end = EmptyEndEvent()

    sub_start.extend(sub_act_1).extend(sub_end)

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${sub_constant_1}"] = DataInput(type=Var.PLAIN, value="default_value")

    start = EmptyStartEvent()
    params = Params({"${sub_constant_1}": Var(type=Var.SPLICE, value="${constant_1}")})
    subprocess = SubProcess(start=sub_start, data=sub_pipeline_data, params=params)
    end = EmptyEndEvent()

    start.extend(subprocess).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_1", "_result": True},
            },
            subprocess.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${constant_1}"].value == "value_1"

    context_values = get_context_dict(subprocess.id)
    assert len(context_values) == 1
    assert context_values["${sub_constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${sub_constant_1}"].value == "value_1"


def test_ref_constant_using_splice_input():
    sub_start = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${sub_constant_1}")
    sub_end = EmptyEndEvent()

    sub_start.extend(sub_act_1).extend(sub_end)

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${sub_constant_1}"] = DataInput(type=Var.SPLICE, value="default_value")

    start = EmptyStartEvent()
    params = Params({"${sub_constant_1}": Var(type=Var.SPLICE, value="${constant_1}")})
    subprocess = SubProcess(start=sub_start, data=sub_pipeline_data, params=params)
    end = EmptyEndEvent()

    start.extend(subprocess).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_1", "_result": True},
            },
            subprocess.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${constant_1}"].value == "value_1"

    context_values = get_context_dict(subprocess.id)
    assert len(context_values) == 1
    assert context_values["${sub_constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${sub_constant_1}"].value == "value_1"


def test_ref_constant_using_default_value():
    sub_start = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${sub_constant_1}")
    sub_end = EmptyEndEvent()

    sub_start.extend(sub_act_1).extend(sub_end)

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${sub_constant_1}"] = DataInput(type=Var.PLAIN, value="default_value")

    start = EmptyStartEvent()
    params = Params()
    subprocess = SubProcess(start=sub_start, data=sub_pipeline_data, params=params)
    end = EmptyEndEvent()

    start.extend(subprocess).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "default_value"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "default_value", "_result": True},
            },
            subprocess.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${constant_1}"].value == "value_1"

    context_values = get_context_dict(subprocess.id)
    assert len(context_values) == 1
    assert context_values["${sub_constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${sub_constant_1}"].value == "default_value"


def test_nesting_ref_constant():
    # subprocess 1
    sub_start_1 = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${sub_constant_1}")
    sub_end_1 = EmptyEndEvent()

    sub_start_1.extend(sub_act_1).extend(sub_end_1)

    sub_pipeline_data_1 = Data()
    sub_pipeline_data_1.inputs["${sub_constant_1}"] = DataInput(type=Var.PLAIN, value="default_value_1")

    # subprocess 2
    sub_start_2 = EmptyStartEvent()
    params_1 = Params({"${sub_constant_1}": Var(type=Var.SPLICE, value="${sub_constant_2}")})
    subprocess_1 = SubProcess(start=sub_start_1, data=sub_pipeline_data_1, params=params_1)
    sub_end_2 = EmptyEndEvent()

    sub_start_2.extend(subprocess_1).extend(sub_end_2)

    sub_pipeline_data_2 = Data()
    sub_pipeline_data_2.inputs["${sub_constant_2}"] = DataInput(type=Var.PLAIN, value="default_value_2")

    # root flow
    start = EmptyStartEvent()
    params_2 = Params({"${sub_constant_2}": Var(type=Var.SPLICE, value="${constant}")})
    subprocess_2 = SubProcess(start=sub_start_2, data=sub_pipeline_data_2, params=params_2)
    end = EmptyEndEvent()
    start.extend(subprocess_2).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${constant}"] = Var(type=Var.PLAIN, value="value_3")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_3"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_3", "_result": True},
            },
            subprocess_1.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
            subprocess_2.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${constant}"].type == ContextValueType.PLAIN
    assert context_values["${constant}"].value == "value_3"

    context_values = get_context_dict(subprocess_1.id)
    assert len(context_values) == 1
    assert context_values["${sub_constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${sub_constant_1}"].value == "value_3"

    context_values = get_context_dict(subprocess_2.id)
    assert len(context_values) == 1
    assert context_values["${sub_constant_2}"].type == ContextValueType.PLAIN
    assert context_values["${sub_constant_2}"].value == "value_3"


def test_nesting_ref_constant_with_same_key():
    # subprocess 1
    sub_start_1 = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${same_key}")
    sub_end_1 = EmptyEndEvent()

    sub_start_1.extend(sub_act_1).extend(sub_end_1)

    sub_pipeline_data_1 = Data()
    sub_pipeline_data_1.inputs["${same_key}"] = DataInput(type=Var.PLAIN, value="default_value_1")

    # subprocess 2
    sub_start_2 = EmptyStartEvent()
    params_1 = Params({"${same_key}": Var(type=Var.SPLICE, value="${same_key}")})
    subprocess_1 = SubProcess(start=sub_start_1, data=sub_pipeline_data_1, params=params_1)
    sub_end_2 = EmptyEndEvent()

    sub_start_2.extend(subprocess_1).extend(sub_end_2)

    sub_pipeline_data_2 = Data()
    sub_pipeline_data_2.inputs["${same_key}"] = DataInput(type=Var.PLAIN, value="default_value_2")

    # root flow
    start = EmptyStartEvent()
    params_2 = Params({"${same_key}": Var(type=Var.SPLICE, value="${constant}")})
    subprocess_2 = SubProcess(start=sub_start_2, data=sub_pipeline_data_2, params=params_2)
    end = EmptyEndEvent()
    start.extend(subprocess_2).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${constant}"] = Var(type=Var.PLAIN, value="value_3")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(1)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_3"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_3", "_result": True},
            },
            subprocess_1.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
            subprocess_2.id: {"inputs": {}, "outputs": {"_loop": 1, "_inner_loop": 1}},
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${constant}"].type == ContextValueType.PLAIN
    assert context_values["${constant}"].value == "value_3"

    context_values = get_context_dict(subprocess_1.id)
    assert len(context_values) == 1
    assert context_values["${same_key}"].type == ContextValueType.PLAIN
    assert context_values["${same_key}"].value == "value_3"

    context_values = get_context_dict(subprocess_2.id)
    assert len(context_values) == 1
    assert context_values["${same_key}"].type == ContextValueType.PLAIN
    assert context_values["${same_key}"].value == "value_3"
