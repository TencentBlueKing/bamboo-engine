"""Render report vectors A-D with inert sinks, including off/warn modes."""

import io
from unittest import mock

import pytest

from bamboo_engine.config import Settings
from bamboo_engine.template.template import Template

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


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
@pytest.mark.parametrize("vector", sorted(PAYLOADS))
def test_report_frame_vectors_never_reach_command_sinks(monkeypatch, mode, vector):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    monkeypatch.setattr(Settings, "MAKO_SANDBOX_IMPORT_MODULES", {})
    monkeypatch.setattr(Settings, "MAKO_RENDER_BACKEND", "inprocess", raising=False)
    payload = PAYLOADS[vector]
    with mock.patch("os.system", return_value=0) as system, mock.patch(
        "os.popen", return_value=io.StringIO("INERT")
    ) as popen, mock.patch("subprocess.Popen", return_value="INERT") as process:
        assert Template(payload).render({}) == payload
        system.assert_not_called()
        popen.assert_not_called()
        process.assert_not_called()


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
@pytest.mark.parametrize("payload,expected", CONTROLS)
def test_report_normal_controls(monkeypatch, mode, payload, expected):
    monkeypatch.setattr(Settings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", mode)
    monkeypatch.setattr(Settings, "MAKO_RENDER_BACKEND", "inprocess", raising=False)
    assert Template(payload).render({}) == expected
