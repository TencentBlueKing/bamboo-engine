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

import datetime

import pytest
from mako.template import Template as MakoTemplate

from bamboo_engine.config import Settings
from bamboo_engine.template import Template
from bamboo_engine.utils import mako_safety
from bamboo_engine.utils.mako_utils.checker import check_mako_template_safety
from bamboo_engine.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


def test_get_reference():
    t = Template(["${a}", ["${a}", "${a+int(b)}"]])
    assert t.get_reference() == {"${a}", "${b}", "${int}"}

    t = Template(['${a["c"]}', ['${"%s" % a}', "${a+int(b)}"]])
    assert t.get_reference() == {"${a}", "${b}", "${int}"}

    t = Template("a-${1 if t else 2}-${a}")
    assert t.render({"t": False, "a": "c"}) == "a-2-c"
    t = Template("${'a-%s-c' % 1 if t else 2}")
    assert t.render({"t": True}) == "a-1-c"


def test_get_templates():
    t = Template(["${a}", ["${a}", "${a+int(b)}"]])
    assert set(t.get_templates()) == {"${a+int(b)}", "${a}"}


def test_render():
    list_template = Template(["${a}", ["${a}", "${a+int(b)}"]])
    assert list_template.render({"a": 2, "b": "3"}), [2, [2, "5"]]

    tuple_template = Template(("${a}", ("${a}", "${a+int(b)}")))
    assert tuple_template.render({"a": 2, "b": "3"}), (2, (2, "5"))

    dict_template = Template({"aaaa": {"a": "${a}", "b": "${a+int(b)}"}})
    assert dict_template.render({"a": 2, "b": "3"}), {"aaaa": {"a": 2, "b": "5"}}

    simple_template = Template("${a}")
    assert simple_template.render({"a": "1"}) == "1"

    calculate_template = Template("${a+int(b)}")
    assert calculate_template.render({"a": 2, "b": "3"}) == "5"

    split_template = Template("${a[0]}")
    assert split_template.render({"a": [1, 2]}) == "1"

    dict_item_template = Template('${a["b"]}')
    assert dict_item_template.render({"a": {"b": 1}}) == "1"

    not_exists_template = Template("${a}")
    assert not_exists_template.render({}) == "${a}"

    syntax_error_template = Template("${a.b}")
    assert syntax_error_template.render({}) == "${a.b}"

    syntax_error_template = Template("${a:b}")
    assert syntax_error_template.render({}) == "${a:b}"


def test_render__with_sandbox():

    r1 = Template("""${exec(print(''))}""").render({})
    assert r1 == """${exec(print(''))}"""

    r2 = Template("""${datetime.datetime.now().strftime("%Y")}""").render({})
    assert r2 == """${datetime.datetime.now().strftime("%Y")}"""

    Settings.MAKO_SANDBOX_IMPORT_MODULES = {"datetime": "datetime"}

    r2 = Template("""${datetime.datetime.now().strftime("%Y")}""").render({})
    year = datetime.datetime.now().strftime("%Y")
    assert r2 == year

    Settings.MAKO_SANDBOX_IMPORT_MODULES = {}

    r3 = Template("""${exec(print(''))}""").render({})
    assert r1 == """${exec(print(''))}"""


def test_render__built_in_functions__with_args():
    int_template = Template("${int(111)}")
    assert int_template.render({}) == "111"

    int_template = Template("${str('aaa')}")
    assert int_template.render({}) == "aaa"


def test_redner__built_in_functions__cover():
    int_template = Template("${int}")
    assert int_template.render({"int": "cover"}) == "cover"


def test_mako_attack():
    attack_templates = [
        '${"".__class__.__mro__[-1].__subclasses__()[127].__init__.__globals__["system"]("whoami")}',  # noqa
        '${getattr("", dir(0)[0][0] + dir(0)[0][0] + "class" + dir(0)[0][0]+ dir(0)[0][0])}',  # noqa
        'a-${__import__("os").system("whoami")}',
        "${while True: pass}",
        """<% import json %> ${json.codecs.builtins.exec('import os; os.system("whoami")')}""",  # noqa
    ]
    for at in attack_templates:
        assert Template(at).render({}) == at


@pytest.fixture
def whitelist_mode():
    original_mode = Settings.MAKO_TEMPLATE_NAME_WHITELIST_MODE
    original_extra = Settings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST

    def _set(mode, extra=()):
        Settings.MAKO_TEMPLATE_NAME_WHITELIST_MODE = mode
        Settings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST = frozenset(extra)

    try:
        yield _set
    finally:
        Settings.MAKO_TEMPLATE_NAME_WHITELIST_MODE = original_mode
        Settings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST = original_extra


def test_mako_self_module_namespace_executes_when_whitelist_off(whitelist_mode):
    whitelist_mode("off")
    payload = '${self.module.cache.util.os.popen("echo OFF").read()}'
    rendered = Template(payload).render({})
    assert "OFF" in rendered


def test_mako_whitelist_default_blocks_self_module_namespace():
    payload = '${self.module.cache.util.os.popen("echo PWNED").read()}'
    assert Template(payload).render({}) == payload


def _assert_forbidden_template(payload):
    with pytest.raises(ForbiddenMakoTemplateException):
        check_mako_template_safety(
            payload,
            mako_safety.SingleLineNodeVisitor(),
            mako_safety.SingleLinCodeExtractor(),
        )


@pytest.mark.parametrize(
    "payload",
    [
        '${self.module.cache.util.os.popen("echo PWNED").read()}',
        "${context.lookup}",
        "${local.something}",
        "${parent.foo}",
        "${caller.body()}",
        "${pageargs.x}",
    ],
)
def test_mako_whitelist_blocks_reserved_namespaces(whitelist_mode, payload):
    whitelist_mode("enforce")
    assert Template(payload).render({}) == payload


@pytest.mark.parametrize(
    "payload",
    [
        '${os.path.os.popen("echo PWNED").read()}',
        '${os.path.genericpath.os.popen("echo PWNED").read()}',
        '${datetime.sys.modules["os"].popen("echo PWNED").read()}',
        '${re.enum.sys.modules["os"].popen("echo PWNED").read()}',
        '${os.path.os.system("echo PWNED")}',
    ],
)
def test_mako_whitelist_blocks_dangerous_attr_chain(whitelist_mode, payload):
    whitelist_mode("enforce")
    original_imports = Settings.MAKO_SANDBOX_IMPORT_MODULES
    Settings.MAKO_SANDBOX_IMPORT_MODULES = {
        "datetime": "datetime",
        "re": "re",
        "os.path": "os.path",
    }
    try:
        rendered = Template({"x": payload}).render({})
        assert rendered["x"] == payload
    finally:
        Settings.MAKO_SANDBOX_IMPORT_MODULES = original_imports


@pytest.mark.parametrize(
    "payload",
    [
        "${context._kwargs}",
        "${context._with_template}",
        "${context._data}",
        "${obj._secret}",
        "${obj.public._private}",
    ],
)
def test_mako_whitelist_blocks_single_underscore_attr(whitelist_mode, payload):
    whitelist_mode("enforce")
    rendered = Template({"x": payload}).render({"obj": object()})
    assert rendered["x"] == payload


def test_mako_whitelist_allows_business_patterns(whitelist_mode):
    whitelist_mode("enforce")
    cases = [
        ("${name.upper()}", {"name": "abc"}, "ABC"),
        ("${name.split('-')}", {"name": "a-b-c"}, "['a', 'b', 'c']"),
        ("${[x * 2 for x in items]}", {"items": [1, 2, 3]}, "[2, 4, 6]"),
        ("${(lambda y: y + 1)(seed)}", {"seed": 4}, "5"),
        ("${a if a else 'default'}", {"a": ""}, "default"),
        ("${len(items)}", {"items": [1, 2, 3]}, "3"),
    ]
    for tpl, ctx, expected in cases:
        assert Template(tpl).render(ctx) == expected


def test_mako_whitelist_allows_imported_modules(whitelist_mode):
    whitelist_mode("enforce")
    original_imports = Settings.MAKO_SANDBOX_IMPORT_MODULES
    Settings.MAKO_SANDBOX_IMPORT_MODULES = {
        "datetime": "datetime",
        "os.path": "os.path",
    }
    try:
        assert Template('${os.path.join("a", "b")}').render({}) == "a/b"
        out = Template('${datetime.datetime.now().strftime("%Y")}').render({})
        assert len(out) == 4 and out.isdigit()
    finally:
        Settings.MAKO_SANDBOX_IMPORT_MODULES = original_imports


def test_mako_whitelist_extra_names_allowed(whitelist_mode):
    whitelist_mode("enforce", extra=("_loop", "_system"))
    assert Template("${_loop}").render({"_loop": 7}) == 7
    assert Template("${_loop + 1}").render({"_loop": 2}) == "3"


def test_mako_whitelist_unknown_root_name_is_blocked(whitelist_mode):
    whitelist_mode("enforce")
    payload = "${secret_var}"
    assert Template(payload).render({}) == payload


def test_mako_filter_side_effect_expression_is_blocked():
    _assert_forbidden_template("${'x'|((side_effect() or str))}")


def test_mako_filter_dunder_chain_is_blocked():
    _assert_forbidden_template("${'x'|().__class__.__bases__[0].__subclasses__}")


def test_mako_filter_list_blocks_any_malicious_item():
    _assert_forbidden_template("${'x'|h, (side_effect() or str)}")


def test_mako_decode_filter_private_attribute_is_blocked():
    _assert_forbidden_template("${'x'|decode.__class__}")


@pytest.mark.parametrize(
    "payload",
    [
        '<%page expression_filter="(side_effect() or str)"/>${name}',
        '<%def name="render_name(name)" filter="(side_effect() or str)">${name}</%def>${render_name("x")}',
        '<%block filter="(side_effect() or str)">x</%block>',
        '<%text filter="(side_effect() or str)">x</%text>',
    ],
)
def test_mako_tag_filter_callables_are_blocked(payload):
    _assert_forbidden_template(payload)


@pytest.mark.parametrize(
    "payload",
    [
        "${' x ' | h}",
        "${' x ' | trim}",
        "${' x ' | h, trim}",
        "${'x' | n}",
        "${b'abc' | decode.utf8}",
    ],
)
def test_mako_builtin_filters_remain_allowed(payload):
    check_mako_template_safety(
        payload,
        mako_safety.SingleLineNodeVisitor(),
        mako_safety.SingleLinCodeExtractor(),
    )


def test_mako_builtin_filter_rendering_still_works():
    assert MakoTemplate("${'x' | h}").render_unicode() == "x"
    assert MakoTemplate("${' x ' | trim}").render_unicode() == "x"


def test_mako_filter_side_effect_is_not_executed_by_template_render():
    sentinel = {"called": False}

    def side_effect():
        sentinel["called"] = True
        return str

    payload = "${'x'|((side_effect() or str))}"

    assert Template(payload).render({"side_effect": side_effect}) == payload
    assert sentinel["called"] is False


@pytest.mark.parametrize(
    "payload",
    [
        '${"{0.__class__}".format("")}',
        '${"{value.__class__}".format_map({"value": ""})}',
    ],
)
def test_mako_format_private_lookup_is_blocked(payload):
    _assert_forbidden_template(payload)
