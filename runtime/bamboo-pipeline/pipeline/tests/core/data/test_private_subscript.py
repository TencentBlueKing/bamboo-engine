import unittest

from bamboo_engine.config import Settings
from pipeline.core.data import mako_safety
from pipeline.core.data.expression import ConstantTemplate
from pipeline.utils.mako_utils.checker import check_mako_template_safety
from pipeline.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


class PrivateSubscriptTest(unittest.TestCase):
    def test_private_subscript_is_rejected_on_supported_python_versions(self):
        for key in ("__builtins__", "__class__", "__callback__"):
            with self.subTest(key=key), self.assertRaises(ForbiddenMakoTemplateException):
                check_mako_template_safety(
                    "${data['%s']}" % key,
                    mako_safety.SingleLineNodeVisitor(),
                    mako_safety.SingleLinCodeExtractor(),
                )

    def test_private_subscript_never_invokes_context_callable(self):
        original_mode = Settings.MAKO_TEMPLATE_NAME_WHITELIST_MODE
        try:
            for mode in ("off", "warn", "enforce"):
                with self.subTest(mode=mode):
                    Settings.MAKO_TEMPLATE_NAME_WHITELIST_MODE = mode
                    calls = []
                    payload = "${data['__callback__']()}"
                    context = {"data": {"__callback__": lambda: calls.append("called"), "_module": "normal"}}
                    self.assertEqual(ConstantTemplate(payload).resolve_data(context), payload)
                    self.assertEqual(calls, [])
                    self.assertEqual(ConstantTemplate("${data['_module']}").resolve_data(context), "normal")
        finally:
            Settings.MAKO_TEMPLATE_NAME_WHITELIST_MODE = original_mode
