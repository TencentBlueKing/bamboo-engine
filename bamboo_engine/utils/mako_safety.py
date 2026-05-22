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

# Mako 安全工具


import ast
import logging
import re

from mako import parsetree

from .mako_utils.code_extract import MakoNodeCodeExtractor
from .mako_utils.exceptions import ForbiddenMakoTemplateException


logger = logging.getLogger("root")

# 与 ``MAKO_SANDBOX_SHIELD_WORDS`` 不重叠的"安全内建函数"集合。
# 用于白名单模式下默认放行的根标识符。
# 不包含 ``bytes/bytearray/frozenset/memoryview/object/type/vars/getattr/...``
# 等常出现在 shield 列表中的内建——它们即便能通过 AST 也会在渲染期被屏蔽成 ``None``，
# 留在白名单里只会带来认知噪音。
SAFE_BUILTIN_NAMES = frozenset(
    {
        "True",
        "False",
        "None",
        # 类型构造（不会构造危险对象）
        "bool",
        "int",
        "float",
        "str",
        "list",
        "tuple",
        "dict",
        "set",
        # 数学 / 长度
        "abs",
        "round",
        "pow",
        "sum",
        "min",
        "max",
        "len",
        # 序列
        "range",
        "slice",
        "enumerate",
        "zip",
        "sorted",
        "reversed",
        # 逻辑
        "all",
        "any",
    }
)

# Mako 在渲染期会向模板命名空间注入的保留对象名，用户模板里出现这些名字时
# 极大概率是在尝试触达模板内部对象（``self.module.cache.util.os...`` SSTI 链路）。
# 对它们直接拒绝，可以堵住绝大多数 namespace 链式 RCE 路径。
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

# attr 链路上一旦出现下列名字就立刻拒绝。
#
# 根 ``Name`` 白名单只能防"未授权根标识符"，挡不住通过白名单根名（如 ``os``、``datetime``、
# ``re``）反向触达危险模块的链路：
#
# * ``${os.path.os.popen(...)}``        — ``os.path`` 内部 ``import os``
# * ``${datetime.sys.modules['os']...}`` — ``datetime`` 内部 ``import sys``
# * ``${re.enum.sys.modules['os']...}``  — ``re`` 重新 export ``enum``，``enum`` 内 ``import sys``
#
# 所有这些链路都需要 attr 链上出现 ``os / sys / subprocess / shutil / ctypes / socket /
# builtins / modules`` 之一，或调用 ``popen / system / exec* / spawn* / fork*`` 之一。
# 直接把 attr 名拉黑，就能切掉公共必经路径。这是纵深防御里的"任何路径都不该带这些字"，
# 不是替代根名白名单。
DANGEROUS_ATTR_NAMES = frozenset(
    {
        # 直接拿到危险模块对象
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
        # 通过模块字典反向触达任意已导入模块
        "modules",
        # 进程 / 文件描述符相关原语（即便有人未来误把 ``os`` 加进白名单，也再加一层）
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
    for filter_arg in filter_args:
        normalized_filter = filter_arg.strip()
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
    """根据当前渲染 context 与全局 ``Settings`` 计算白名单的根标识符集合。

    包含：
      * ``context`` 中的键（``${name}`` 形式自动 deformat）
      * ``Settings.MAKO_SANDBOX_IMPORT_MODULES`` 中每个 alias 的首段
        （例：``os.path`` → ``os``）
      * :data:`SAFE_BUILTIN_NAMES`
      * ``Settings.MAKO_TEMPLATE_NAME_EXTRA_WHITELIST``
      * 调用方传入的 ``extra``
    """
    # 局部 import 避免循环依赖（``Settings`` 在 ``bamboo_engine.config``）。
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
    """根标识符白名单 visitor。

    只允许 Load 语义的 ``Name`` 节点引用 ``allowed_names`` 中的标识符；其余一律按
    ``mode`` 处理：

      * ``warn``：调用 ``on_violation`` / 打 warning 日志，**不抛异常**（灰度模式）。
      * ``enforce``：抛 :exc:`ForbiddenMakoTemplateException`，由
        :func:`bamboo_engine.utils.mako_utils.checker.check_mako_template_safety` 捕获。

    本 visitor 还显式拦截 :data:`MAKO_RESERVED_NAMESPACES` 中的标识符，
    无论是否被传入 ``allowed_names`` 都会被拒，避免误把 ``self/context/...`` 加进
    上下文导致 SSTI 链路被放行。

    支持 ``ListComp / SetComp / DictComp / GeneratorExp / Lambda`` 引入的局部
    绑定——这些临时变量会被压入作用域栈，在子树访问完后自动弹出。
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
        # Store / Del 上下文是赋值/删除目标，由 _enter_* 显式处理，跳过命名检查
        if not isinstance(node.ctx, ast.Load):
            return
        if node.id in MAKO_RESERVED_NAMESPACES:
            self._violate(node.id, "mako reserved namespace")
            return
        if not self._name_allowed(node.id):
            self._violate(node.id, "not in whitelist")

    def visit_Attribute(self, node):
        # 单下划线 attr 拒绝：堵 ``context._with_template / context._kwargs`` 这类
        # Python "半私有" 通道（双下划线已经在 ``SingleLineNodeVisitor`` 拦过，这里
        # 顺手收紧成单下划线，覆盖更广）。
        if node.attr.startswith("_"):
            self._violate(node.attr, "private attribute")
            return
        # 危险 attr 名拒绝：堵 ``${os.path.os.popen(...)}`` /
        # ``${datetime.sys.modules['os'].popen(...)}`` 类反向引用链路。
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
