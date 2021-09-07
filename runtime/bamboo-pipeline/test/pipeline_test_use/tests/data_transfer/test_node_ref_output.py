# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestNodeRefOutput(EngineTestCase):
    def test_ref_output(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_outputs_equals(act_1, "param_1", "output_value_1")
        self.assert_inputs_equals(act_2, "param_2", "output_value_1")

        self.test_pass()

    def test_ref_subprocess_output(self):
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

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(act_1, "param_1", "from_subprocess")

        self.test_pass()

    def test_ref_nesting_subprocess_output(self):
        # subprocess 1
        sub_start_1 = EmptyStartEvent()
        sub_act_1 = ServiceActivity(component_code="debug_node")
        sub_act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="from_inner_subprocess")
        sub_end_1 = EmptyEndEvent()

        sub_start_1.extend(sub_act_1).extend(sub_end_1)

        sub_pipeline_data_1 = Data()
        sub_pipeline_data_1.inputs["${act_1_output}"] = NodeOutput(
            source_act=sub_act_1.id, source_key="param_1", type=Var.PLAIN, value=""
        )
        sub_pipeline_data_1.outputs.append("${act_1_output}")

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
        sub_pipeline_data_2.outputs.append("${subprocess_output}")

        # root
        start = EmptyStartEvent()
        params = Params()
        subprocess = SubProcess(start=sub_start_2, data=sub_pipeline_data_2, params=params)
        act_1 = ServiceActivity(component_code="debug_node")
        act_1.component.inputs.param_1 = Var(type=Var.SPLICE, value="${subprocess_2_output}")

        end = EmptyEndEvent()

        start.extend(subprocess).extend(act_1).extend(end)

        pipeline_data = Data()
        pipeline_data.inputs["${subprocess_2_output}"] = NodeOutput(
            source_act=subprocess.id, source_key="${subprocess_output}", type=Var.PLAIN, value=""
        )

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_inputs_equals(act_1, "param_1", "from_inner_subprocess")

        self.test_pass()
