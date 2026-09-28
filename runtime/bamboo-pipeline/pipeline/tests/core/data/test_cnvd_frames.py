"""Inert report probes and old-Python AST coverage for ConstantTemplate."""
import ast
import io
from unittest import mock

from django.test import SimpleTestCase, override_settings

from bamboo_engine.config import Settings
from bamboo_engine.template import render_backend
from pipeline.core.data import expression, mako_safety
from pipeline.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


PAYLOADS = {
    "A": "${(g for g in [1]).gi_frame.f_builtins['ev'+'al'](\"__import__('os').system('echo VECTOR_A_EXECUTED')\")}",
    "B": "${(g for g in [1]).gi_frame.f_globals['__'+'builtins__']['ev'+'al']"
    "(\"__import__('os').system('echo VECTOR_B_EXECUTED')\")}",
    "C": "${(g for g in [1]).gi_frame.f_builtins['__'+'import__']"
    "('subprocess').Popen('echo VECTOR_C_EXECUTED',shell=True)}",
    "D": "${(g for g in [1]).gi_frame.f_builtins['ev'+'al'](\"__import__('os').popen('whoami').read()\")}",
}


@override_settings(MAKO_SAFETY_CHECK=True)
class ConstantTemplateFrameSafetyTests(SimpleTestCase):
    def setUp(self):
        self.calls = []
        patches = [
            mock.patch("os.system", side_effect=self.record),
            mock.patch("os.popen", side_effect=self.record),
            mock.patch("subprocess.Popen", side_effect=self.record),
            mock.patch.object(render_backend, "_BACKEND", render_backend.InProcessRenderBackend()),
            mock.patch.object(expression, "MAKO_SAFETY_CHECK", True),
            mock.patch.object(Settings, "MAKO_SANDBOX_IMPORT_MODULES", {}),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def record(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return io.StringIO("INERT_COMMAND_MARKER")

    def tearDown(self):
        self.assertEqual(self.calls, [])

    def test_report_vectors_cannot_reach_command_sinks(self):
        for mode in ("off", "warn", "enforce"):
            with mock.patch.object(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode):
                for label, payload in PAYLOADS.items():
                    with self.subTest(mode=mode, vector=label):
                        self.assertEqual(expression.ConstantTemplate(payload).resolve_data({}), payload)

    def test_private_subscript_is_blocked_by_ast_and_real_render(self):
        for mode in ("off", "warn", "enforce"):
            with mock.patch.object(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode):
                for key in ("__class__", "__builtins__", "__globals__"):
                    with self.subTest(mode=mode, key=key):
                        code = "data[{!r}]".format(key)
                        node = ast.parse(code, mode="eval")
                        self.assertEqual(mako_safety.SingleLineNodeVisitor._get_subscript_key(node.body), key)
                        with self.assertRaises(ForbiddenMakoTemplateException):
                            mako_safety.SingleLineNodeVisitor().visit(node)
                        payload = "${" + code + "}"
                        self.assertEqual(
                            expression.ConstantTemplate(payload).resolve_data({"data": {key: "MUST_NOT_RENDER"}}),
                            payload,
                        )

    def test_normal_expressions_still_render(self):
        cases = [
            ("${1 + 2}", {}, "3"),
            ("${sum(g for g in [1, 2, 3])}", {}, "6"),
            ("${data['name']}", {"data": {"name": "allowed"}}, "allowed"),
        ]
        for mode in ("off", "warn", "enforce"):
            with mock.patch.object(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode):
                for payload, context, expected in cases:
                    with self.subTest(mode=mode, payload=payload):
                        self.assertEqual(expression.ConstantTemplate(payload).resolve_data(context), expected)
