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
import re

from mako import parsetree

from pipeline.utils.mako_utils.code_extract import MakoNodeCodeExtractor
from pipeline.utils.mako_utils.exceptions import ForbiddenMakoTemplateException


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
