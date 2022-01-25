# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_ref_output():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="output_value_1")
    act_2 = ServiceActivity(component_code="debug_node")
    act_2.component.inputs.param_2 = Var(type=Var.SPLICE, value="${act_1_output}")
    end = EmptyEndEvent()

    start.extend(act_1).extend(act_2).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${act_1_output}"] = NodeOutput(
        source_act=act_1.id, source_key="param_1", type=Var.SPLICE, value=""
    )

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "output_value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "output_value_1", "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_2": "output_value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_2": "output_value_1", "_result": True},
            },
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${act_1_output}"].type == ContextValueType.PLAIN
    assert context_values["${act_1_output}"].value == "output_value_1"


def test_ref_subprocess_output():
    sub_start = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="from_subprocess")
    sub_end = EmptyEndEvent()

    sub_start.extend(sub_act_1).extend(sub_end)

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${act_1_output}"] = NodeOutput(
        source_act=sub_act_1.id, source_key="param_1", type=Var.PLAIN, value=""
    )
    sub_pipeline_data.outputs.append("${act_1_output}")

    start = EmptyStartEvent()
    params = Params()
    subprocess = SubProcess(start=sub_start, data=sub_pipeline_data, params=params)
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${subprocess_output}")

    end = EmptyEndEvent()

    start.extend(subprocess).extend(act_1).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${subprocess_output}"] = NodeOutput(
        source_act=subprocess.id, source_key="${act_1_output}", type=Var.PLAIN, value=""
    )

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "from_subprocess"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "from_subprocess", "_result": True},
            },
            subprocess.id: {
                "inputs": {},
                "outputs": {"${act_1_output}": "from_subprocess", "_loop": 1, "_inner_loop": 1},
            },
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "from_subprocess"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "from_subprocess", "_result": True},
            },
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${subprocess_output}"].type == ContextValueType.PLAIN
    assert context_values["${subprocess_output}"].value == "from_subprocess"

    context_values = get_context_dict(subprocess.id)
    assert len(context_values) == 1
    assert context_values["${act_1_output}"].type == ContextValueType.PLAIN
    assert context_values["${act_1_output}"].value == "from_subprocess"

    context_outputs = runtime.get_context_outputs(subprocess.id)
    assert context_outputs == {"${act_1_output}"}


def test_ref_nesting_subprocess_output():
    # subprocess 1
    sub_start_1 = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="from_inner_subprocess")
    sub_act_1.component.inputs.param_2 = Var(type=Var.PLAIN, value="from_inner_subprocess_2")
    sub_end_1 = EmptyEndEvent()

    sub_start_1.extend(sub_act_1).extend(sub_end_1)

    sub_pipeline_data_1 = Data()
    sub_pipeline_data_1.inputs["${act_1_output}"] = NodeOutput(
        source_act=sub_act_1.id, source_key="param_1", type=Var.PLAIN, value=""
    )
    sub_pipeline_data_1.inputs["${act_1_output_2}"] = NodeOutput(
        source_act=sub_act_1.id, source_key="param_2", type=Var.PLAIN, value=""
    )
    sub_pipeline_data_1.outputs.append("${act_1_output}")
    sub_pipeline_data_1.outputs.append("${act_1_output_2}")

    # subprocess 2
    sub_start_2 = EmptyStartEvent()
    params_1 = Params()
    subprocess_1 = SubProcess(start=sub_start_1, data=sub_pipeline_data_1, params=params_1)
    sub_end_2 = EmptyEndEvent()

    sub_start_2.extend(subprocess_1).extend(sub_end_2)

    sub_pipeline_data_2 = Data()
    sub_pipeline_data_2.inputs["${subprocess_output}"] = NodeOutput(
        source_act=subprocess_1.id, source_key="${act_1_output}", type=Var.PLAIN, value=""
    )
    sub_pipeline_data_2.inputs["${subprocess_output_2}"] = NodeOutput(
        source_act=subprocess_1.id, source_key="${act_1_output_2}", type=Var.PLAIN, value=""
    )
    sub_pipeline_data_2.outputs.append("${subprocess_output}")
    sub_pipeline_data_2.outputs.append("${subprocess_output_2}")

    # root
    start = EmptyStartEvent()
    params = Params()
    subprocess = SubProcess(start=sub_start_2, data=sub_pipeline_data_2, params=params)
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${subprocess_2_output}")
    act_1.component.inputs.param_2 = Var(type=Var.SPLICE, value="${subprocess_2_output_2}")

    end = EmptyEndEvent()

    start.extend(subprocess).extend(act_1).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${subprocess_2_output}"] = NodeOutput(
        source_act=subprocess.id, source_key="${subprocess_output}", type=Var.PLAIN, value=""
    )
    pipeline_data.inputs["${subprocess_2_output_2}"] = NodeOutput(
        source_act=subprocess.id, source_key="${subprocess_output_2}", type=Var.PLAIN, value=""
    )

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            sub_act_1.id: {
                "inputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "from_inner_subprocess",
                    "param_2": "from_inner_subprocess_2",
                },
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "from_inner_subprocess",
                    "param_2": "from_inner_subprocess_2",
                    "_result": True,
                },
            },
            subprocess_1.id: {
                "inputs": {},
                "outputs": {
                    "${act_1_output}": "from_inner_subprocess",
                    "${act_1_output_2}": "from_inner_subprocess_2",
                    "_loop": 1,
                    "_inner_loop": 1,
                },
            },
            subprocess.id: {
                "inputs": {},
                "outputs": {
                    "${subprocess_output}": "from_inner_subprocess",
                    "${subprocess_output_2}": "from_inner_subprocess_2",
                    "_loop": 1,
                    "_inner_loop": 1,
                },
            },
            act_1.id: {
                "inputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "from_inner_subprocess",
                    "param_2": "from_inner_subprocess_2",
                },
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "from_inner_subprocess",
                    "param_2": "from_inner_subprocess_2",
                    "_result": True,
                },
            },
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 2
    assert context_values["${subprocess_2_output}"].type == ContextValueType.PLAIN
    assert context_values["${subprocess_2_output}"].value == "from_inner_subprocess"
    assert context_values["${subprocess_2_output_2}"].type == ContextValueType.PLAIN
    assert context_values["${subprocess_2_output_2}"].value == "from_inner_subprocess_2"

    context_values = get_context_dict(subprocess.id)
    assert len(context_values) == 2
    assert context_values["${subprocess_output}"].type == ContextValueType.PLAIN
    assert context_values["${subprocess_output}"].value == "from_inner_subprocess"
    assert context_values["${subprocess_output_2}"].type == ContextValueType.PLAIN
    assert context_values["${subprocess_output_2}"].value == "from_inner_subprocess_2"

    context_values = get_context_dict(subprocess_1.id)
    assert len(context_values) == 2
    assert context_values["${act_1_output}"].type == ContextValueType.PLAIN
    assert context_values["${act_1_output}"].value == "from_inner_subprocess"
    assert context_values["${act_1_output_2}"].type == ContextValueType.PLAIN
    assert context_values["${act_1_output_2}"].value == "from_inner_subprocess_2"
