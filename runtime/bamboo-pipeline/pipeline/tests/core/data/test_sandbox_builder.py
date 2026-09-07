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

# NOTE: this module is intentionally Django-free and MUST be importable/usable without configuring
# Django settings, so that an isolated (spawn) render worker can rebuild the legacy sandbox without
# pulling the app + its credentials back into the worker process.

from pipeline.core.data import sandbox_builder


def test_build_sandbox_includes_mock_builtins():
    sb = sandbox_builder.build_sandbox([], {})
    # mock builtins render as their name and are callable proxies to the real builtin
    assert str(sb["int"]) == "int"
    assert sb["int"]("3") == 3
    assert str(sb["len"]) == "len"
    assert sb["len"]([1, 2, 3]) == 3


def test_build_sandbox_applies_shield_words():
    sb = sandbox_builder.build_sandbox(["exec", "compile"], {})
    assert sb["exec"] is None
    assert sb["compile"] is None


def test_build_sandbox_imports_modules():
    sb = sandbox_builder.build_sandbox([], {"datetime": "datetime"})
    assert type(sb["datetime"]).__name__ == "module"


def test_build_sandbox_imports_dotted_alias_as_module_object():
    sb = sandbox_builder.build_sandbox([], {"datetime.datetime": "datetime.datetime"})
    # dotted alias becomes a ModuleObject chain: sb["datetime"].datetime is the class
    assert isinstance(sb["datetime"], sandbox_builder.ModuleObject)
    assert sb["datetime"].datetime.__name__ == "datetime"


def test_build_sandbox_rejects_dangerous_import_modules():
    sb = sandbox_builder.build_sandbox([], {"os": "os", "subprocess": "subprocess", "json": "json"})
    assert "os" not in sb
    assert "subprocess" not in sb
    assert type(sb["json"]).__name__ == "module"


def test_build_sandbox_returns_fresh_dict_each_call():
    a = sandbox_builder.build_sandbox([], {})
    b = sandbox_builder.build_sandbox([], {})
    assert a is not b
    assert a["int"] is not None and b["int"] is not None
