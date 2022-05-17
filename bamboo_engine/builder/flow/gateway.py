# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bamboo_engine.eri import NodeType

from .base import Element

__all__ = [
    "ParallelGateway",
    "ExclusiveGateway",
    "ConvergeGateway",
    "ConditionalParallelGateway",
]


class ParallelGateway(Element):
    def type(self):
        return NodeType.ParallelGateway.value


class ConditionGateway(Element):
    def __init__(self, conditions=None, default_condition_outgoing=None, *args, **kwargs):
        self.conditions = conditions or {}
        self.default_condition_outgoing = default_condition_outgoing
        super(ConditionGateway, self).__init__(*args, **kwargs)

    def add_condition(self, index, evaluate):
        self.conditions[index] = evaluate

    def link_conditions_with(self, outgoing):
        conditions = {}
        for i, out in enumerate(outgoing):
            conditions[out] = {"evaluate": self.conditions[i]}

        return conditions

    def link_default_condition_with(self, outgoing):
        if self.default_condition_outgoing is None:
            return {}
        return {"flow_id": outgoing[self.default_condition_outgoing]}


class ConditionalParallelGateway(ConditionGateway):
    def type(self):
        return NodeType.ConditionalParallelGateway.value


class ExclusiveGateway(ConditionGateway):
    def type(self):
        return NodeType.ExclusiveGateway.value


class ConvergeGateway(Element):
    def type(self):
        return NodeType.ConvergeGateway.value
