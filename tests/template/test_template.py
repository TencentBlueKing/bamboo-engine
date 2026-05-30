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

    default_enable_value = Settings.ENABLE_RENDER_OBJ_BY_MAKO_STRING
    Settings.ENABLE_RENDER_OBJ_BY_MAKO_STRING = True

    simple_list_template = Template("${a}")
    assert simple_list_template.render({"a": [1, 2, 3]}) == [1, 2, 3]

    nested_list_template = Template("${a[0][3]}")
    assert nested_list_template.render({"a": [[1, 2, 3, {"a": "b"}], [5, 6, 7, 8]]}) == {"a": "b"}

    simple_dict_template = Template("${a}")
    assert simple_dict_template.render({"a": {"a": "b"}}) == {"a": "b"}

    nested_dict_template = Template("${a[0][3]['a']}")
    assert nested_dict_template.render({"a": [[1, 2, 3, {"a": [1,2,3]}], [5, 6, 7, 8]]}) == [1,2,3]

    type_error_template = Template("${a[1]}")
    assert type_error_template.render({"a": 1}) == "${a[1]}"

    Settings.ENABLE_RENDER_OBJ_BY_MAKO_STRING = default_enable_value


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


# ---------------------------------------------------------------------------
# 根标识符白名单（``MAKO_TEMPLATE_NAME_WHITELIST_MODE``）。这套机制覆盖：
#
# 1. ``self / context / local / parent / next / caller / pageargs`` 等 Mako
#    渲染期注入的保留命名空间（堵 ``self.module.cache.util.os.popen`` SSTI 链路）。
# 2. attr 链路上的危险字段 / 单下划线 attr，堵 ``${os.path.os.popen(...)}``、
#    ``${datetime.sys.modules['os']...}``、``${context._kwargs}`` 这类反向引用。
# 3. 业务正常用法（字符串方法、``datetime.datetime.now().strftime(...)``、
#    ``os.path.join`` / 列表推导 / lambda）必须照常渲染。
# ---------------------------------------------------------------------------


@pytest.fixture
def whitelist_mode():
    """在 ``Settings`` 上切换 ``MAKO_TEMPLATE_NAME_WHITELIST_MODE``，测试结束后还原。"""
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
    """白名单关闭时，``self.module.*`` SSTI 链路是确实存在的——这是回归基线。"""
    whitelist_mode("off")
    payload = '${self.module.cache.util.os.popen("echo OFF").read()}'
    rendered = Template(payload).render({})
    assert "OFF" in rendered, "off 模式下白名单未启用，PoC 应仍执行"


def test_mako_whitelist_default_blocks_self_module_namespace():
    """默认配置必须阻断 ``self.module.*`` SSTI 链路。"""
    payload = '${self.module.cache.util.os.popen("echo PWNED").read()}'
    assert Template(payload).render({}) == payload


def _assert_forbidden_template(payload):
    with pytest.raises(ForbiddenMakoTemplateException):
        check_mako_template_safety(
            payload,
            mako_safety.SingleLineNodeVisitor(),
            mako_safety.SingleLinCodeExtractor(),
        )


def test_mako_filter_side_effect_expression_is_blocked():
    payload = "${'x'|((side_effect() or str))}"

    _assert_forbidden_template(payload)


def test_mako_filter_dunder_chain_is_blocked():
    payload = "${'x'|().__class__.__bases__[0].__subclasses__}"

    _assert_forbidden_template(payload)


def test_mako_filter_list_blocks_any_malicious_item():
    payload = "${'x'|h, (side_effect() or str)}"

    _assert_forbidden_template(payload)


def test_mako_decode_filter_private_attribute_is_blocked():
    payload = "${'x'|decode.__class__}"

    _assert_forbidden_template(payload)


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
        # ``os.path`` 内部 ``import os``：os.path.os is os
        '${os.path.os.popen("echo PWNED").read()}',
        # 嵌套子模块：os.path.genericpath.os 同样指向真实 os
        '${os.path.genericpath.os.popen("echo PWNED").read()}',
        # ``datetime`` import 了 sys，再走 sys.modules 拿 os
        '${datetime.sys.modules["os"].popen("echo PWNED").read()}',
        # ``re`` 重新 export ``enum``，``enum`` 内部 import sys
        '${re.enum.sys.modules["os"].popen("echo PWNED").read()}',
        # 直接调用 popen / system 也要拦
        '${os.path.os.system("echo PWNED")}',
    ],
)
def test_mako_whitelist_blocks_dangerous_attr_chain(whitelist_mode, payload):
    """白名单根名（``os / datetime / re``）必须挡得住 attr 链反向引用。"""
    whitelist_mode("enforce")
    original_imports = Settings.MAKO_SANDBOX_IMPORT_MODULES
    Settings.MAKO_SANDBOX_IMPORT_MODULES = {
        "datetime": "datetime",
        "re": "re",
        "os.path": "os.path",
    }
    try:
        rendered = Template({"x": payload}).render({})
        # ``rendered["x"] == payload`` 已经证明被拦后原样回显——不再用字面 PWNED 字符串
        # 二次断言（payload 本身就含 ``echo PWNED``，字符串包含关系无法区分"被拦的原文"
        # 和"被执行的输出"）。
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
        # os.path.join 仍可用（join 不在 DANGEROUS_ATTR_NAMES）
        assert Template('${os.path.join("a", "b")}').render({}) == "a/b"
        # datetime.datetime.now().strftime 链路全程合法
        out = Template('${datetime.datetime.now().strftime("%Y")}').render({})
        assert len(out) == 4 and out.isdigit()
    finally:
        Settings.MAKO_SANDBOX_IMPORT_MODULES = original_imports


def test_mako_whitelist_extra_names_allowed(whitelist_mode):
    whitelist_mode("enforce", extra=("_loop", "_system"))
    out = Template("${_loop}").render({"_loop": 7})
    # 单 token 模板会直接返回 context 中的原始值；当不存在时则按白名单评估表达式。
    assert out == 7
    assert Template("${_loop + 1}").render({"_loop": 2}) == "3"


def test_mako_whitelist_unknown_root_name_is_blocked(whitelist_mode):
    whitelist_mode("enforce")
    payload = "${secret_var}"
    assert Template(payload).render({}) == payload


def test_mako_whitelist_warn_mode_does_not_block_but_logs(whitelist_mode, caplog):
    whitelist_mode("warn")
    payload = "${self.module}"
    with caplog.at_level("WARNING"):
        # warn 模式下 visitor 自身不抛——但 Mako 渲染保留命名空间 ``self.module``
        # 时仍会在渲染层失败，因此结果取决于运行期；本测试只确认日志被打到。
        try:
            Template(payload).render({})
        except Exception:
            pass
    assert any("name not in whitelist" in r.getMessage() or "self" in r.getMessage() for r in caplog.records)


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


def test_mako_nested_dunder_expression_is_blocked():
    payload = "${().__class__.mro()}"

    assert Template(payload).render({}) == payload


@pytest.mark.parametrize(
    "payload",
    [
        '${"{0.__class__}".format("")}',
        '${"{value.__class__}".format_map({"value": ""})}',
    ],
)
def test_mako_format_private_lookup_is_blocked(payload):
    _assert_forbidden_template(payload)


# ---------------------------------------------------------------------------
# 纵深防御回归：以下 payload 当前**能通过 AST 安全检查**（visitor 只能识别字面 dunder /
# 已知禁用属性，无法穿透 BinOp/format/getattr 组合出的动态字符串），但通过运行期 sandbox
# shield (`MAKO_SANDBOX_SHIELD_WORDS`) 阻断。
#
# 把这些 payload 纳入回归是为了：未来一旦 ``Settings.MAKO_SANDBOX_SHIELD_WORDS`` 被
# 误改成不完整列表，或者 ``_render_template`` 把 ``context.update`` 顺序换成允许 context
# 覆盖 shield，这些用例会立刻红，提示重新评估纵深防御。
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        # BinOp 字符串拼接绕过字面量 dunder 检测
        "${getattr('', '__cl' + 'ass__')}",
        # 完整 subclasses RCE 链（多重 getattr + 字符串拼接）
        (
            "${getattr(getattr(getattr('', '__cl' + 'ass__'), '__ba' + 'se__'),"
            " '__sub' + 'classes__')()}"
        ),
        # 通过 dir(0)[0][0] 间接得到下划线字符再拼出 __class__
        "${getattr('', dir(0)[0][0] + dir(0)[0][0] + 'class' + dir(0)[0][0] + dir(0)[0][0])}",
        # type / object / vars 等 callable 走 Name 调用
        "${type('').mro()}",
        "${vars()}",
        # 内建 format() 走 Name 调用（visitor 仅拦 Attribute 形式的 .format(...)）
        "${format('', '')}",
        # breakpoint 未屏蔽时会触发 pdb，构成 DoS / 调试 RCE；shield 完整时必须 inert
        "${breakpoint()}",
    ],
)
def test_mako_latent_bypass_is_inert_at_render(payload):
    """这些 payload 必须始终在 ``Template.render`` 后保持 inert（原样回显）。

    它们能通过 AST 安全检查（visitor 只能识别字面 dunder / 已知禁用属性，无法穿透
    BinOp / dir()[0][0] / Name 调用组合出的动态字符串与危险内建调用），所以**唯一的
    防御**是 ``Settings.MAKO_SANDBOX_SHIELD_WORDS`` 中包含 ``getattr/type/vars/format/
    breakpoint`` 等条目。若任何一条变成"非原样输出"，意味着 shield 被弱化或
    ``_render_template`` 的 context 合并顺序被改动，需要立刻重新评估安全边界。
    """
    rendered = Template(payload).render({})
    assert rendered == payload, (
        "Mako sandbox bypass regression: payload {!r} rendered to {!r}, expected inert echo. "
        "Check Settings.MAKO_SANDBOX_SHIELD_WORDS completeness."
    ).format(payload, rendered)
