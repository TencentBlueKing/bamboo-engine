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
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine import api as bamboo_engine_api
from .base import ActionRequestHandler, HandlerType


class BambooEngineRequestHandler(ActionRequestHandler):
    handler_type = HandlerType.BAMBOO_ENGINE

    def task_pause(self, **kwargs):
        return bamboo_engine_api.pause_pipeline(runtime=BambooDjangoRuntime(), pipeline_id=self.instance_id)

    def task_resume(self, **kwargs):
        return bamboo_engine_api.resume_pipeline(runtime=BambooDjangoRuntime(), pipeline_id=self.instance_id)

    def task_revoke(self, **kwargs):
        return bamboo_engine_api.revoke_pipeline(runtime=BambooDjangoRuntime(), pipeline_id=self.instance_id)

    def node_retry(self, **kwargs):
        runtime = BambooDjangoRuntime()
        api_result = bamboo_engine_api.get_data(runtime=runtime, node_id=self.instance_id)
        if not api_result.result:
            return api_result
        return bamboo_engine_api.retry_node(runtime=runtime, node_id=self.instance_id, data=kwargs.get("inputs"))

    def node_skip(self, **kwargs):
        return bamboo_engine_api.skip_node(runtime=BambooDjangoRuntime(), node_id=self.instance_id)

    def node_callback(self, **kwargs):
        runtime = BambooDjangoRuntime()
        version = kwargs.get("version")
        if not version:
            version = runtime.get_state(self.instance_id).version
        return bamboo_engine_api.callback(
            runtime=BambooDjangoRuntime(), node_id=self.instance_id, data=kwargs.get("data"), version=version
        )

    def node_skip_exg(self, **kwargs):
        return bamboo_engine_api.skip_exclusive_gateway(
            runtime=BambooDjangoRuntime(), node_id=self.instance_id, flow_id=kwargs["flow_id"]
        )

    def node_skip_cpg(self, **kwargs):
        return bamboo_engine_api.skip_conditional_parallel_gateway(
            runtime=BambooDjangoRuntime(),
            node_id=self.instance_id,
            flow_ids=kwargs["flow_ids"],
            converge_gateway_id=kwargs["converge_gateway_id"],
        )

    def node_forced_fail(self, **kwargs):
        return bamboo_engine_api.forced_fail_activity(
            runtime=BambooDjangoRuntime(),
            node_id=self.instance_id,
            ex_data=f"force fail by {kwargs.get('operator', 'engine_admin')}",
            send_post_set_state_signal=kwargs.get("send_post_set_state_signal", False),
        )
