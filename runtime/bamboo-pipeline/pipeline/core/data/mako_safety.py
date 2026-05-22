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
import ast
import logging
import re

from mako import parsetree

from pipeline.utils.mako_utils.code_extract import MakoNodeCodeExtractor
from pipeline.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


logger = logging.getLogger("root")

# 与 ``MAKO_SANDBOX_SHIELD_WORDS`` 不重叠的"安全内建函数"集合，详见
# ``bamboo_engine.utils.mako_safety.SAFE_BUILTIN_NAMES``。
SAFE_BUILTIN_NAMES = frozenset(
    {
        "True",
        "False",
        "None",
        "bool",
        "int",
        "float",
        "str",
        "list",
        "tuple",
        "dict",
        "set",
        "abs",
        "round",
        "pow",
        "sum",
        "min",
        "max",
        "len",
        "range",
        "slice",
        "enumerate",
        "zip",
        "sorted",
        "reversed",
        "all",
        "any",
    }
)

# Mako 渲染期保留命名空间，详见 ``bamboo_engine.utils.mako_safety.MAKO_RESERVED_NAMESPACES``。
MAKO_RESERVED_NAMESPACES = frozenset(
    {
        "self",
        "context",
        "local",
        "parent",
        "next",
        "caller",
        "pageargs",
        "UNDEFINED",
        "STOP_RENDERING",
    }
)

# attr 链路危险字段，详见 ``bamboo_engine.utils.mako_safety.DANGEROUS_ATTR_NAMES``。
DANGEROUS_ATTR_NAMES = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "ctypes",
        "socket",
        "_thread",
        "threading",
        "builtins",
        "__builtins__",
        "modules",
        "popen",
        "popen2",
        "popen3",
        "popen4",
        "system",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "fork",
        "forkpty",
        "kill",
    }
)

FORBIDDEN_TEMPLATE_METHODS = {"format", "format_map"}
SAFE_FILTERS = {"n", "h", "x", "u", "trim", "entity", "unicode", "str"}
SAFE_DECODE_FILTER_PATTERN = re.compile(r"^decode\.[A-Za-z0-9][A-Za-z0-9_.-]*$")


class SingleLineNodeVisitor(ast.NodeVisitor):
    """
    遍历语法树节点，遇到魔术方法使用或 import 时，抛出异常
    """

    def __init__(self, *args, **kwargs):
        super(SingleLineNodeVisitor, self).__init__(*args, **kwargs)

    @staticmethod
    def _get_subscript_key(node):
        slice_node = node.slice
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return slice_node.value
        if hasattr(ast, "Str") and isinstance(slice_node, ast.Str):
            return slice_node.s
        return None

    def visit_Attribute(self, node):
        if node.attr.startswith("__"):
            raise ForbiddenMakoTemplateException("can not access private attribute")
        if node.attr in FORBIDDEN_TEMPLATE_METHODS:
            raise ForbiddenMakoTemplateException("can not call forbidden method")
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id.startswith("__"):
            raise ForbiddenMakoTemplateException("can not access private method")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        subscript_key = self._get_subscript_key(node)
        if isinstance(subscript_key, str) and subscript_key.startswith("__"):
            raise ForbiddenMakoTemplateException("can not access private key")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_TEMPLATE_METHODS:
            raise ForbiddenMakoTemplateException("can not call forbidden method")
        self.generic_visit(node)

    def visit_Import(self, node):
        raise ForbiddenMakoTemplateException("can not use import statement")

    def visit_ImportFrom(self, node):
        self.visit_Import(node)


def validate_filter_args(filter_args):
    """对 ``${expr | filter}`` 与 tag-level ``filter=`` 的 filter callable 做白名单校验。

    Mako 在渲染期会把 filter 表达式作为 Python 代码 ``eval`` 出 callable，因此必须在
    parse 阶段就拒绝任意 Python 表达式，否则攻击者可以通过 ``(side_effect() or str)``
    这种 filter 表达式绕过主表达式上的 AST 检查。
    """

    for filter_arg in filter_args:
        normalized_filter = filter_arg.strip()
        if not normalized_filter:
            continue
        if normalized_filter in SAFE_FILTERS:
            continue
        decode_filter_parts = normalized_filter.split(".")
        if (
            SAFE_DECODE_FILTER_PATTERN.match(normalized_filter)
            and "__" not in normalized_filter
            and not any(part.startswith("_") for part in decode_filter_parts[1:])
        ):
            continue
        raise ForbiddenMakoTemplateException("unsupported filter expression: [{}]".format(normalized_filter))


class SingleLinCodeExtractor(MakoNodeCodeExtractor):
    def extract(self, node):
        if isinstance(node, parsetree.Code) or isinstance(node, parsetree.Expression):
            return node.text
        elif isinstance(node, parsetree.Text):
            return None
        else:
            raise ForbiddenMakoTemplateException("Unsupported node: [{}]".format(node.__class__.__name__))


def _deformat_var_key(key):
    """``${name}`` -> ``name``；其它 key 原样返回。"""
    if isinstance(key, str) and key.startswith("${") and key.endswith("}"):
        return key[2:-1]
    return key


def build_allowed_names(context, *, extra=()):
    """legacy 模板渲染白名单根标识符集合。

    与 ``bamboo_engine.utils.mako_safety.build_allowed_names`` 行为一致：
    复用 ``bamboo_engine.config.Settings`` 上的 ``MAKO_SANDBOX_IMPORT_MODULES /
    MAKO_TEMPLATE_NAME_EXTRA_WHITELIST`` 配置，避免接入方维护两套白名单源。
    """
    from bamboo_engine.config import Settings

    allowed = set(SAFE_BUILTIN_NAMES)

    for key in context.keys() if context else ():
        allowed.add(_deformat_var_key(key))

    import_modules = getattr(Settings, "MAKO_SANDBOX_IMPORT_MODULES", None) or {}
    for alias in import_modules.values():
        if alias:
            allowed.add(alias.split(".", 1)[0])

    extra_whitelist = getattr(Settings, "MAKO_TEMPLATE_NAME_EXTRA_WHITELIST", None) or ()
    allowed.update(extra_whitelist)
    allowed.update(extra)

    return allowed


class WhitelistNameVisitor(ast.NodeVisitor):
    """legacy 渲染路径用的白名单 visitor，行为对齐
    ``bamboo_engine.utils.mako_safety.WhitelistNameVisitor``。
    """

    def __init__(self, allowed_names, mode="enforce", on_violation=None):
        if mode not in {"warn", "enforce"}:
            raise ValueError("invalid whitelist mode: {}".format(mode))
        self.allowed_names = set(allowed_names)
        self.mode = mode
        self.on_violation = on_violation
        self.scope_stack = []

    def _name_allowed(self, name):
        if name in MAKO_RESERVED_NAMESPACES:
            return False
        if name in self.allowed_names:
            return True
        for scope in self.scope_stack:
            if name in scope:
                return True
        return False

    def _violate(self, name, reason):
        msg = "name not in whitelist: {} ({})".format(name, reason)
        if self.on_violation is not None:
            try:
                self.on_violation(name, reason)
            except Exception:  # pragma: no cover - defensive
                logger.exception("on_violation callback raised")
        if self.mode == "enforce":
            raise ForbiddenMakoTemplateException(msg)
        logger.warning("[mako_whitelist] %s", msg)

    @staticmethod
    def _collect_targets(target, into):
        if isinstance(target, ast.Name):
            into.add(target.id)
        elif isinstance(target, ast.Starred):
            WhitelistNameVisitor._collect_targets(target.value, into)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                WhitelistNameVisitor._collect_targets(elt, into)

    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Load):
            return
        if node.id in MAKO_RESERVED_NAMESPACES:
            self._violate(node.id, "mako reserved namespace")
            return
        if not self._name_allowed(node.id):
            self._violate(node.id, "not in whitelist")

    def visit_Attribute(self, node):
        # 与新引擎 ``bamboo_engine.utils.mako_safety.WhitelistNameVisitor.visit_Attribute``
        # 保持一致：单下划线前缀 + 危险 attr 名一律拒绝，堵反向引用 SSTI 链路。
        if node.attr.startswith("_"):
            self._violate(node.attr, "private attribute")
            return
        if node.attr in DANGEROUS_ATTR_NAMES:
            self._violate(node.attr, "dangerous attribute")
            return
        self.generic_visit(node)

    def _enter_comprehension(self, node):
        local = set()
        for gen in node.generators:
            self._collect_targets(gen.target, local)
        self.scope_stack.append(local)
        try:
            self.generic_visit(node)
        finally:
            self.scope_stack.pop()

    def visit_ListComp(self, node):
        self._enter_comprehension(node)

    def visit_SetComp(self, node):
        self._enter_comprehension(node)

    def visit_DictComp(self, node):
        self._enter_comprehension(node)

    def visit_GeneratorExp(self, node):
        self._enter_comprehension(node)

    def visit_Lambda(self, node):
        local = set()
        args = node.args
        local.update(arg.arg for arg in args.args)
        local.update(arg.arg for arg in args.kwonlyargs)
        local.update(arg.arg for arg in getattr(args, "posonlyargs", ()) or ())
        if args.vararg:
            local.add(args.vararg.arg)
        if args.kwarg:
            local.add(args.kwarg.arg)
        self.scope_stack.append(local)
        try:
            self.generic_visit(node)
        finally:
            self.scope_stack.pop()
