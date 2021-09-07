# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestPauseAndResumeActivity(EngineTestCase):
    def test_pause_activity_in_plain(self):
        start = EmptyStartEvent()
        act_0 = ServiceActivity(component_code="sleep_timer")
        act_0.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
        act_1 = ServiceActivity(component_code="debug_node")
        end = EmptyEndEvent()

        start.extend(act_0).extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.pause_activity(act_1)

        self.wait_to(act_0, state=states.FINISHED)

        self.assert_state(act_1, state=states.SUSPENDED)
        self.assert_state(pipeline, state=states.BLOCKED)
        self.assert_not_execute(end)

        self.resume_activity(act_1)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_pause_activity_in_parallel(self):
        parallel_count = 5
        start = EmptyStartEvent()
        pg_1 = ParallelGateway()
        pg_2 = ParallelGateway()
        sleep_group_1 = []

        for _ in range(parallel_count):
            act = ServiceActivity(component_code="sleep_timer")
            act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
            sleep_group_1.append(act)

        sleep_group_2 = []
        for _ in range(parallel_count):
            act = ServiceActivity(component_code="sleep_timer")
            act.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
            sleep_group_2.append(act)

        acts_group_1 = [ServiceActivity(component_code="debug_node") for _ in range(parallel_count)]
        acts_group_2 = [ServiceActivity(component_code="debug_node") for _ in range(parallel_count)]
        cg_1 = ConvergeGateway()
        cg_2 = ConvergeGateway()
        end = EmptyEndEvent()

        for i in range(parallel_count):
            sleep_group_1[i].connect(acts_group_1[i])
            sleep_group_2[i].connect(acts_group_2[i])

        start.extend(pg_1).connect(pg_2, *sleep_group_1).to(pg_2).connect(*sleep_group_2).converge(cg_1).to(
            pg_1
        ).converge(cg_2).extend(end)

        pause_act = [acts_group_1[0], acts_group_1[1], acts_group_2[0], acts_group_2[1]]
        node_not_execute = [cg_1, cg_2, end]
        node_finished = []
        node_finished.extend(acts_group_1)
        node_finished.extend(acts_group_2)

        for act in pause_act:
            node_finished.remove(act)

        pipeline = self.create_pipeline_and_run(start)

        for act in pause_act:
            self.pause_activity(act)

        self.wait_to(*node_finished, state=states.FINISHED)

        self.assert_state(*pause_act, state=states.SUSPENDED)
        self.assert_state(pipeline, state=states.BLOCKED)
        self.assert_not_execute(*node_not_execute)
        self.assert_finished(*node_finished)

        for act in pause_act:
            self.resume_activity(act)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_pause_activity_in_subprocess(self):
        sub_1_start = EmptyStartEvent()
        sub_1_act_1 = ServiceActivity(component_code="sleep_timer")
        sub_1_act_1.component.inputs.bk_timing = Var(type=Var.PLAIN, value=3)
        sub_1_act_2 = ServiceActivity(component_code="debug_node")
        sub_1_end = EmptyEndEvent()

        sub_1_start.extend(sub_1_act_1).extend(sub_1_act_2).extend(sub_1_end)

        sub_2_start = EmptyStartEvent()
        sub_2_act_1 = ServiceActivity(component_code="debug_node")
        sub_2_end = EmptyEndEvent()

        sub_2_start.extend(sub_2_act_1).extend(sub_2_end)

        sub_3_start = EmptyStartEvent()
        sub_3_pg = ParallelGateway()
        sub_3_subproc_1 = SubProcess(start=sub_1_start)
        sub_3_subproc_2 = SubProcess(start=sub_2_start)
        sub_3_cg = ConvergeGateway()
        sub_3_end = EmptyEndEvent()

        sub_3_start.extend(sub_3_pg).connect(sub_3_subproc_1, sub_3_subproc_2).converge(sub_3_cg).extend(sub_3_end)

        start = EmptyStartEvent()
        subproc = SubProcess(start=sub_3_start)
        end = EmptyEndEvent()

        start.extend(subproc).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.pause_activity(sub_1_act_2)

        self.wait_to(pipeline, subproc, sub_3_subproc_1, state=states.BLOCKED)

        self.assert_state(pipeline, subproc, sub_3_subproc_1, state=states.BLOCKED)
        self.assert_finished(start, sub_3_start, sub_3_pg, sub_3_subproc_2, sub_2_start, sub_2_act_1, sub_2_end)
        self.assert_not_execute(sub_3_cg, sub_3_end, end)

        self.resume_activity(sub_1_act_2)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)
        self.test_pass()
