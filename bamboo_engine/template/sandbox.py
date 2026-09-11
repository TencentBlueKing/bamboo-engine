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


# 模板渲染沙箱


from typing import List, Dict

import logging
import importlib

from bamboo_engine.config import Settings

logger = logging.getLogger("root")


# 渲染期从模板模块 ``__builtins__`` 中摘除的危险内建。
#
# Mako 会把每段模板编译进一个独立 module，其 ``__builtins__`` 默认指向**真实** builtins。
# 模板里通过 ``(g).gi_frame.f_builtins`` / ``frame.f_globals['__builtins__']`` 等反射链路
# 拿到的正是这个 module 的 builtins。即便 AST deny-list 漏掉了某条通向 frame 的属性，
# 只要这里事先把可直接"执行代码 / 读写文件"的原语摘掉，攻击者拿到的 builtins 视图里也
# 不再有可用武器，是 deny-list 之外的纵深防御（capability allow-list by removal）。
#
# 仅摘除"非 ``__`` 前缀、可当作下标 key 直接取用"的执行 / IO 原语：
# ``f_builtins['eval'](...)`` / ``['exec'](...)`` / ``['open'](...)`` 这类。
# 刻意**保留** ``__import__``：它是 ``__`` 前缀（下标 / 属性 / 名称三条路径都已被
# dunder 规则拦死，无法被直接取用），且 CPython 的 C 扩展在渲染期会惰性 import
# （如 ``datetime.strftime`` 内部 ``import time``），摘掉会误伤正常渲染。
# 同样保留 ``str/len/range`` 等 Mako codegen 与业务表达式需要的安全内建。
DANGEROUS_RENDER_BUILTINS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
    }
)

_RESTRICTED_BUILTINS = None


def restricted_builtins() -> dict:
    """返回去除 :data:`DANGEROUS_RENDER_BUILTINS` 后的 builtins 视图（只读、进程内缓存）。"""
    global _RESTRICTED_BUILTINS
    if _RESTRICTED_BUILTINS is None:
        import builtins as _builtins

        safe = {name: getattr(_builtins, name) for name in dir(_builtins)}
        for name in DANGEROUS_RENDER_BUILTINS:
            safe.pop(name, None)
        _RESTRICTED_BUILTINS = safe
    return _RESTRICTED_BUILTINS


def harden_template_builtins(mako_template) -> None:
    """把编译后模板模块的 ``__builtins__`` 换成去除危险原语的视图。

    需在任何一次 render 创建 frame 之前调用。Mako 各版本内部结构略有差异，任何异常都不应
    影响正常渲染，因此整体 try/except 兜底。
    """
    try:
        mako_template.module.__builtins__ = restricted_builtins()
    except Exception:  # pragma: no cover - defensive, never break rendering
        logger.warning("failed to harden mako template builtins")


def _shield_words(sandbox: dict, words: List[str]):
    for shield_word in words:
        sandbox[shield_word] = None


# 绝不允许注入 ``MAKO_SANDBOX_IMPORT_MODULES`` 的模块根。
#
# 注入模块白名单是整个沙箱的信任根：一旦把下列任意模块注入渲染命名空间，攻击者无需触碰
# dunder / frame，直接 ``${module.<primitive>(...)}`` 就能执行代码 / 导入 / 反序列化 /
# 读写文件，AST deny-list 与根名白名单全部形同虚设（例如 ``operator.attrgetter('__globals__')``
# 用字符串绕过 dunder 检查、``pickle.loads`` 反序列化、``os.system`` 直接命令执行）。
# 这里在注入入口做一层 deny-list 兜底：即便接入方误配置，也拒绝把这些模块放进沙箱。
DANGEROUS_IMPORT_MODULE_ROOTS = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "importlib",
        "imp",
        "runpy",
        "operator",
        "inspect",
        "pickle",
        "_pickle",
        "cpickle",
        "marshal",
        "shelve",
        "dill",
        "ctypes",
        "cffi",
        "pty",
        "platform",
        "pydoc",
        "code",
        "codeop",
        "builtins",
        "__builtin__",
        "gc",
        "socket",
        "shutil",
        "signal",
        "multiprocessing",
        "threading",
        "_thread",
        "mmap",
        "fcntl",
        "resource",
        "tempfile",
        "pdb",
        "bdb",
        "trace",
        "timeit",
        "ast",
        "compileall",
        "py_compile",
    }
)

# deny-list 的例外：这些子模块本身不暴露执行原语，历史上被业务合法注入（如 ``os.path`` 的
# ``join / exists``）。``os.path.os`` / ``os.path.sys`` 这类反向 pivot 已由 always-on 的属性
# deny-list（``DANGEROUS_ATTR_NAMES``）拦截，因此保留 ``os.path`` 是安全的。
SAFE_IMPORT_SUBMODULES = frozenset({"os.path"})

_WARNED_DANGEROUS_IMPORTS = set()


def _is_dangerous_import(mod_path: str) -> bool:
    if not mod_path:
        return False
    if mod_path in SAFE_IMPORT_SUBMODULES:
        return False
    root = mod_path.split(".", 1)[0]
    return root in DANGEROUS_IMPORT_MODULE_ROOTS


def filter_import_modules(modules: Dict[str, str]) -> Dict[str, str]:
    """剔除 deny-list 中的危险模块，返回可安全注入沙箱的子集。

    命中危险模块时不抛异常（避免误配置直接打挂全部渲染），改为跳过 + 记录一次 error 日志，
    保证系统 fail-safe：危险模块不会进入渲染命名空间，依赖它的模板会以 inert 形式失败并留痕。
    """
    safe = {}
    for mod_path, alias in modules.items():
        if _is_dangerous_import(mod_path):
            if mod_path not in _WARNED_DANGEROUS_IMPORTS:
                _WARNED_DANGEROUS_IMPORTS.add(mod_path)
                logger.error(
                    "refuse to inject dangerous module into mako sandbox: %s (alias=%s)",
                    mod_path,
                    alias,
                )
            continue
        safe[mod_path] = alias
    return safe


class ModuleObject:
    def __init__(self, sub_paths, module):
        if len(sub_paths) == 1:
            setattr(self, sub_paths[0], module)
            return
        setattr(self, sub_paths[0], ModuleObject(sub_paths[1:], module))


def resolve_import_object(mod_path):
    try:
        return importlib.import_module(mod_path)
    except ImportError:
        parts = mod_path.split(".")
        obj = importlib.import_module(parts[0])
        for part in parts[1:]:
            obj = getattr(obj, part)
        return obj


def _import_modules(sandbox: dict, modules: Dict[str, str]):
    modules = filter_import_modules(modules)
    items = sorted(modules.items(), key=lambda kv: kv[1].count("."))
    for mod_path, alias in items:
        obj = resolve_import_object(mod_path)
        sub_paths = alias.split(".")
        if len(sub_paths) == 1:
            sandbox[alias] = obj
            continue
        root = sub_paths[0]
        existing = sandbox.get(root)
        if existing is not None and not isinstance(existing, ModuleObject):
            continue
        sandbox[root] = ModuleObject(sub_paths[1:], obj)


def get() -> dict:
    sandbox = {}

    _shield_words(sandbox, Settings.MAKO_SANDBOX_SHIELD_WORDS)
    _import_modules(sandbox, Settings.MAKO_SANDBOX_IMPORT_MODULES)

    return sandbox
