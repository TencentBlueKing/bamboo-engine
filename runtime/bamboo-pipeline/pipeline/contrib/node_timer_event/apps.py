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


class NodeTimerEventConfig(AppConfig):
    name = "pipeline.contrib.node_timer_event"
    verbose_name = "PipelineNodeTimerEvent"

    def ready(self):
        from pipeline.contrib.node_timer_event.signals.handlers import (  # noqa
            bamboo_engine_eri_node_state_handler,
        )
        from pipeline.contrib.node_timer_event.tasks import (  # noqa
            dispatch_expired_nodes,
            execute_node_timer_event_action,
        )

        if not hasattr(settings, "redis_inst"):
            raise Exception("Django Settings should have redis_inst attribute")
