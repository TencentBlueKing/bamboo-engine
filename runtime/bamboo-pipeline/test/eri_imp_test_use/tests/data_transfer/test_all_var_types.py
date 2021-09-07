# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_all_var_types():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    act_1.component.inputs.param_2 = Var(type=Var.LAZY, custom_type="upper_case", value="abc")
    act_1.component.inputs.param_3 = Var(type=Var.PLAIN, value="normal var")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

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
            act_1.id: {
                "inputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "value_1",
                    "param_2": "ABC",
                    "param_3": "normal var",
                },
                "outputs": {
                    "_loop": 1,
                    "_inner_loop": 1,
                    "param_1": "value_1",
                    "param_2": "ABC",
                    "param_3": "normal var",
                    "_result": True,
                },
            }
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 2
    assert context_values["${constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${constant_1}"].value == "value_1"
    assert context_values["${param_2_%s}" % act_1.id].type == ContextValueType.COMPUTE
    assert context_values["${param_2_%s}" % act_1.id].value == "abc"
    assert context_values["${param_2_%s}" % act_1.id].code == "upper_case"
