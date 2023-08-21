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
from enum import Enum

from bamboo_engine.eri import ContextValueType

VAR_CONTEXT_MAPPING = {
    "plain": ContextValueType.PLAIN,
    "splice": ContextValueType.SPLICE,
    "lazy": ContextValueType.COMPUTE,
}


class ExclusiveGatewayStrategy(Enum):
    """
    网关命中策略
    """

    # 唯一命中
    ONLY = 1
    # 优先命中第一个
    FIRST = 2


class RuntimeSettings(Enum):
    PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC = "PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC"
    PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY = "PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY"
    PIPELINE_ENABLE_ROLLBACK = "PIPELINE_ENABLE_ROLLBACK"


RUNTIME_ALLOWED_CONFIG = [
    RuntimeSettings.PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC.value,
    RuntimeSettings.PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY.value,
    RuntimeSettings.PIPELINE_ENABLE_ROLLBACK.value,
]
