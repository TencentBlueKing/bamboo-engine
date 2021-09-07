# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestAllVarTypes(EngineTestCase):
    def test_all_var_types(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${constant_1}")
        act_1.component.inputs.param_2 = Var(type=Var.LAZY, custom_type="upper_case", value="abc")
        act_1.component.inputs.param_3 = Var(type=Var.PLAIN, value="normal var")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline_data = Data()
        pipeline_data.inputs["${constant_1}"] = Var(type=Var.PLAIN, value="value_1")

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(act_1, "param_1", "value_1")
        self.assert_inputs_equals(act_1, "param_2", "ABC")
        self.assert_inputs_equals(act_1, "param_3", "normal var")

        self.test_pass()
