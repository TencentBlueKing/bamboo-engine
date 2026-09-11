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
import re
import logging

from mako import lexer, codegen
from mako.exceptions import MakoException

from bamboo_engine.template.render_backend import get_render_backend, SandboxProvider, SandboxSpec
from pipeline import exceptions
from pipeline.conf.default_settings import MAKO_SAFETY_CHECK, MAKO_SANDBOX_SHIELD_WORDS, MAKO_SANDBOX_IMPORT_MODULES
from pipeline.core.data.sandbox import SANDBOX
from pipeline.core.data import mako_safety
from pipeline.utils.mako_utils.checker import check_mako_template_safety
from pipeline.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


logger = logging.getLogger("root")
# find mako template(format is ${xxx}，and ${}# not in xxx, # may raise memory error)
TEMPLATE_PATTERN = re.compile(r"\${[^$#]+}")


def _mako_render_sandbox():
    """render backend 的 sandbox_builder：在调用时读取本模块的 ``SANDBOX`` 全局。

    与历史实现 ``data.update(SANDBOX)`` 的语义严格一致——都以 *expression 模块此刻绑定的*
    ``SANDBOX`` 为准。这一点很关键：部分测试会 ``sandbox.SANDBOX = deepcopy(...)`` 重新绑定
    ``pipeline.core.data.sandbox`` 的全局，但历史渲染读的始终是 expression 侧捕获的对象，因此
    这里也必须读 expression 的 ``SANDBOX``，而不是 ``pipeline.core.data.sandbox`` 的实时全局，
    否则会在 rebind 后与历史行为分叉。该函数为模块级函数，可被隔离 backend 跨进程引用。
    """
    return SANDBOX


def format_constant_key(key):
    """
    @summary: format key to ${key}
    @param key:
    @return:
    """
    return "${%s}" % key


def deformat_constant_key(key):
    """
    @summary: deformat ${key} to key
    @param key:
    @return:
    """
    return key[2:-1]


class ConstantTemplate(object):
    def __init__(self, data):
        self.data = data

    def get_reference(self):
        reference = []
        templates = self.get_templates()
        for tpl in templates:
            reference += self.get_template_reference(tpl)
        reference = list(set(reference))
        return reference

    def get_templates(self):
        templates = []
        data = self.data
        if isinstance(data, str):
            templates += self.get_string_templates(data)
        if isinstance(data, (list, tuple)):
            for item in data:
                templates += ConstantTemplate(item).get_templates()
        if isinstance(data, dict):
            for value in list(data.values()):
                templates += ConstantTemplate(value).get_templates()
        return list(set(templates))

    def resolve_data(self, value_maps):
        data = self.data
        if isinstance(data, str):
            return self.resolve_string(data, value_maps)
        if isinstance(data, list):
            ldata = [""] * len(data)
            for index, item in enumerate(data):
                ldata[index] = ConstantTemplate(copy.deepcopy(item)).resolve_data(value_maps)
            return ldata
        if isinstance(data, tuple):
            ldata = [""] * len(data)
            for index, item in enumerate(data):
                ldata[index] = ConstantTemplate(copy.deepcopy(item)).resolve_data(value_maps)
            return tuple(ldata)
        if isinstance(data, dict):
            for key, value in list(data.items()):
                data[key] = ConstantTemplate(copy.deepcopy(value)).resolve_data(value_maps)
            return data
        return data

    @staticmethod
    def get_string_templates(string):
        return list(set(TEMPLATE_PATTERN.findall(string)))

    @staticmethod
    def get_template_reference(template):
        lex = lexer.Lexer(template)

        try:
            node = lex.parse()
        except MakoException as e:
            logger.warning("pipeline get template[{}] reference error[{}]".format(template, e))
            return []

        # Dummy compiler. _Identifiers class requires one
        # but only interested in the reserved_names field
        def compiler():
            return None

        compiler.reserved_names = set()
        identifiers = codegen._Identifiers(compiler, node)

        return list(identifiers.undeclared)

    @staticmethod
    def resolve_string(string, value_maps):
        if not isinstance(string, str):
            return string
        templates = ConstantTemplate.get_string_templates(string)

        # TODO keep render return object, here only process simple situation
        if len(templates) == 1 and templates[0] == string and deformat_constant_key(string) in value_maps:
            return value_maps[deformat_constant_key(string)]

        for tpl in templates:
            if MAKO_SAFETY_CHECK:
                try:
                    check_mako_template_safety(
                        tpl, mako_safety.SingleLineNodeVisitor(), mako_safety.SingleLinCodeExtractor()
                    )
                except ForbiddenMakoTemplateException as e:
                    logger.warning("forbidden template: {}, exception: {}".format(tpl, e))
                    continue
                except Exception:
                    logger.exception("{} safety check error.".format(tpl))
                    continue

                # 根标识符白名单，与新引擎 ``bamboo_engine.template.Template`` 保持一致。
                from bamboo_engine.config import Settings as _BambooSettings

                whitelist_mode = getattr(_BambooSettings, "MAKO_TEMPLATE_NAME_WHITELIST_MODE", "off")
                if whitelist_mode in {"warn", "enforce"}:
                    try:
                        allowed_names = mako_safety.build_allowed_names(value_maps)
                        check_mako_template_safety(
                            tpl,
                            mako_safety.WhitelistNameVisitor(allowed_names, mode=whitelist_mode),
                            mako_safety.SingleLinCodeExtractor(),
                        )
                    except ForbiddenMakoTemplateException as e:
                        logger.warning("forbidden by whitelist: {}, exception: {}".format(tpl, e))
                        continue
                    except Exception:
                        logger.exception("{} whitelist check error.".format(tpl))
                        continue

            resolved = ConstantTemplate.resolve_template(tpl, value_maps)
            string = string.replace(tpl, resolved)
        return string

    @staticmethod
    def resolve_template(template, value_maps):
        if not isinstance(template, str):
            raise exceptions.ConstantTypeException("constant resolve error, template[%s] is not a string" % template)
        # 与 ``bamboo_engine.template.template.Template._render_template`` 对齐：唯一的“执行用户
        # 表达式”入口下沉到可插拔 render backend，默认行为完全不变。provider 同时提供：进程内
        # ``_mako_render_sandbox`` 现场取沙箱（mock builtins + shield + 注入模块），与可序列化的
        # ``SandboxSpec``（legacy flavor，供隔离 backend 在子进程本地重建沙箱、只序列化 value_maps）。
        provider = SandboxProvider(
            _mako_render_sandbox,
            SandboxSpec("legacy", MAKO_SANDBOX_SHIELD_WORDS, MAKO_SANDBOX_IMPORT_MODULES),
        )
        return get_render_backend().render(template, value_maps, provider)
