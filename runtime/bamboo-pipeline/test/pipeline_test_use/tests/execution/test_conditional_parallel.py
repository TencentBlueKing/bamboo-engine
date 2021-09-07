# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestConditionalParallelExecution(EngineTestCase):
    def test_parallel_execution(self):
        start = EmptyStartEvent()
        cpg = ConditionalParallelGateway(
            conditions={0: "True == True", 1: "True == True", 2: "True == True", 3: "True == False", 4: "True == False"}
        )
        acts = [ServiceActivity(component_code="debug_node") for _ in range(5)]
        cg = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(cpg).connect(*acts).converge(cg).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)

        self.assert_finished(start, cpg, acts[0], acts[1], acts[2], cg, end)

        self.assert_not_execute(acts[3], acts[4])

        self.test_pass()

    def test_nest_parallel_execution(self):
        start = EmptyStartEvent()
        cpg_1 = ConditionalParallelGateway(
            conditions={0: "True == True", 1: "True == True", 2: "True == True", 3: "True == False", 4: "True == False"}
        )
        cpg_2 = ConditionalParallelGateway(
            conditions={
                0: "True == True",
                1: "True == False",
                2: "True == False",
                3: "True == False",
                4: "True == False",
            }
        )
        acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(4)]
        acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(5)]
        cg_1 = ConvergeGateway()
        cg_2 = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(cpg_1).connect(cpg_2, *acts_group_1).to(cpg_2).connect(*acts_group_2).converge(cg_1).to(
            cpg_1
        ).converge(cg_2).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)

        self.assert_finished(start, cpg_1, cpg_2, acts_group_1[0], acts_group_1[1], acts_group_2[0], cg_1, cg_2, end)

        self.assert_not_execute(
            acts_group_1[2], acts_group_1[3], acts_group_2[1], acts_group_2[2], acts_group_2[3], acts_group_2[4],
        )

        self.test_pass()
