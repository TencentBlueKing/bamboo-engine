import pytest

from bamboo_engine.config import Settings
from bamboo_engine.template.template import Template
from bamboo_engine.utils import mako_safety
from bamboo_engine.utils.mako_utils.checker import check_mako_template_safety
from bamboo_engine.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


@pytest.mark.parametrize("key", ["__builtins__", "__class__", "__callback__"])
def test_private_subscript_is_rejected_on_supported_python_versions(key):
    with pytest.raises(ForbiddenMakoTemplateException):
        check_mako_template_safety(
            "${data['%s']}" % key,
            mako_safety.SingleLineNodeVisitor(),
            mako_safety.SingleLinCodeExtractor(),
        )


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
def test_private_subscript_never_invokes_context_callable(monkeypatch, mode):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    calls = []
    payload = "${data['__callback__']()}"
    context = {"data": {"__callback__": lambda: calls.append("called"), "_module": "normal"}}
    assert Template(payload).render(context) == payload
    assert calls == []
    assert Template("${data['_module']}").render(context) == "normal"
