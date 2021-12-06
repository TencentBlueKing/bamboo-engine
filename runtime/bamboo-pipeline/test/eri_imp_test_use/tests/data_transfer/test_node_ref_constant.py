# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_ref_constant():
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline_data = Data()
    pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

    pipeline = build_tree(start, data=pipeline_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    assert_all_finish([pipeline["id"]])

    assert_exec_data_equal(
        {
            act_1.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_1"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "param_1": "value_1", "_result": True},
            }
        }
    )

    context_values = get_context_dict(pipeline["id"])
    assert len(context_values) == 1
    assert context_values["${constant_1}"].type == ContextValueType.PLAIN
    assert context_values["${constant_1}"].value == "value_1"
