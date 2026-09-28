"""Real report vectors use inert command sinks, including on a regressed checkout."""
import ast
import io
import os
import subprocess

import pytest

from bamboo_engine.config import Settings
from bamboo_engine.template import Template, render_backend
from bamboo_engine.utils import mako_safety
from bamboo_engine.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


PAYLOADS = {
    "A": "${(g for g in [1]).gi_frame.f_builtins['ev'+'al'](\"__import__('os').system('echo VECTOR_A_EXECUTED')\")}",
    "B": "${(g for g in [1]).gi_frame.f_globals['__'+'builtins__']['ev'+'al']"
    "(\"__import__('os').system('echo VECTOR_B_EXECUTED')\")}",
    "C": "${(g for g in [1]).gi_frame.f_builtins['__'+'import__']"
    "('subprocess').Popen('echo VECTOR_C_EXECUTED',shell=True)}",
    "D": "${(g for g in [1]).gi_frame.f_builtins['ev'+'al'](\"__import__('os').popen('whoami').read()\")}",
}


@pytest.fixture(autouse=True)
def inprocess_with_inert_sinks(monkeypatch):
    calls = []

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return io.StringIO("INERT_COMMAND_MARKER")

    monkeypatch.setattr(os, "system", record)
    monkeypatch.setattr(os, "popen", record)
    monkeypatch.setattr(subprocess, "Popen", record)
    monkeypatch.setattr(render_backend, "_BACKEND", render_backend.InProcessRenderBackend())
    monkeypatch.setattr(Settings, "MAKO_SANDBOX_IMPORT_MODULES", {})
    yield calls
    assert calls == []


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
@pytest.mark.parametrize("label,payload", list(PAYLOADS.items()))
def test_report_vectors_cannot_reach_command_sinks(monkeypatch, mode, label, payload):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    assert Template(payload).render({}) == payload


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
@pytest.mark.parametrize("key", ["__class__", "__builtins__", "__globals__"])
def test_private_subscript_is_blocked_by_ast_and_real_render(monkeypatch, mode, key):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    expression = "data[{!r}]".format(key)
    node = ast.parse(expression, mode="eval")
    # Python 3.6/3.7 parse a literal key as Index(Str), not Constant.
    assert mako_safety.SingleLineNodeVisitor._get_subscript_key(node.body) == key
    with pytest.raises(ForbiddenMakoTemplateException):
        mako_safety.SingleLineNodeVisitor().visit(node)
    payload = "${" + expression + "}"
    assert Template(payload).render({"data": {key: "MUST_NOT_RENDER"}}) == payload


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
@pytest.mark.parametrize(
    "payload,context,expected",
    [
        ("${1 + 2}", {}, "3"),
        ("${sum(g for g in [1, 2, 3])}", {}, "6"),
        ("${data['name']}", {"data": {"name": "allowed"}}, "allowed"),
    ],
)
def test_normal_expressions_still_render(monkeypatch, mode, payload, context, expected):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    assert Template(payload).render(context) == expected
