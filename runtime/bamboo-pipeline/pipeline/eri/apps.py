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

from django.apps import AppConfig
from django.conf import settings
from pipeline.exceptions import ConfigValidationError

from bamboo_engine.handlers import register
from bamboo_engine.utils.constants import ExclusiveGatewayStrategy


class ERIConfig(AppConfig):
    name = "pipeline.eri"
    verbose_name = "PipelineEngineRuntimeInterface"

    def ready(self):
        from .celery.tasks import execute, schedule  # noqa

        register()

        # 校验 PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC 配置
        if hasattr(settings, "PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC"):

            pipeline_exclusive_gateway_expr_func = getattr(settings, "PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC", None)
            if not callable(pipeline_exclusive_gateway_expr_func):
                raise ConfigValidationError("config validate error, the expr func must be callable, please check it")

            # 是否校验
            pipeline_exclusive_gateway_expr_func_check = getattr(
                settings, "PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC_CHECK", True
            )
            if pipeline_exclusive_gateway_expr_func_check:
                # 获取校验文本
                pipeline_exclusive_gateway_expr_func_text = getattr(
                    settings, "PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC_TEXT", "1==1"
                )
                check_result = pipeline_exclusive_gateway_expr_func(pipeline_exclusive_gateway_expr_func_text, {}, {})
                if not check_result:
                    raise ConfigValidationError("config validate error, the expr func return False")

        if hasattr(settings, "PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY"):
            pipeline_exclusive_gateway_strategy = getattr(settings, "PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY")
            if pipeline_exclusive_gateway_strategy not in [
                ExclusiveGatewayStrategy.ONLY.value,
                ExclusiveGatewayStrategy.FIRST.value,
            ]:
                raise ConfigValidationError(
                    "config validate error, the pipeline_exclusive_gateway_strategy only support 1(ONLY), 2(FIRST)"
                )
