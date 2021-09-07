# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestCallbackActivity(EngineTestCase):
    def test_callback_node_success(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="callback_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(3)

        self.callback_activity(act_1)

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_multi_callback_node_success(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="multi_callback_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(3)
        for schedule_time in range(10):
            self.callback_activity(act_1, data={"bit": 1, "schedule_time": schedule_time})

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_multi_callback_node_fail_and_callback_again(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="multi_callback_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(3)
        self.callback_activity(act_1, {"bit": 0})
        self.wait_to(act_1, state=states.FAILED)

        self.retry_activity(act_1)
        for schedule_time in range(5):
            self.callback_activity(act_1, data={"bit": 1, "schedule_time": schedule_time})

        self.join_or_fail(pipeline, waitimes=20)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_callback_node_fail_and_callback_again(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="callback_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(3)

        self.callback_activity(act_1, {"bit": 0})

        self.wait_to(act_1, state=states.FAILED)

        self.retry_activity(act_1)

        self.wait(3)

        self.callback_activity(act_1)

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_callback_node_fail_and_skip(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="callback_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait(3)

        self.callback_activity(act_1, {"bit": 0})

        self.wait_to(act_1, state=states.FAILED)

        self.skip_activity(act_1)

        self.join_or_fail(pipeline)

        self.assert_pipeline_finished(pipeline)

        self.test_pass()
