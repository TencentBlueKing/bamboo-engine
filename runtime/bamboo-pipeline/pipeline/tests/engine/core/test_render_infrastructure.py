# -*- coding: utf-8 -*-
"""Run real legacy handlers and persist FAILED through the existing runtime boundary."""

from functools import partial
from unittest import mock

from django.test import TestCase
from pipeline.conf import settings
from pipeline.core.data.base import DataObject
from pipeline.core.data.context import Context
from pipeline.core.data.expression import ConstantTemplate
from pipeline.core.data.var import SpliceVariable
from pipeline.core.flow import (
    Condition,
    ConditionalParallelGateway,
    EmptyEndEvent,
    EmptyStartEvent,
    ExclusiveGateway,
    SequenceFlow,
    Service,
    ServiceActivity,
    SubProcess,
)
from pipeline.engine import states
from pipeline.engine.core import runtime, schedule
from pipeline.engine.models import Data, PipelineProcess, ScheduleService, Status
from pipeline.tests.core.data.test_render_infrastructure import failing_render_backend
from pipeline.tests.mock import MockPipelineProcess, MockScheduleService, PipelineObject

from bamboo_engine.exceptions import RenderInfrastructureError


class RecordingService(Service):
    def __init__(self, render_at=None):
        super(RecordingService, self).__init__()
        self.render_at = render_at
        self.calls = []

    def execute_pre_process(self, data, parent_data):
        self.calls.append("pre_process")
        if self.render_at == "pre_process":
            ConstantTemplate("prefix-${value}").resolve_data({"value": "ok"})
        return True

    def execute(self, data, parent_data):
        self.calls.append("execute")
        if self.render_at == "execute":
            ConstantTemplate("prefix-${value}").resolve_data({"value": "ok"})
        return True

    def schedule(self, data, parent_data, callback_data=None):
        self.calls.append("schedule")
        ConstantTemplate("prefix-${value}").resolve_data({"value": "ok"})
        return True


class RenderInfrastructureRuntimeTestCase(TestCase):
    def setUp(self):
        self.context = Context({}, scope={"${value}": "ok"})
        # Persistence of Status stays real; process scheduling and external data storage are isolated.
        self.patches = [
            mock.patch("pipeline.engine.models.FunctionSwitch.objects.is_frozen", return_value=False),
            mock.patch("pipeline.engine.models.NodeRelationship.objects.build_relationship"),
            mock.patch("pipeline.django_signal_valve.valve.send"),
            mock.patch("pipeline.engine.core.context.set_node_id"),
            mock.patch.object(Data.objects, "write_node_data"),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def splice(self):
        return SpliceVariable("${rendered}", "prefix-${value}", self.context)

    def process_for(self, node, context=None):
        pipeline = PipelineObject(context=context or self.context, data=DataObject({}), node=node)
        process = MockPipelineProcess(
            top_pipeline=pipeline, root_pipeline=pipeline, current_node_id=node.id, destination_id="destination"
        )
        process.root_sleep_check.return_value = (False, states.RUNNING)
        process.exit_gracefully = partial(PipelineProcess.exit_gracefully, process)
        # Stop a successful baseline run at a destination without dispatching another node.
        destination = EmptyEndEvent("destination", data=DataObject({}))
        pipeline.nodes[destination.id] = destination
        node.outgoing.add_flow(SequenceFlow("to_destination", node, destination, is_default=True))
        return process

    def assert_failed(self, node, process):
        status = Status.objects.get(id=node.id)
        self.assertEqual(status.state, states.FAILED)
        self.assertFalse(status.error_ignorable)
        process.sleep.assert_called_once_with(adjust_status=True)
        self.assertEqual(process.current_node_id, node.id)
        process.destroy_and_wake_up_parent.assert_not_called()
        written = Data.objects.write_node_data.call_args
        ex_data = written[1].get("ex_data") if len(written[0]) == 1 else written[0][1]
        self.assertIn("isolated render failed (", ex_data)

    def test_input_failure_fails_node_before_any_business_code_even_if_ignorable(self):
        for ignorable in (False, True):
            with self.subTest(ignorable=ignorable):
                service = RecordingService()
                node = ServiceActivity(
                    "service-{}".format(ignorable),
                    service,
                    data=DataObject({"input": self.splice()}),
                    error_ignorable=ignorable,
                )
                process = self.process_for(node)
                with failing_render_backend():
                    runtime.run_loop(process)
                self.assertEqual(service.calls, [])
                self.assert_failed(node, process)

    def test_pre_process_failure_cannot_be_ignored_or_execute_business_service(self):
        service = RecordingService(render_at="pre_process")
        node = ServiceActivity("pre-process", service, data=DataObject({}), error_ignorable=True, timeout=5)
        process = self.process_for(node)
        with mock.patch("pipeline.engine.signals.service_activity_timeout_monitor_start.send"):
            with mock.patch("pipeline.engine.signals.service_activity_timeout_monitor_end.send") as monitor_end:
                with failing_render_backend():
                    runtime.run_loop(process)
        self.assertEqual(service.calls, ["pre_process"])
        self.assert_failed(node, process)
        monitor_end.assert_called_once()

    def test_plugin_specific_exceptions_cannot_convert_infrastructure_failure_to_success(self):
        service = RecordingService(render_at="execute")
        node = ServiceActivity("plugin-specific", service, data=DataObject({}), error_ignorable=True)
        process = self.process_for(node)
        with mock.patch.object(settings, "PLUGIN_SPECIFIC_EXCEPTIONS", (Exception,)):
            with failing_render_backend():
                runtime.run_loop(process)
        self.assert_failed(node, process)

    def test_gateway_context_failure_fails_before_routing_or_forking(self):
        for gateway_cls in (ExclusiveGateway, ConditionalParallelGateway):
            with self.subTest(gateway=gateway_cls.__name__):
                kwargs = {"converge_gateway_id": "converge"} if gateway_cls is ConditionalParallelGateway else {}
                node = gateway_cls(gateway_cls.__name__, data=DataObject({}), **kwargs)
                context = Context({}, scope={"${rendered}": self.splice()})
                process = self.process_for(node, context)
                with mock.patch.object(PipelineProcess.objects, "fork_child") as fork:
                    with failing_render_backend():
                        runtime.run_loop(process)
                    fork.assert_not_called()
                self.assert_failed(node, process)

    def test_gateway_condition_preserves_infrastructure_exception_identity(self):
        error = RenderInfrastructureError("worker")
        target = EmptyEndEvent("target")
        for gateway_cls in (ExclusiveGateway, ConditionalParallelGateway):
            kwargs = {"converge_gateway_id": "converge"} if gateway_cls is ConditionalParallelGateway else {}
            node = gateway_cls("gateway", **kwargs)
            node.add_condition(Condition("${value} == 'ok'", SequenceFlow("branch", node, target)))
            evaluate = node.next if gateway_cls is ExclusiveGateway else node.targets_meet_condition
            with mock.patch("pipeline.core.data.expression.get_render_backend") as backend:
                backend.return_value.render.side_effect = error
                with self.assertRaises(Exception) as caught:
                    evaluate({"${value}": "ok"})
            self.assertIs(caught.exception, error)

    def test_scheduling_infrastructure_failure_is_failed_even_if_ignorable(self):
        for specific in ((), (Exception,)):
            with self.subTest(specific=specific):
                scheduled = MockScheduleService()
                service = RecordingService()
                node = ServiceActivity(scheduled.activity_id, service, data=DataObject({}), error_ignorable=True)
                scheduled.service_act = node
                process = self.process_for(node)
                Status.objects.create(id=node.id, state=states.RUNNING, version=scheduled.version)
                with mock.patch.object(ScheduleService.objects, "get", return_value=scheduled), mock.patch.object(
                    ScheduleService.objects, "filter"
                ) as schedules, mock.patch.object(
                    PipelineProcess.objects, "get", return_value=process
                ), mock.patch.object(
                    PipelineProcess.objects, "select_for_update"
                ) as locked, mock.patch(
                    "pipeline.engine.core.schedule.get_schedule_parent_data", return_value=DataObject({})
                ), mock.patch(
                    "pipeline.engine.core.schedule.set_schedule_data"
                ), mock.patch(
                    "pipeline.engine.signals.service_schedule_fail.send"
                ), mock.patch.object(
                    settings, "PLUGIN_SPECIFIC_EXCEPTIONS", specific
                ):
                    schedules.return_value.update.return_value = 1
                    locked.return_value.get.return_value = process
                    with failing_render_backend():
                        schedule.schedule(process.id, scheduled.id)
                self.assertEqual(Status.objects.get(id=node.id).state, states.FAILED)
                self.assertFalse(Status.objects.get(id=node.id).error_ignorable)
                scheduled.finish.assert_not_called()
                scheduled.set_next_schedule.assert_not_called()

    def test_subprocess_input_failure_does_not_enter_child(self):
        child = PipelineObject(context=Context({}), data=DataObject({"input": self.splice()}))
        node = SubProcess("subprocess", child)
        process = self.process_for(node)
        with failing_render_backend():
            runtime.run_loop(process)
        self.assert_failed(node, process)
        process.push_pipeline.assert_not_called()
        process.take_snapshot.assert_not_called()
        self.assertEqual(child.context.variables, {})

    def test_start_pre_render_failure_stops_pipeline(self):
        node = EmptyStartEvent("start", data=DataObject({"pre_render_keys": ["${rendered}"]}))
        context = Context({}, scope={"${rendered}": self.splice()})
        process = self.process_for(node, context)
        with failing_render_backend():
            runtime.run_loop(process)
        self.assert_failed(node, process)

    def test_output_failure_keeps_root_and_subprocess_stack_for_retry(self):
        for in_subprocess in (False, True):
            with self.subTest(in_subprocess=in_subprocess):
                node = EmptyEndEvent("end-{}".format(in_subprocess), data=DataObject({}))
                context = Context({}, output_key=["${rendered}"], scope={"${rendered}": self.splice()})
                process = self.process_for(node, context)
                if in_subprocess:
                    process.pipeline_stack.insert(0, PipelineObject(context=Context({}), data=DataObject({})))
                stack = list(process.pipeline_stack)
                Status.objects.create(id=process.top_pipeline.id, state=states.RUNNING, version="test")
                with failing_render_backend():
                    runtime.run_loop(process)
                self.assertEqual(process.pipeline_stack, stack)
                self.assert_failed(node, process)
                process.destroy.assert_not_called()
