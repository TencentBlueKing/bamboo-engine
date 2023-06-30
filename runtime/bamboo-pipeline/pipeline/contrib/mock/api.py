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
from pipeline.contrib.utils import ensure_return_pipeline_contrib_api_result

from pipeline.contrib.mock.hanlder import MockHandler


@ensure_return_pipeline_contrib_api_result
def update_node_outputs(root_pipeline_id, node_id, context_values):
    """
    批量修改任务某个节点的输出和上下文
    :param root_pipeline_id: pipeline的id
    :param node_id: 节点id
    :param context_values: {
        "${code}": 200
    }
    :return:
    """
    MockHandler(root_pipeline_id, node_id, context_values).update_node_outputs()
