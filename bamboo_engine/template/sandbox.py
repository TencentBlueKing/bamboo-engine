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

import importlib

from bamboo_engine.config import Settings


def _shield_words(sandbox: dict, words: List[str]):
    for shield_word in words:
        sandbox[shield_word] = None


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
