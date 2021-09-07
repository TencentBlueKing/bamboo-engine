# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestParallelExecution(EngineTestCase):
    def test_parallel_execution(self):
        start = EmptyStartEvent()
        pg = ParallelGateway()
        acts = [ServiceActivity(component_code="debug_node") for _ in range(10)]
        additional_act = [ServiceActivity(component_code="debug_node") for _ in range(5)]
        cg = ConvergeGateway()
        end = EmptyEndEvent()

        for i in range(len(additional_act)):
            acts[i].connect(additional_act[i])

        start.extend(pg).connect(*acts).converge(cg).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_nest_parallel_execution(self):
        start = EmptyStartEvent()
        pg_1 = ParallelGateway()
        pg_2 = ParallelGateway()
        acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(10)]
        acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(10)]
        cg_1 = ConvergeGateway()
        cg_2 = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(pg_1).connect(pg_2, *acts_group_1).to(pg_2).connect(*acts_group_2).converge(cg_1).to(
            pg_1
        ).converge(cg_2).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()
