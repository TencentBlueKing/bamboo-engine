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

import copy
import datetime

from django.test import TestCase

from pipeline.core.data import expression, mako_safety, sandbox
from pipeline.core.data.expression import format_constant_key, deformat_constant_key
from pipeline.utils.mako_utils.checker import check_mako_template_safety
from pipeline.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


class TestConstantTemplate(TestCase):
    def setUp(self):
        pass

    def test_format_constant_key(self):
        self.assertEqual(format_constant_key("a"), "${a}")

    def test_deformat_constant_key(self):
        self.assertEqual(deformat_constant_key("${a}"), "a")

    def test_get_reference(self):
        all_in_cons_template = expression.ConstantTemplate(["${a}", ["${a}", "${a+int(b)}"]])
        self.assertEqual(set(all_in_cons_template.get_reference()), {"a", "b", "int"})

        comma_exclude_template = expression.ConstantTemplate(['${a["c"]}', ['${"%s" % a}', "${a+int(b)}"]])
        self.assertEqual(set(comma_exclude_template.get_reference()), {"a", "b", "int"})

    def test_get_templates(self):
        cons_tmpl = expression.ConstantTemplate(["${a}", ["${a}", "${a+int(b)}"]])
        self.assertEqual(set(cons_tmpl.get_templates()), {"${a+int(b)}", "${a}"})

    def test_resolve_data(self):
        list_template = expression.ConstantTemplate(["${a}", ["${a}", "${a+int(b)}"]])
        self.assertEqual(list_template.resolve_data({"a": 2, "b": "3"}), [2, [2, "5"]])

        tuple_template = expression.ConstantTemplate(("${a}", ("${a}", "${a+int(b)}")))
        self.assertEqual(tuple_template.resolve_data({"a": 2, "b": "3"}), (2, (2, "5")))

        dict_template = expression.ConstantTemplate({"aaaa": {"a": "${a}", "b": "${a+int(b)}"}})
        self.assertEqual(dict_template.resolve_data({"a": 2, "b": "3"}), {"aaaa": {"a": 2, "b": "5"}})

    def test_get_string_templates(self):
        cons_tmpl = expression.ConstantTemplate("")
        self.assertEqual(cons_tmpl.get_string_templates("${a}"), ["${a}"])

    def test_resolve_template_with_curly_braces(self):
        cons_tmpl = expression.ConstantTemplate("")
        format_attr_template = '${"test_{}".format(a)}'
        self.assertEqual(cons_tmpl.resolve_string(format_attr_template, {"a": "1"}), format_attr_template)
        percent_template = '${"test_%s" % a}'
        self.assertEqual(cons_tmpl.resolve_string(percent_template, {"a": "1"}), "test_1")
        fstring_template = '${f"test_{a}"}'
        self.assertEqual(cons_tmpl.resolve_template(fstring_template, {"a": "2"}), "test_2")

    def test_resolve_string(self):
        cons_tmpl = expression.ConstantTemplate("")
        one_template = "${a}"
        self.assertEqual(cons_tmpl.resolve_string(one_template, {"a": "1"}), "1")

    def test_get_template_reference(self):
        cons_tmpl = expression.ConstantTemplate("")
        self.assertEqual(cons_tmpl.get_template_reference("${a}"), ["a"])

    def test_resolve_template(self):
        cons_tmpl = expression.ConstantTemplate("")
        simple = "${a}"
        self.assertEqual(cons_tmpl.resolve_template(simple, {"a": "1"}), "1")

        calculate = "${a+int(b)}"
        self.assertEqual(cons_tmpl.resolve_template(calculate, {"a": 2, "b": "3"}), "5")

        split = "${a[0]}"
        self.assertEqual(cons_tmpl.resolve_template(split, {"a": [1, 2]}), "1")

        dict_item = '${a["b"]}'
        self.assertEqual(cons_tmpl.resolve_template(dict_item, {"a": {"b": 1}}), "1")

        not_exists = "{a}"
        self.assertEqual(cons_tmpl.resolve_template(not_exists, {}), not_exists)

        resolve_syntax_error = "${a.b}"
        self.assertEqual(cons_tmpl.resolve_template(resolve_syntax_error, {}), resolve_syntax_error)

        template_syntax_error = "${a:b}"
        self.assertEqual(cons_tmpl.resolve_template(template_syntax_error, {}), template_syntax_error)

    def test_resolve_template__with_sandbox(self):

        r1 = expression.ConstantTemplate.resolve_template("""${exec(print(''))}""", {})
        self.assertEqual(r1, """${exec(print(''))}""")

        if "datetime" in expression.SANDBOX:
            expression.SANDBOX.pop("datetime")
        r2 = expression.ConstantTemplate.resolve_template("""${datetime.datetime.now().strftime("%Y")}""", {})
        self.assertEqual(r2, """${datetime.datetime.now().strftime("%Y")}""")

        sandbox._shield_words(expression.SANDBOX, ["exec", "compile"])
        sandbox._import_modules(expression.SANDBOX, {"datetime": "datetime"})

        r1 = expression.ConstantTemplate.resolve_template("""${exec(print(''))}""", {})
        self.assertEqual(r1, """${exec(print(''))}""")

        r2 = expression.ConstantTemplate.resolve_template("""${datetime.datetime.now().strftime("%Y")}""", {})
        year = datetime.datetime.now().strftime("%Y")
        self.assertEqual(r2, year)

        # clean
        expression.SANDBOX.pop("exec")
        expression.SANDBOX.pop("compile")

    def test_resolve(self):
        list_template = expression.ConstantTemplate(["${a}", ["${a}", "${a+int(b)}"]])
        self.assertEqual(list_template.resolve_data({"a": 2, "b": "3"}), [2, [2, "5"]])

        tuple_template = expression.ConstantTemplate(("${a}", ("${a}", "${a+int(b)}")))
        self.assertEqual(tuple_template.resolve_data({"a": 2, "b": "3"}), (2, (2, "5")))

        dict_template = expression.ConstantTemplate({"aaaa": {"a": "${a}", "b": "${a+int(b)}"}})
        self.assertEqual(dict_template.resolve_data({"a": 2, "b": "3"}), {"aaaa": {"a": 2, "b": "5"}})

    def test_get_reference_complex(self):
        all_in_cons_template = expression.ConstantTemplate(["${a}", ["${a}", "${a+int(b)}"]])
        self.assertEqual(set(all_in_cons_template.get_reference()), set(["a", "b", "int"]))

        comma_exclude_template = expression.ConstantTemplate(['${a["c"]}', ['${"%s" % a}', "${a+int(b)}"]])
        self.assertEqual(set(comma_exclude_template.get_reference()), set(["a", "b", "int"]))

    def test_built_in_functions__without_args(self):
        int_template = expression.ConstantTemplate("${int}")
        self.assertEqual(int_template.resolve_data({}), "int")

        int_template = expression.ConstantTemplate("${str}")
        self.assertEqual(int_template.resolve_data({}), "str")

    def test_built_in_functions__with_args(self):
        int_template = expression.ConstantTemplate("${int(111)}")
        self.assertEqual(int_template.resolve_data({}), "111")

        int_template = expression.ConstantTemplate("${str('aaa')}")
        self.assertEqual(int_template.resolve_data({}), "aaa")

    def test_built_in_functions__cover(self):
        int_template = expression.ConstantTemplate("${int}")
        self.assertEqual(int_template.resolve_data({"int": "cover"}), "cover")

    def test_template_join(self):
        template = expression.ConstantTemplate("a-${1 if t else 2}-${a}")
        self.assertEqual(template.resolve_data({"t": False, "a": "c"}), "a-2-c")
        template = expression.ConstantTemplate("${'a-%s-c' % 1 if t else 2}")
        self.assertEqual(template.resolve_data({"t": True}), "a-1-c")

    def test_mako_attack(self):
        sandbox_copy = copy.deepcopy(sandbox.SANDBOX)
        shield_words = [
            "ascii",
            "bytearray",
            "bytes",
            "callable",
            "chr",
            "classmethod",
            "compile",
            "delattr",
            "dir",
            "divmod",
            "exec",
            "eval",
            "filter",
            "frozenset",
            "getattr",
            "globals",
            "hasattr",
            "hash",
            "help",
            "id",
            "input",
            "isinstance",
            "issubclass",
            "iter",
            "locals",
            "map",
            "memoryview",
            "next",
            "object",
            "open",
            "print",
            "property",
            "repr",
            "setattr",
            "staticmethod",
            "super",
            "type",
            "vars",
            "__import__",
        ]
        sandbox._shield_words(sandbox.SANDBOX, shield_words)
        attack_templates = [
            '${"".__class__.__mro__[-1].__subclasses__()[127].__init__.__globals__["system"]("whoami")}',  # noqa
            '${getattr("", dir(0)[0][0] + dir(0)[0][0] + "class" + dir(0)[0][0]+ dir(0)[0][0])}',  # noqa
            'a-${__import__("os").system("whoami")}',
            "${while True: pass}",
            """<% import json %> ${json.codecs.builtins.exec('import os; os.system("whoami")')}""",  # noqa
        ]
        for at in attack_templates:
            self.assertEqual(expression.ConstantTemplate(at).resolve_data({}), at)

        sandbox.SANDBOX = sandbox_copy


class TestMakoNameWhitelist(TestCase):
    def setUp(self):
        from bamboo_engine.config import Settings as BambooSettings

        self._BambooSettings = BambooSettings
        self._original_mode = BambooSettings.MAKO_TEMPLATE_NAME_WHITELIST_MODE
        self._original_extra = BambooSettings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST

    def tearDown(self):
        self._BambooSettings.MAKO_TEMPLATE_NAME_WHITELIST_MODE = self._original_mode
        self._BambooSettings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST = self._original_extra

    def _set_mode(self, mode, extra=()):
        self._BambooSettings.MAKO_TEMPLATE_NAME_WHITELIST_MODE = mode
        self._BambooSettings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST = frozenset(extra)

    def test_off_mode_also_blocks_self_module(self):
        # 保留命名空间属性链下沉 always-on 后，off 模式也 inert
        # （此前 off 会解析出真实 os 模块执行命令，这里回归为拦截）。
        self._set_mode("off")
        payload = '${self.module.cache.util.os.popen("echo OFF").read()}'
        rendered = expression.ConstantTemplate(payload).resolve_data({})
        self.assertEqual(rendered, payload)

    def test_default_mode_blocks_self_module(self):
        payload = '${self.module.cache.util.os.popen("echo PWNED").read()}'
        rendered = expression.ConstantTemplate(payload).resolve_data({})
        self.assertEqual(rendered, payload)

    def test_enforce_blocks_self_module(self):
        self._set_mode("enforce")
        payload = '${self.module.cache.util.os.popen("echo PWNED").read()}'
        rendered = expression.ConstantTemplate(payload).resolve_data({})
        self.assertEqual(rendered, payload)

    def test_dangerous_attr_chain_blocked(self):
        self._set_mode("enforce")
        original_imports = self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES
        self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = {
            "datetime": "datetime",
            "re": "re",
            "os.path": "os.path",
        }
        try:
            payloads = [
                '${os.path.os.popen("echo PWNED").read()}',
                '${os.path.genericpath.os.popen("echo PWNED").read()}',
                '${datetime.sys.modules["os"].popen("echo PWNED").read()}',
                '${re.enum.sys.modules["os"].popen("echo PWNED").read()}',
            ]
            for p in payloads:
                with self.subTest(payload=p):
                    rendered = expression.ConstantTemplate(p).resolve_data({})
                    self.assertEqual(rendered, p)
        finally:
            self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = original_imports

    def test_reserved_namespace_attributes_blocked(self):
        self._set_mode("enforce")
        for p in [
            "${context._kwargs}",
            "${context._with_template}",
        ]:
            with self.subTest(payload=p):
                rendered = expression.ConstantTemplate(p).resolve_data({})
                self.assertEqual(rendered, p)

    def test_user_single_underscore_attr_allowed(self):
        self._set_mode("enforce")

        class Bag(object):
            def __init__(self):
                self._module = [{"gamesvr": "1.1.1.1"}]

        rendered = expression.ConstantTemplate("${obj._module[0]['gamesvr']}").resolve_data({"obj": Bag()})
        self.assertEqual(rendered, "1.1.1.1")

    def test_bare_caller_allowed(self):
        self._set_mode("enforce")
        # ConstantTemplate 对光杆 ``${caller}`` 会按 context 键短路，AST 走不到 visitor。
        self.assertEqual(
            expression.ConstantTemplate("${parent + ''}").resolve_data({"parent": "alice"}),
            "alice",
        )

    def test_import_deep_chain_blocked(self):
        self._set_mode("enforce")
        original = self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES
        self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = {"json": "json"}
        try:
            payload = "${json.codecs.builtins.exec('1')}"
            self.assertEqual(expression.ConstantTemplate(payload).resolve_data({}), payload)
        finally:
            self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = original

    def test_business_patterns_still_render(self):
        self._set_mode("enforce")
        cases = [
            ("${name.upper()}", {"name": "abc"}, "ABC"),
            ("${[x * 2 for x in items]}", {"items": [1, 2, 3]}, "[2, 4, 6]"),
            ("${(lambda y: y + 1)(seed)}", {"seed": 4}, "5"),
            ("${len(items)}", {"items": [1, 2]}, "2"),
        ]
        for tpl, ctx, expected in cases:
            with self.subTest(tpl=tpl):
                self.assertEqual(expression.ConstantTemplate(tpl).resolve_data(ctx), expected)

    def test_extra_whitelist_names(self):
        self._set_mode("enforce", extra=("_loop", "_system"))
        self.assertEqual(expression.ConstantTemplate("${_loop}").resolve_data({"_loop": 3}), 3)
        self.assertEqual(expression.ConstantTemplate("${_loop + 1}").resolve_data({"_loop": 4}), "5")

    def test_unknown_root_name_blocked(self):
        self._set_mode("enforce")
        payload = "${secret_var}"
        self.assertEqual(expression.ConstantTemplate(payload).resolve_data({}), payload)

    def test_generator_frame_gadget_blocked_all_modes(self):
        payload = (
            "${(i for i in [1]).gi_frame.f_builtins['eval']"
            "(\"__import__('os').popen('echo PWNED').read()\")}"
        )
        for mode in ("off", "warn", "enforce"):
            with self.subTest(mode=mode):
                self._set_mode(mode)
                self.assertEqual(expression.ConstantTemplate(payload).resolve_data({}), payload)

    def test_dangerous_attr_chain_blocked_all_modes(self):
        # 危险属性名下沉 always-on 后，模块反向 pivot 在 off / warn / enforce 三档都 inert。
        original_imports = self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES
        self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = {
            "datetime": "datetime",
            "re": "re",
            "os.path": "os.path",
            "json": "json",
        }
        payloads = [
            '${os.path.os.system("echo PWNED")}',
            '${datetime.sys.modules["os"].popen("echo PWNED").read()}',
            '${json.codecs.builtins.exec("import os")}',
        ]
        try:
            for mode in ("off", "warn", "enforce"):
                for p in payloads:
                    with self.subTest(mode=mode, payload=p):
                        self._set_mode(mode)
                        self.assertEqual(expression.ConstantTemplate(p).resolve_data({}), p)
        finally:
            self._BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = original_imports

    def test_reserved_namespace_chain_blocked_all_modes(self):
        for mode in ("off", "warn", "enforce"):
            for p in ("${context.lookup}", "${local.something}", "${parent.foo}"):
                with self.subTest(mode=mode, payload=p):
                    self._set_mode(mode)
                    self.assertEqual(expression.ConstantTemplate(p).resolve_data({}), p)


class TestMakoSafetyHardening(TestCase):
    def _assert_forbidden(self, payload):
        with self.assertRaises(ForbiddenMakoTemplateException):
            check_mako_template_safety(
                payload,
                mako_safety.SingleLineNodeVisitor(),
                mako_safety.SingleLinCodeExtractor(),
            )

    def _assert_allowed(self, payload):
        check_mako_template_safety(
            payload,
            mako_safety.SingleLineNodeVisitor(),
            mako_safety.SingleLinCodeExtractor(),
        )

    def test_filter_callable_with_side_effect_is_blocked(self):
        self._assert_forbidden("${'x'|((side_effect() or str))}")

    def test_filter_with_dunder_chain_is_blocked(self):
        self._assert_forbidden("${'x'|().__class__.__bases__[0].__subclasses__}")

    def test_filter_list_with_malicious_item_is_blocked(self):
        self._assert_forbidden("${'x'|h, (side_effect() or str)}")

    def test_decode_filter_with_dunder_is_blocked(self):
        self._assert_forbidden("${'x'|decode.__class__}")

    def test_tag_level_expression_filter_is_blocked(self):
        self._assert_forbidden('<%page expression_filter="(side_effect() or str)"/>${name}')

    def test_tag_level_def_filter_is_blocked(self):
        payload = '<%def name="r(x)" filter="(side_effect() or str)">${x}</%def>${r("x")}'
        self._assert_forbidden(payload)

    def test_tag_level_block_filter_is_blocked(self):
        self._assert_forbidden('<%block filter="(side_effect() or str)">x</%block>')

    def test_tag_level_text_filter_is_blocked(self):
        self._assert_forbidden('<%text filter="(side_effect() or str)">x</%text>')

    def test_format_attribute_call_is_blocked(self):
        self._assert_forbidden('${"{0.__class__}".format("")}')

    def test_format_map_attribute_call_is_blocked(self):
        self._assert_forbidden('${"{value.__class__}".format_map({"value": ""})}')

    def test_builtin_filters_remain_allowed(self):
        for payload in [
            "${' x ' | h}",
            "${' x ' | trim}",
            "${' x ' | h, trim}",
            "${'x' | n}",
            "${b'abc' | decode.utf8}",
        ]:
            with self.subTest(payload=payload):
                self._assert_allowed(payload)

    def test_frame_introspection_attrs_are_blocked(self):
        for attr in [
            "gi_frame",
            "gi_code",
            "cr_frame",
            "ag_frame",
            "f_back",
            "f_builtins",
            "f_globals",
            "f_locals",
            "f_code",
            "tb_frame",
            "tb_next",
            "func_globals",
        ]:
            with self.subTest(attr=attr):
                self._assert_forbidden("${obj.%s}" % attr)

    def test_restricted_builtins_strips_execution_primitives(self):
        from bamboo_engine.template import sandbox as engine_sandbox

        rb = engine_sandbox.restricted_builtins()
        for name in ("eval", "exec", "compile", "open", "input", "breakpoint"):
            self.assertNotIn(name, rb)
        for name in ("len", "str", "range", "int", "__import__"):
            self.assertIn(name, rb)

    def test_dangerous_attr_names_are_blocked_always_on(self):
        for attr in ("os", "sys", "subprocess", "builtins", "modules", "system", "popen", "kill"):
            with self.subTest(attr=attr):
                self._assert_forbidden("${obj.%s}" % attr)

    def test_reserved_namespace_chain_is_blocked_always_on(self):
        for payload in (
            '${self.module.cache.util}',
            "${context.lookup}",
            "${local.x}",
            "${parent.foo}",
            "${caller.body()}",
            "${pageargs.x}",
        ):
            with self.subTest(payload=payload):
                self._assert_forbidden(payload)

    def test_filter_import_modules_rejects_dangerous_keeps_safe(self):
        from bamboo_engine.template import sandbox as engine_sandbox

        src = {
            "os": "os",
            "subprocess": "subprocess",
            "operator": "operator",
            "pickle": "pickle",
            "os.path": "os.path",
            "json": "json",
        }
        self.assertEqual(set(engine_sandbox.filter_import_modules(src)), {"os.path", "json"})
