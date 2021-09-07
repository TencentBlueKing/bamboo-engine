# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestForcedFailActivity(EngineTestCase):
    def test_forced_fail_schedule_node(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="sleep_timer")
        act_1.component.inputs.bk_timing = Var(type=Var.PLAIN, value=5)
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(1)

        self.forced_fail_activity(act_1)

        self.assert_state(act_1, state=states.FAILED)

        self.skip_activity(act_1)

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_forced_fail_not_schedule_node(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="dummy_exec_node")
        act_1.component.inputs.time = Var(type=Var.PLAIN, value=100)
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(1)

        self.forced_fail_activity(act_1)

        self.assert_state(act_1, state=states.FAILED)

        self.skip_activity(act_1)

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_forced_fail_callback_node(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="callback_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(1)

        self.forced_fail_activity(act_1)

        self.assert_state(act_1, state=states.FAILED)

        self.skip_activity(act_1)

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()
