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

import functools
import logging
import traceback

from bamboo_engine.api import EngineAPIResult

logger = logging.getLogger("root")


class PipelineContribAPIResult(EngineAPIResult):
    pass


def ensure_return_pipeline_contrib_api_result(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
        except Exception as e:
            logger.exception("{} raise error.".format(func.__name__))
            trace = traceback.format_exc()
            return PipelineContribAPIResult(result=False, message="fail", exc=e, data=None, exc_trace=trace)

        return PipelineContribAPIResult(result=True, message="success", exc=None, data=data, exc_trace=None)

    return wrapper
