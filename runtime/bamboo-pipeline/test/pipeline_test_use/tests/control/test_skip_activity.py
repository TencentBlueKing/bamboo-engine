# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestSkipActivity(EngineTestCase):
    def test_skip_with_simple_pipeline(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="fail_ctrl_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait_to(act_1, state=states.FAILED)

        self.skip_activity(act_1)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_skip_with_subprocess_has_parallel(self):
        parallel_count = 5
        start = EmptyStartEvent()
        pg_1 = ParallelGateway()
        pg_2 = ParallelGateway()

        acts_group_1 = [ServiceActivity(component_code="fail_ctrl_node") for _ in range(parallel_count)]
        acts_group_2 = [ServiceActivity(component_code="fail_ctrl_node") for _ in range(parallel_count)]
        cg_1 = ConvergeGateway()
        cg_2 = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(pg_1).connect(pg_2, *acts_group_1).to(pg_2).connect(*acts_group_2).converge(cg_1).to(
            pg_1
        ).converge(cg_2).extend(end)

        parent_start = EmptyStartEvent()
        subproc = SubProcess(start=start)
        parent_end = EmptyEndEvent()

        parent_start.extend(subproc).extend(parent_end)

        pipeline = self.create_pipeline_and_run(parent_start)

        fail_nodes = []
        fail_nodes.extend(acts_group_1)
        fail_nodes.extend(acts_group_2)

        self.wait_to(*fail_nodes, state=states.FAILED)

        self.assert_state(pipeline, subproc, state=states.BLOCKED)
        self.assert_not_execute(cg_1, cg_2, end, parent_end)

        for node in fail_nodes:
            self.skip_activity(node)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()
