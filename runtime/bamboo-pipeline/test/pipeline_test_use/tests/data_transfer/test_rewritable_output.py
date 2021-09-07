# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestRewritableNodeRefOutput(EngineTestCase):
    def test_rewrite_output(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)
        self.assert_outputs_equals(act_2, "context_var", "output_value_1")

        self.assert_outputs_equals(act_3, "context_var", "output_value_2")

        self.test_pass()
