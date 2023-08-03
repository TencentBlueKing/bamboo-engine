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
from abc import ABCMeta, abstractmethod

from pipeline.eri.runtime import BambooDjangoRuntime
from bamboo_engine import api as bamboo_engine_api


class NodeTimeoutStrategy(metaclass=ABCMeta):
    TIMEOUT_NODE_OPERATOR = "bamboo_engine"

    @abstractmethod
    def deal_with_timeout_node(self, node_id, *args, **kwargs) -> dict:
        pass


class ForcedFailStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, node_id, *args, **kwargs):
        result = bamboo_engine_api.forced_fail_activity(
            runtime=BambooDjangoRuntime(),
            node_id=node_id,
            ex_data="forced fail by {}".format(self.TIMEOUT_NODE_OPERATOR),
            send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
        )
        return {"result": result.result, "message": result.message, "data": result.data}


class ForcedFailAndSkipStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, node_id, *args, **kwargs):
        result = bamboo_engine_api.forced_fail_activity(
            runtime=BambooDjangoRuntime(),
            node_id=node_id,
            ex_data="forced fail by {}".format(self.TIMEOUT_NODE_OPERATOR),
            send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
        )
        if result.result:
            result = bamboo_engine_api.skip_node(
                runtime=BambooDjangoRuntime(),
                node_id=node_id,
                ex_data="forced skip by {}".format(self.TIMEOUT_NODE_OPERATOR),
                send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
            )
        return {"result": result.result, "message": result.message, "data": result.data}


node_timeout_handler = {
    "forced_fail": ForcedFailStrategy(),
    "forced_fail_and_skip": ForcedFailAndSkipStrategy(),
}
