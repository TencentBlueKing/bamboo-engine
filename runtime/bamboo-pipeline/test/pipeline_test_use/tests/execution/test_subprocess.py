# -*- coding: utf-8 -*-

from ..base import *  # noqa


class TestSubprocessExecution(EngineTestCase):
    def test_subprocess_execution(self):
        subproc_start = EmptyStartEvent()
        subproc_act = ServiceActivity(component_code="debug_node")
        subproc_end = EmptyEndEvent()

        subproc_start.extend(subproc_act).extend(subproc_end)

        start = EmptyStartEvent()
        subproc = SubProcess(start=subproc_start)
        end = EmptyEndEvent()

        start.extend(subproc).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()

    def test_parallel_subprocess_execution(self):
        start_nodes = []

        for _ in range(5):
            subproc_start = EmptyStartEvent()
            subproc_act = ServiceActivity(component_code="debug_node")
            subproc_end = EmptyEndEvent()

            subproc_start.extend(subproc_act).extend(subproc_end)

            start_nodes.append(subproc_start)

        start = EmptyStartEvent()
        pg = ParallelGateway()
        subprocs = [SubProcess(start=s) for s in start_nodes]

        # additioinal node
        additional_start = EmptyStartEvent()
        additional_act = ServiceActivity(component_code="debug_node")
        additional_end = EmptyEndEvent()

        additional_start.extend(additional_act).extend(additional_end)

        additional_subproc = SubProcess(start=additional_start)
        cg = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(pg).connect(*subprocs).to(subprocs[0]).extend(additional_subproc).to(pg).converge(cg).extend(end)

        pipeline = self.create_pipeline_and_run(start)

        self.join_or_fail(pipeline)
        self.assert_pipeline_finished(pipeline)

        self.test_pass()
