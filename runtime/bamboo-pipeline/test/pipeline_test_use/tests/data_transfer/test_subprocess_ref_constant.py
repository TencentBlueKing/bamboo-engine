# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestSubprocessRefConstant(EngineTestCase):
    def test_ref_constant(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(sub_act_1, "param_1", "value_1")

        self.test_pass()

    def test_ref_constant_using_splice_input(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(sub_act_1, "param_1", "value_1")

        self.test_pass()

    def test_ref_constant_using_default_value(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(sub_act_1, "param_1", "default_value")

        self.test_pass()

    def test_nesting_ref_constant(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(sub_act_1, "param_1", "value_3")

        self.test_pass()

    def test_nesting_ref_constant_with_same_key(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(sub_act_1, "param_1", "value_3")

        self.test_pass()
