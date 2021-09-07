# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestNodeRefConstant(EngineTestCase):
    def test_ref_constant(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline_data = Data()
        pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(act_1, "param_1", "value_1")

        self.test_pass()
