# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_ref_self_node_constant():
    sub_start = EmptyStartEvent()
    sub_act_1 = ServiceActivity(component_code="debug_node")
    sub_act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${sub_constant_1}")
    sub_act_1.component.inputs.param_2 = Var(type=Var.PLAIN, value="sub_var2")
    sub_act_2 = ServiceActivity(component_code="debug_node")
    sub_act_2.component.inputs.param_1 = Var(type=Var.SPLICE, value="${ref_sub_act_1_outputs}")
    sub_end = EmptyEndEvent()

    sub_start.extend(sub_act_1).extend(sub_act_2).extend(sub_end)

    sub_pipeline_data = Data()
    sub_pipeline_data.inputs["${sub_constant_1}"] = DataInput(type=Var.PLAIN, value="value_1")
    sub_pipeline_data.inputs["${sub_act_1_outputs}"] = NodeOutput(
        source_act=sub_act_1.id, source_key="param_2", type=Var.SPLICE, value=""
    )
    sub_pipeline_data.inputs["${ref_sub_act_1_outputs}"] = Var(type=Var.SPLICE, value="${sub_act_1_outputs}")

    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="output_value_1")
    params = Params({"${sub_constant_1}": Var(type=Var.SPLICE, value="${act_1_output}")})
    subprocess = SubProcess(start=sub_start, data=sub_pipeline_data, params=params)
    end = EmptyEndEvent()

    start.extend(act_1).extend(subprocess).extend(end)

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
            sub_act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "output_value_1", "param_2": "sub_var2"},
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "output_value_1",
                    "param_2": "sub_var2",
                    "_result": True,
                },
            },
            sub_act_2.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "sub_var2"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "sub_var2", "_result": True},
            },
            subprocess.id: {
                "inputs": {"${sub_constant_1}": "output_value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1},
            },
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${act_1_output}"].type == ContextValueType.PLAIN
    assert context_values["${act_1_output}"].value == "output_value_1"

    context_values = get_context_dict(subprocess.id)
    assert len(context_values) == 3
    assert context_values["${sub_constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${sub_constant_1}"].value == "output_value_1"
    assert context_values["${sub_act_1_outputs}"].type == ContextValueType.PLAIN
    assert context_values["${sub_act_1_outputs}"].value == "sub_var2"
    assert context_values["${ref_sub_act_1_outputs}"].type == ContextValueType.SPLICE
    assert context_values["${ref_sub_act_1_outputs}"].value == "${sub_act_1_outputs}"
