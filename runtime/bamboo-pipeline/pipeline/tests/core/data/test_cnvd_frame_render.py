"""Run the report's A-D probes through the real legacy ConstantTemplate."""

import io
from unittest import mock

from django.test import SimpleTestCase

from bamboo_engine.config import Settings
from pipeline.core.data.expression import ConstantTemplate

PAYLOADS = {
    "A": "${(g for g in [1]).gi_frame.f_builtins['ev'+'al'](\"__import__('os').system('echo " "VECTOR_A_EXECUTED')\")}",
    "B": "${(g for g in "
    "[1]).gi_frame.f_globals['__'+'builtins__']['ev'+'al'](\"__import__('os').system('echo "
    "VECTOR_B_EXECUTED')\")}",
    "C": "${(g for g in [1]).gi_frame.f_builtins['__'+'import__']('subprocess').Popen('echo "
    "VECTOR_C_EXECUTED',shell=True)}",
    "D": "${(g for g in [1]).gi_frame.f_builtins['ev'+'al'](\"__import__('os').popen('whoami').read()\")}",
}

CONTROLS = [("${1 + 2}", "3"), ("${sum(g for g in [1, 2, 3])}", "6")]


class ReportFrameRenderTestCase(SimpleTestCase):
    def setUp(self):
        patches = [
            mock.patch.object(Settings, "MAKO_RENDER_BACKEND", "inprocess", create=True),
            mock.patch.object(Settings, "MAKO_SANDBOX_IMPORT_MODULES", {}),
            mock.patch("pipeline.core.data.expression.MAKO_SAFETY_CHECK", True),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_report_vectors_never_reach_command_sinks(self):
        for mode in ("off", "warn", "enforce"):
            for vector, payload in PAYLOADS.items():
                with self.subTest(mode=mode, vector=vector), mock.patch.object(
                    Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode
                ), mock.patch("os.system", return_value=0) as system, mock.patch(
                    "os.popen", return_value=io.StringIO("INERT")
                ) as popen, mock.patch(
                    "subprocess.Popen", return_value="INERT"
                ) as process:
                    self.assertEqual(ConstantTemplate(payload).resolve_data({}), payload)
                    system.assert_not_called()
                    popen.assert_not_called()
                    process.assert_not_called()

    def test_normal_controls(self):
        for mode in ("off", "warn", "enforce"):
            for payload, expected in CONTROLS:
                with self.subTest(mode=mode, payload=payload), mock.patch.object(
                    Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode
                ):
                    self.assertEqual(ConstantTemplate(payload).resolve_data({}), expected)
