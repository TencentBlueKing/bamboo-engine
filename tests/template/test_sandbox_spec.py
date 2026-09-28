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

import pickle

from bamboo_engine.template import sandbox
from bamboo_engine.template.render_backend import SandboxProvider, SandboxSpec


def test_engine_build_sandbox_applies_shield_and_imports_without_mock_builtins():
    sb = sandbox.build_sandbox(["exec", "compile"], {"datetime": "datetime"})
    assert sb["exec"] is None
    assert sb["compile"] is None
    assert type(sb["datetime"]).__name__ == "module"
    # engine flavor has no legacy mock builtins
    assert "int" not in sb


def test_engine_spec_build_matches_engine_build_sandbox():
    spec = SandboxSpec("engine", ["exec"], {"datetime": "datetime"})
    d = spec.build()
    assert d["exec"] is None
    assert type(d["datetime"]).__name__ == "module"
    assert "int" not in d


def test_sandbox_spec_is_picklable_and_roundtrips():
    spec = SandboxSpec("legacy", ["exec", "compile"], {"datetime": "datetime"})
    restored = pickle.loads(pickle.dumps(spec))
    assert restored.flavor == "legacy"
    assert restored.shield_words == ["exec", "compile"]
    assert restored.import_modules == {"datetime": "datetime"}


def test_sandbox_provider_is_callable_build_and_exposes_spec():
    marker = {"a": 1}
    spec = SandboxSpec("engine", [], {})
    provider = SandboxProvider(lambda: marker, spec)
    # callable -> in-process build path (backward-compatible with plain builder callables)
    assert provider() is marker
    assert provider.build() is marker
    # spec -> serializable rebuild path for isolated workers
    assert provider.spec() is spec


def test_unknown_flavor_raises():
    import pytest

    with pytest.raises(ValueError):
        SandboxSpec("bogus", [], {}).build()
