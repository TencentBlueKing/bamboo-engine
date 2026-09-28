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

# mock str return value of Built-in Functions，make str(func) return "func" rather than "<built-in function func>"
#
# 渲染沙箱的构造原语已下沉到 Django-free 的 ``pipeline.core.data.sandbox_builder``，使无网无凭证的
# 隔离渲染子进程能复用**同一套**构造逻辑重建沙箱（不必 import Django / 业务 app / 凭证）。本模块保留
# Django 侧入口（读 settings、维护进程内全局 ``SANDBOX``）与历史向后兼容符号
# （``MockStrMeta`` / ``_shield_words`` / ``_import_modules`` / ``ModuleObject``）。

from pipeline.core.data import sandbox_builder
from pipeline.conf import default_settings

SANDBOX = {}

# 向后兼容原语：re-export Django-free 实现，保证进程内构造与隔离 worker 重建同源、不漂移。
ModuleObject = sandbox_builder.ModuleObject
_shield_words = sandbox_builder.shield_words
_import_modules = sandbox_builder.import_modules


class MockStrMeta(sandbox_builder.MockStrMeta):
    """历史 ``MockStrMeta``：动态定义 mock 类时自动注册进模块级 ``SANDBOX``。

    外部代码与既有测试依赖这一副作用，故保留；``__str__`` / ``__call__`` 复用
    ``sandbox_builder.MockStrMeta``，此处仅额外维持全局注册行为。
    """

    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        SANDBOX.update({new_cls.str_return: new_cls})
        return new_cls


# 进程内渲染沙箱：委托同源 Django-free builder 构造，仅在此读取 Django settings。
SANDBOX.update(
    sandbox_builder.build_sandbox(
        default_settings.MAKO_SANDBOX_SHIELD_WORDS,
        default_settings.MAKO_SANDBOX_IMPORT_MODULES,
    )
)
