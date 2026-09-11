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

from bamboo_engine.template.template import Template
from bamboo_engine.template.render_backend import (
    RenderBackend,
    reset_render_backend,
    set_render_backend,
)


class _StubBackend(RenderBackend):
    def __init__(self):
        self.calls = []

    def render(self, template, context, sandbox_builder):
        self.calls.append((template, context, sandbox_builder))
        return "STUB::" + template


@pytest.fixture(autouse=True)
def _reset_backend():
    reset_render_backend()
    yield
    reset_render_backend()


def test_engine_render_template_routes_through_configured_backend():
    stub = _StubBackend()
    set_render_backend(stub)
    out = Template._render_template("${a}", {"a": 1})
    assert out == "STUB::${a}"
    assert len(stub.calls) == 1
    template_arg, context_arg, sandbox_builder = stub.calls[0]
    assert template_arg == "${a}"
    assert context_arg == {"a": 1}
    # the seam must hand the sandbox *builder* (callable) to the backend, not a pre-built dict,
    # so an isolated backend can rebuild the sandbox locally in a subprocess.
    assert callable(sandbox_builder)
    assert isinstance(sandbox_builder(), dict)


def test_engine_render_template_default_backend_still_renders_inprocess():
    # With no backend override, behavior is unchanged: real in-process render.
    assert Template._render_template("${a + b}", {"a": 2, "b": 3}) == "5"


def test_engine_render_template_rejects_non_string_template():
    with pytest.raises(TypeError):
        Template._render_template(123, {})
