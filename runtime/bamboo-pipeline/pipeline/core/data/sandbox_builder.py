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

# 渲染沙箱构造原语（Django-free）。
#
# 目的：把「构造 legacy 渲染沙箱命名空间」这件事与 Django settings 彻底解耦，使其可以在一个
# **精简、无网、无凭证的隔离渲染子进程**里被重建——子进程只需 import 本模块 + bamboo_engine
# 的沙箱原语，而**不必** import ``pipeline.conf`` / Django / 业务 app（那会把平台密钥、DB/ESB
# 凭证重新带回子进程，破坏隔离承诺）。
#
# 与历史 ``pipeline.core.data.sandbox`` 的构造语义严格等价：
#   * mock builtins：``str(int) -> "int"``、``int("3") -> 3``（模板里 ``${int}`` 打印成名字）；
#   * shield words：把危险名在命名空间里置 None；
#   * import modules：按别名注入模块 / ModuleObject 链，并复用 bamboo_engine 的注入 deny-list。
#
# 关键区别：本模块**不依赖任何模块级全局**，``build_sandbox`` 每次返回全新 dict，天然规避跨渲染
# 状态泄漏——这正是隔离 worker「每次 render 拿到 pristine 命名空间」所需要的。

import builtins

from bamboo_engine.template.sandbox import filter_import_modules, resolve_import_object


class MockStrMeta(type):
    """使内建函数代理类的 ``str(cls)`` 返回原名、``cls(...)`` 调用真实内建。

    与历史实现不同：这里**不**在 ``__new__`` 里写任何模块级全局，构造过程全部落在传入的 dict 上，
    保证 Django-free 且无副作用。
    """

    def __str__(cls):
        return cls.str_return

    def __call__(cls, *args, **kwargs):
        return cls.call(*args, **kwargs)


def make_mock_builtin(func_name):
    """为单个内建名生成一个 :class:`MockStrMeta` 代理类。"""
    new_func_name = "Mock{}".format(func_name.capitalize())
    return MockStrMeta(new_func_name, (object,), {"call": getattr(builtins, func_name), "str_return": func_name})


def add_mock_builtins(sandbox):
    """把安全内建（小写、非 ``_`` 开头）的 mock 代理类注入 ``sandbox``。"""
    for func_name in dir(builtins):
        if func_name.lower() == func_name and not func_name.startswith("_"):
            cls = make_mock_builtin(func_name)
            sandbox[cls.str_return] = cls
    return sandbox


def shield_words(sandbox, words):
    """把 ``words`` 中的每个名字在 ``sandbox`` 里置 None（渲染期取用即失败）。"""
    for shield_word in words or []:
        sandbox[shield_word] = None
    return sandbox


class ModuleObject:
    def __init__(self, sub_paths, module):
        if len(sub_paths) == 1:
            setattr(self, sub_paths[0], module)
            return
        setattr(self, sub_paths[0], ModuleObject(sub_paths[1:], module))


def import_modules(sandbox, modules):
    """按别名把 ``modules`` 注入 ``sandbox``；复用 bamboo_engine 的注入 deny-list 兜底。"""
    modules = filter_import_modules(modules or {})
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
    return sandbox


def build_sandbox(shield, imports):
    """从（shield_words, import_modules）配置构造一个全新的 legacy 渲染沙箱命名空间。

    :param shield: 需要在命名空间里置 None 的危险名列表
    :param imports: ``{模块路径: 别名}`` 注入表
    :return: 全新 dict（mock builtins + shields + 注入模块）
    """
    sandbox = {}
    add_mock_builtins(sandbox)
    shield_words(sandbox, shield)
    import_modules(sandbox, imports)
    return sandbox
