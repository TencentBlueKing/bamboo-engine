# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_rewrite_output():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="output_value_1")
    act_2 = ServiceActivity(component_code="debug_node")
    act_2.component.inputs.context_var = Var(type=Var.SPLICE, value="${rewritable_output}")
    act_2.component.inputs.param_2 = Var(type=Var.PLAIN, value="output_value_2")
    act_3 = ServiceActivity(component_code="debug_node")
    act_3.component.inputs.context_var = Var(type=Var.SPLICE, value="${rewritable_output}")
    end = EmptyEndEvent()

    start.extend(act_1).extend(act_2).extend(act_3).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${rewritable_output}"] = RewritableNodeOutput(
        source_act=[
            {"source_act": act_1.id, "source_key": "param_1"},
            {"source_act": act_2.id, "source_key": "param_2"},
        ],
        type=Var.SPLICE,
        value="",
    )

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(3)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "output_value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "output_value_1", "_result": True},
            },
            act_2.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_2": "output_value_2", "context_var": "output_value_1"},
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_2": "output_value_2",
                    "context_var": "output_value_1",
                    "_result": True,
                },
            },
            act_3.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "context_var": "output_value_2"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "context_var": "output_value_2", "_result": True},
            },
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${rewritable_output}"].type == ContextValueType.PLAIN
    assert context_values["${rewritable_output}"].value == "output_value_2"
