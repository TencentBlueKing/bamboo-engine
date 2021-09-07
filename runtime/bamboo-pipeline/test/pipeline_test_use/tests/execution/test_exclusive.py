# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestExclusiveExecution(EngineTestCase):
    def test_exclusive_execution(self):
        start = EmptyStartEvent()
        before_eg = ServiceActivity(component_code="debug_node")
        eg = ExclusiveGateway(conditions={0: "True == True", 1: "True == False"})
        act_executed_1 = ServiceActivity(component_code="debug_node")
        act_executed_2 = ServiceActivity(component_code="debug_node")
        act_will_not_executed = ServiceActivity(component_code="debug_node")
        converge = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(before_eg).extend(eg).connect(act_executed_1, act_will_not_executed).to(act_executed_1).connect(
            act_executed_2
        ).to(eg).converge(converge).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)

        self.assert_finished(start, before_eg, eg, act_executed_1, act_executed_2, converge, end)

        self.assert_not_execute(act_will_not_executed)

        self.test_pass()
