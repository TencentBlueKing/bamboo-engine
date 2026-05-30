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
from bamboo_engine.utils.constants import ExclusiveGatewayStrategy
from bamboo_engine.utils.expr import default_expr_func

# 引擎内部配置模块


class Settings:
    """
    引擎全局配置对象
    """

    MAKO_SANDBOX_SHIELD_WORDS = [
        "ascii",
        "breakpoint",
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
        "format",
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

    MAKO_SANDBOX_IMPORT_MODULES = {}

    # 模板根标识符白名单模式：
    #   "off"     - 关闭白名单（兼容历史行为）
    #   "warn"    - 仅记录违规日志，不阻断渲染（灰度阶段使用）
    #   "enforce" - 违规即按当前 deny-list 风格拦截（行为同 ForbiddenMakoTemplateException）
    # 默认 "enforce"，避免默认安装后继续暴露 Mako 渲染期保留命名空间注入链路。
    # 如接入方确有兼容性风险，可在自身 settings 中临时切到 "warn" 或 "off"。
    MAKO_TEMPLATE_NAME_WHITELIST_MODE = "enforce"

    # 在白名单基础上额外允许的根标识符（除 context/导入模块/SAFE_BUILTIN_NAMES 之外）。
    # 接入方通常用于声明 ``_system``、``_loop`` 这类 Mako 渲染期才注入的特殊对象名。
    MAKO_TEMPLATE_NAME_EXTRA_WHITELIST = frozenset()

    RERUN_INDEX_OFFSET = 0

    # 当字符串是纯mako字符串时，是否自动渲染成对象，默认还是会渲染成字符串
    ENABLE_RENDER_OBJ_BY_MAKO_STRING = False

    PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC = default_expr_func

    PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY = ExclusiveGatewayStrategy.ONLY.value

    PIPELINE_ENABLE_ROLLBACK = False

    LOOP_OUTPUTS_INNER_KEY = "outputs"
