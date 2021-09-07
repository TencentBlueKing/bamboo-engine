# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestOneNodeExecution(EngineTestCase):
    def test_execution(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()
