# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestRerun(EngineTestCase):
    def test_single_node_rerun(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        act_2 = ServiceActivity(component_code="loop_count_node")
        eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
        end = EmptyEndEvent()

        act_2.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

        start.extend(act_1).extend(act_2).extend(eg).connect(act_1, end)

        pipeline_data = Data()
        pipeline_data.inputs["${a_i}"] = NodeOutput(type=Var.SPLICE, source_act=act_2.id, source_key="_loop", value="")
        pipeline_data.inputs["${input_a}"] = Var(type=Var.SPLICE, value='${l.split(",")[a_i]}')
        pipeline_data.inputs["${l}"] = Var(type=Var.PLAIN, value="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t")
        pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="4")

        pipeline = self.create_pipeline_and_run(start, data=pipeline_data)

        self.join_or_fail(pipeline)

        self.assert_finished(pipeline)

        self.assert_loop(act_1, 5)
        self.assert_loop(eg, 5)
        self.assert_loop(act_2, 5)

        self.assert_outputs_equals(act_2, "input_a", "e")
        self.assert_outputs_equals(act_2, "loop", 4)
        self.assert_history(
            act_2,
            [
                {"input_a": "a", "loop": 0},
                {"input_a": "b", "loop": 1},
                {"input_a": "c", "loop": 2},
                {"input_a": "d", "loop": 3},
            ],
        )

        self.test_pass()

    def test_subprocess_rerun(self):
        start_sub = EmptyStartEvent()
        act_1_sub = ServiceActivity(component_code="debug_node")
        end_sub = EmptyEndEvent()

        act_1_sub.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

        start_sub.extend(act_1_sub).extend(end_sub)

        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        act_2 = SubProcess(
            start=start_sub,
            data={
                "inputs": {
                    "${input_a}": {"type": "splice", "value": '${l.split(",")[a_i]}'},
                    "${a_i}": {"type": "plain", "value": "", "is_param": True},
                    "${l}": {"type": "plain", "value": "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t"},
                    "${output_a}": {"type": "splice", "source_act": act_1_sub.id, "source_key": "input_a"},
                },
                "outputs": ["${output_a}"],
            },
            params={"${a_i}": {"type": "splice", "value": u"${s_i}"}},
        )
        eg = ExclusiveGateway(conditions={0: "${s_i} < 4", 1: "${s_i} >= 4"})

        end = EmptyEndEvent()

        start.extend(act_1).extend(act_2).extend(eg).connect(act_2, end)

        pipeline = self.create_pipeline_and_run(
            start,
            data={
                "inputs": {"${s_i}": {"source_act": act_2.id, "source_key": "_loop", "type": "splice", "value": ""}},
                "outputs": [],
            },
        )

        self.join_or_fail(pipeline)

        self.assert_finished(pipeline)

        self.assert_loop(act_1, 1)
        self.assert_loop(act_2, 5)
        self.assert_loop(eg, 5)

        self.assert_outputs_equals(act_2, "${output_a}", "e")
        self.assert_outputs_equals(act_2, "_loop", 4)
        self.assert_history(
            act_2,
            [
                {"${output_a}": "a", "_loop": 0},
                {"${output_a}": "b", "_loop": 1},
                {"${output_a}": "c", "_loop": 2},
                {"${output_a}": "d", "_loop": 3},
            ],
        )

        self.test_pass()

    def test_parallel_gateway_rerun(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        pg = ParallelGateway()
        act_2 = ServiceActivity(component_code="loop_count_node")
        act_3 = ServiceActivity(component_code="loop_count_node")
        act_4 = ServiceActivity(component_code="loop_count_s_node")
        cg = ConvergeGateway()
        eg = ExclusiveGateway(
            conditions={
                0: "${a_i} < ${c} and ${b_i} < ${c} and ${c_i} < ${c} and ${d} < ${c}",
                1: "${a_i} >= ${c} and ${b_i} >= ${c} and ${c_i} >= ${c} and ${d} >= ${c}",
            }
        )
        end = EmptyEndEvent()

        act_2.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_a}")

        act_3.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_b}")

        act_4.component.inputs.input_a = Var(type=Var.SPLICE, value="${input_c}")

        start.extend(act_1).extend(pg).connect(act_2, act_3, act_4).to(pg).converge(cg).extend(eg).connect(act_1, end)

        pipeline = self.create_pipeline_and_run(
            start,
            data={
                "inputs": {
                    "${a_i}": {"source_act": act_2.id, "source_key": "_loop", "type": "splice", "value": ""},
                    "${b_i}": {"source_act": act_3.id, "source_key": "_loop", "type": "splice", "value": ""},
                    "${c_i}": {"source_act": act_4.id, "source_key": "_loop", "type": "splice", "value": ""},
                    "${input_a}": {"type": "splice", "value": '${l.split(",")[a_i]}'},
                    "${input_b}": {"type": "splice", "value": '${l.split(",")[b_i]}'},
                    "${input_c}": {"type": "splice", "value": '${l.split(",")[c_i]}'},
                    "${d}": {"type": "splice", "value": "${c_i}"},
                    "${l}": {"type": "plain", "value": "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t"},
                    "${c}": {"type": "plain", "value": "3"},
                },
                "outputs": [],
            },
        )

        self.join_or_fail(pipeline, waitimes=30)

        self.assert_finished(pipeline)

        self.assert_loop(act_1, 4)
        self.assert_loop(pg, 4)
        self.assert_loop(act_2, 4)
        self.assert_loop(act_3, 4)
        self.assert_loop(act_4, 4)
        self.assert_loop(eg, 4)

        for act in [act_2, act_3, act_4]:
            self.assert_outputs_equals(act, "input_a", "d")
            self.assert_outputs_equals(act, "loop", 3)
            self.assert_history(
                act, [{"input_a": "a", "loop": 0}, {"input_a": "b", "loop": 1}, {"input_a": "c", "loop": 2}]
            )

        self.test_pass()

    def test_rerun_in_branch(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        pg = ParallelGateway()

        # branch 1

        act_2 = ServiceActivity(component_code="loop_count_node")
        eg_1 = ExclusiveGateway(conditions={0: "${l_2} < 2", 1: "${l_2} >= 2"})

        # branch 2

        act_3 = ServiceActivity(component_code="loop_count_node")
        act_4 = ServiceActivity(component_code="loop_count_node")
        eg_2 = ExclusiveGateway(conditions={0: "${l_3} < 2", 1: "${l_3} >= 2"})

        # branch 3

        act_5 = ServiceActivity(component_code="loop_count_node")

        cg = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(act_1).extend(pg).connect(act_2, act_3, act_5)

        act_2.extend(eg_1).connect(act_2, cg)

        act_3.extend(act_4).extend(eg_2).connect(act_3, cg)

        act_5.extend(cg).extend(end)

        pipeline = self.create_pipeline_and_run(
            start,
            data={
                "inputs": {
                    "${l_2}": {"source_act": act_2.id, "source_key": "_loop", "type": "splice", "value": ""},
                    "${l_3}": {"source_act": act_3.id, "source_key": "_loop", "type": "splice", "value": ""},
                },
                "outputs": {},
            },
        )

        self.join_or_fail(pipeline)

        self.assert_finished(pipeline)

        self.assert_loop(act_2, 3)
        self.assert_loop(act_3, 3)
        self.assert_loop(act_4, 3)
        self.assert_loop(eg_1, 3)
        self.assert_loop(eg_2, 3)

        self.test_pass()

    def test_retry_rerun(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="fail_at_second_node")
        eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
        end = EmptyEndEvent()

        act_1.component.inputs.key_1 = Var(type=Var.PLAIN, value="val_1")
        act_1.component.inputs.key_2 = Var(type=Var.PLAIN, value="val_2")

        start.extend(act_1).extend(eg).connect(act_1, end)

        pipeline = self.create_pipeline_and_run(
            start,
            data={
                "inputs": {
                    "${a_i}": {"source_act": act_1.id, "source_key": "_loop", "type": "splice", "value": ""},
                    "${c}": {"type": "plain", "value": "4"},
                },
                "outputs": [],
            },
        )

        self.wait_to(act_1, state=states.FAILED)

        self.retry_activity(act_1)

        self.wait_to(act_1, state=states.FAILED)

        self.retry_activity(act_1, data={"can_go": True})

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_loop(act_1, 5)
        self.assert_loop(eg, 5)

        self.assert_outputs_equals(act_1, "loop", 4)
        self.assert_history(act_1, [{"loop": 0}, {"_loop": 1}, {"_loop": 1}, {"loop": 1}, {"loop": 2}, {"loop": 3}])

        self.test_pass()

    def test_skip_rerun(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="fail_at_second_node")
        eg = ExclusiveGateway(conditions={0: "${a_i} < ${c}", 1: "${a_i} >= ${c}"})
        end = EmptyEndEvent()

        act_1.component.inputs.key_1 = Var(type=Var.PLAIN, value="val_1")
        act_1.component.inputs.key_2 = Var(type=Var.PLAIN, value="val_2")

        start.extend(act_1).extend(eg).connect(act_1, end)

        pipeline = self.create_pipeline_and_run(
            start,
            data={
                "inputs": {
                    "${a_i}": {"source_act": act_1.id, "source_key": "_loop", "type": "splice", "value": ""},
                    "${c}": {"type": "plain", "value": "4"},
                },
                "outputs": [],
            },
        )

        self.wait_to(act_1, state=states.FAILED)

        self.skip_activity(act_1)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.assert_loop(act_1, 5)
        self.assert_loop(eg, 5)

        self.assert_outputs_equals(act_1, "loop", 4)
        self.assert_history(act_1, [{"loop": 0}, {"_loop": 1}, {"_loop": 1}, {"loop": 2}, {"loop": 3}], {2: True})

        self.test_pass()
