# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from copy import deepcopy

from pipeline.conf import default_settings
from pipeline.core.data.context import Context
from pipeline.core.data.hydration import hydrate_node_data
from pipeline.core.flow.activity.sub_canvas import SubCanvas

from .base import FlowElementHandler

logger = logging.getLogger("pipeline_engine")

__all__ = ["SubCanvasHandler"]


class SubCanvasHandler(FlowElementHandler):
    @staticmethod
    def element_cls():
        return SubCanvas

    def handle(self, process, element, status):
        # rerun mode
        if status.loop > 1:
            element.prepare_rerun_data()
            element.pipeline.context.recover_variable()
            process.top_pipeline.context.recover_variable()

        # set loop count
        element.data.outputs._loop = status.loop + default_settings.PIPELINE_RERUN_INDEX_OFFSET

        # 子画布与父流程共享同一份上下文命名空间（act_outputs / output_key），
        # 但变量数据需要复制一份新的，避免子画布内部的写入污染父流程上下文
        parent_context = process.top_pipeline.context
        element.pipeline.context = Context(
            act_outputs=parent_context.act_outputs,
            output_key=parent_context._output_key,
            scope=deepcopy(parent_context.variables),
        )
        parent_context.extract_output(element, set_miss=False)

        # hydrate data
        hydrate_node_data(element)

        sub_pipeline = element.pipeline
        process.push_pipeline(sub_pipeline, is_subprocess=False)
        process.take_snapshot()
        return self.HandleResult(next_node=sub_pipeline.start_event, should_return=False, should_sleep=False)
