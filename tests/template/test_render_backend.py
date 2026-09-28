# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bamboo_engine.template.render_backend import (
    InProcessRenderBackend,
    RenderBackend,
    get_render_backend,
    reset_render_backend,
    set_render_backend,
)


@pytest.fixture(autouse=True)
def _reset_backend():
    reset_render_backend()
    yield
    reset_render_backend()


def _empty_sandbox():
    return {}


def test_inprocess_backend_renders_template_with_context():
    result = InProcessRenderBackend().render("${a} and ${b}", {"a": "x", "b": "y"}, _empty_sandbox)
    assert result == "x and y"


def test_inprocess_backend_merges_sandbox_builder_into_namespace():
    def sandbox():
        return {"greet": lambda who: "hi " + who}

    result = InProcessRenderBackend().render("${greet(name)}", {"name": "bob"}, sandbox)
    assert result == "hi bob"


def test_context_overrides_sandbox_on_key_collision():
    def sandbox():
        return {"a": "from_sandbox"}

    result = InProcessRenderBackend().render("${a}", {"a": "from_context"}, sandbox)
    assert result == "from_context"


def test_inprocess_backend_returns_template_inert_on_compile_error():
    tpl = "${"  # unbalanced expression -> compile failure
    assert InProcessRenderBackend().render(tpl, {}, _empty_sandbox) == tpl


def test_inprocess_backend_returns_template_inert_on_render_error():
    tpl = "${undefined_name_xyz}"  # NameError at render time
    assert InProcessRenderBackend().render(tpl, {}, _empty_sandbox) == tpl


def test_inprocess_backend_applies_shield_word_from_sandbox():
    # The real production defense for bare ``${eval(...)}`` is the sandbox shield word
    # (``eval`` bound to None in the namespace), which turns the call into a TypeError
    # and renders inert. This asserts the backend feeds shield words into the namespace.
    def sandbox():
        return {"eval": None}

    tpl = "${eval('1+1')}"
    assert InProcessRenderBackend().render(tpl, {}, sandbox) == tpl


def test_inprocess_backend_invokes_harden_before_render(monkeypatch):
    # Behavior-preservation guarantee: the refactor must still call harden_template_builtins
    # on the compiled template before executing it (defense-in-depth layer stays wired).
    calls = []
    import bamboo_engine.template.render_backend as rb

    def _spy(mako_template):
        calls.append(mako_template)

    monkeypatch.setattr(rb, "harden_template_builtins", _spy)
    result = InProcessRenderBackend().render("${a}", {"a": "ok"}, _empty_sandbox)
    assert result == "ok"
    assert len(calls) == 1


def test_get_render_backend_defaults_to_inprocess():
    backend = get_render_backend()
    assert isinstance(backend, RenderBackend)
    assert isinstance(backend, InProcessRenderBackend)


def test_get_render_backend_is_cached_singleton():
    assert get_render_backend() is get_render_backend()


def test_set_render_backend_overrides_default():
    sentinel = InProcessRenderBackend()
    set_render_backend(sentinel)
    assert get_render_backend() is sentinel


def test_reset_render_backend_rebuilds_default():
    sentinel = InProcessRenderBackend()
    set_render_backend(sentinel)
    reset_render_backend()
    assert get_render_backend() is not sentinel
