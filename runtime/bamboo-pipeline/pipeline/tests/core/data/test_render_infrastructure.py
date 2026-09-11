# -*- coding: utf-8 -*-
"""Infrastructure failures must survive legacy variable and context hydration."""

from contextlib import contextmanager
from unittest import mock

from django.test import SimpleTestCase
from pipeline.conf import settings
from pipeline.core.data.base import DataObject
from pipeline.core.data.context import Context
from pipeline.core.data.expression import ConstantTemplate
from pipeline.core.data.hydration import hydrate_data, hydrate_subprocess_context
from pipeline.core.data.var import LazyVariable, PlainVariable, SpliceVariable

from bamboo_engine.exceptions import RenderInfrastructureError
from bamboo_engine.template.render_backend import InProcessRenderBackend, SubprocessPoolRenderBackend


@contextmanager
def failing_render_backend():
    """Exercise real admission/supervision, failing before any worker is started."""
    backend = SubprocessPoolRenderBackend(pool_size=1, timeout=2, os_harden=False, no_network=False)
    try:
        with mock.patch.object(backend, "_spawn_worker", side_effect=OSError("test worker startup failed")):
            with mock.patch("pipeline.core.data.expression.get_render_backend", return_value=backend):
                yield backend
    finally:
        backend.close()


class RenderInfrastructureVariableTestCase(SimpleTestCase):
    def setUp(self):
        self.context = Context({}, scope={"${value}": "ok"})

    def splice(self):
        return SpliceVariable("${rendered}", "prefix-${value}", self.context)

    def test_real_backend_failure_is_not_returned_as_template(self):
        with failing_render_backend(), self.assertRaises(RenderInfrastructureError):
            ConstantTemplate("prefix-${value}").resolve_data({"value": "ok"})

    def test_splice_and_nested_reference_propagate_real_backend_failure(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                variable = self.splice()
                if nested:
                    self.context.set_global_var("${rendered}", variable)
                    variable = SpliceVariable("${nested}", "${rendered}", self.context)
                with failing_render_backend(), self.assertRaises(RenderInfrastructureError):
                    variable.get()
                self.assertIsNone(variable._value)

    def test_specific_exception_configuration_cannot_swallow_infrastructure_failure(self):
        with mock.patch.object(settings, "VARIABLE_SPECIFIC_EXCEPTIONS", (Exception,)):
            with failing_render_backend(), self.assertRaises(RenderInfrastructureError):
                self.splice().get()

    def test_lazy_get_value_propagates_infrastructure_failure(self):
        # Instantiate the base to avoid registering a test variable in the application.
        variable = LazyVariable("${lazy}", "plain", self.context, {})
        error = RenderInfrastructureError("worker")
        for specific in ((), (Exception,)):
            with self.subTest(specific=specific):
                with mock.patch.object(settings, "VARIABLE_SPECIFIC_EXCEPTIONS", specific):
                    with mock.patch.object(variable, "get_value", side_effect=error):
                        with self.assertRaises(RenderInfrastructureError) as caught:
                            variable.get()
                self.assertIs(caught.exception, error)

    def test_lazy_reference_failure_does_not_call_get_value(self):
        variable = LazyVariable("${lazy}", "prefix-${value}", self.context, {})
        with mock.patch.object(variable, "get_value") as get_value:
            with failing_render_backend(), self.assertRaises(RenderInfrastructureError):
                variable.get()
            get_value.assert_not_called()

    def test_context_hydration_and_output_propagate_failure(self):
        for operation in ("hydrate", "output", "subprocess"):
            with self.subTest(operation=operation):
                context = Context({}, output_key=["${rendered}"], scope={"${rendered}": self.splice()})
                pipeline = mock.Mock(context=context, data=DataObject({}))
                with failing_render_backend(), self.assertRaises(RenderInfrastructureError):
                    if operation == "hydrate":
                        hydrate_data(context.variables)
                    elif operation == "output":
                        context.write_output(pipeline)
                    else:
                        hydrate_subprocess_context(mock.Mock(data=pipeline.data, pipeline=pipeline))

    def test_ordinary_lazy_error_keeps_historical_fallback(self):
        variable = LazyVariable("${lazy}", "original", self.context, {})
        with mock.patch.object(variable, "get_value", side_effect=ValueError("user error")):
            self.assertEqual(variable.get(), "original")
            with mock.patch.object(settings, "VARIABLE_SPECIFIC_EXCEPTIONS", (ValueError,)):
                self.assertEqual(variable.get(), "Error: user error")

    def test_shell_and_user_expression_errors_keep_original_text(self):
        with mock.patch("pipeline.core.data.expression.get_render_backend", return_value=InProcessRenderBackend()):
            for template in ("echo ${SHELL_UNDEFINED}", "${1 / 0}", "${value:-fallback}"):
                with self.subTest(template=template):
                    self.assertEqual(SpliceVariable("${shell}", template, self.context).get(), template)

    def test_plain_input_does_not_render_even_when_backend_is_unavailable(self):
        value = "echo ${SHELL_UNDEFINED}"
        with failing_render_backend():
            self.assertEqual(hydrate_data({"shell": PlainVariable("shell", value)}), {"shell": value})
