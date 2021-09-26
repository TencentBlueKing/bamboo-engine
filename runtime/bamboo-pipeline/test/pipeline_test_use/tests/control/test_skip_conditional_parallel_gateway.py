# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestSkipConditionalParallelGateway(EngineTestCase):
    def test_skip_exclusive_gateway(self):
        start = EmptyStartEvent()
        before_cpg = ServiceActivity(component_code="debug_node")
        cpg = ConditionalParallelGateway(conditions={0: "True == False", 1: "True == False"})
        act_executed_1 = ServiceActivity(component_code="debug_node")
        act_executed_2 = ServiceActivity(component_code="debug_node")
        act_will_not_executed = ServiceActivity(component_code="debug_node")
        converge = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(before_cpg).extend(cpg).connect(act_executed_1, act_will_not_executed).to(act_executed_1).connect(
            act_executed_2
        ).to(cpg).converge(converge).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait_to(cpg, state=states.FAILED)

        flow = pipeline.node(act_executed_1.id).incoming.unique_one()

        self.skip_conditional_parallel_gateway(cpg, [flow.id], converge.id)

        self.join_or_fail(pipeline)

        self.assert_finished(start, before_cpg, cpg, act_executed_1, act_executed_2, converge, end)

        self.assert_not_execute(act_will_not_executed)

        self.test_pass()
