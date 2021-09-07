from ..base import *  # noqa

from pipeline_test_use.components.end_events import MyTestEndEvent, MyRaiseEndEvent


class TestExecutableEndEventExecution(EngineTestCase):
    def test_executable_end_event_execution(self):
        start = EmptyStartEvent()
        act = ServiceActivity(component_code="debug_node")
        end = ExecutableEndEvent(type=MyTestEndEvent.__name__)

        start.extend(act).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)

        self.assert_finished(start, act, end)

    def test_executable_end_event_raise(self):
        start = EmptyStartEvent()
        act = ServiceActivity(component_code="debug_node")
        end = ExecutableEndEvent(type=MyRaiseEndEvent.__name__)

        start.extend(act).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait_to(end, state=states.FAILED)

        self.assert_finished(start, act)
        self.assert_state(pipeline, state=states.BLOCKED)
        self.assert_ex_data_is_not_none(end)

    def test_executable_end_event_in_subprocess(self):
        sub_start = EmptyStartEvent()
        act = ServiceActivity(component_code="debug_node")
        sub_end = ExecutableEndEvent(type=MyTestEndEvent.__name__)

        sub_start.extend(act).extend(sub_end)

        start = EmptyStartEvent()
        subproc = SubProcess(start=sub_start)
        end = ExecutableEndEvent(type=MyTestEndEvent.__name__)

        start.extend(subproc).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)

        self.assert_finished(sub_start, act, sub_end, start, subproc, end)

    def test_executable_end_event_raise_in_subproc(self):
        sub_start = EmptyStartEvent()
        act = ServiceActivity(component_code="debug_node")
        sub_end = ExecutableEndEvent(type=MyRaiseEndEvent.__name__)

        sub_start.extend(act).extend(sub_end)

        start = EmptyStartEvent()
        subproc = SubProcess(start=sub_start)
        end = ExecutableEndEvent(type=MyTestEndEvent.__name__)

        start.extend(subproc).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.wait_to(sub_end, state=states.FAILED)

        self.assert_finished(start, act)
        self.assert_not_execute(end)
        self.assert_state(pipeline, subproc, state=states.BLOCKED)
        self.assert_ex_data_is_not_none(sub_end)
