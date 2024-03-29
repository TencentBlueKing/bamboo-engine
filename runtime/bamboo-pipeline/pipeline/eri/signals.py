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

from django.dispatch import Signal

post_set_state = Signal(providing_args=["node_id", "to_state", "version", "root_id", "parent_id", "loop"])
execute_interrupt = Signal(providing_args=["event"])
schedule_interrupt = Signal(providing_args=["event"])
pre_service_execute = Signal(providing_args=["service", "data", "parent_data"])
pre_service_schedule = Signal(providing_args=["service", "data", "parent_data", "callback_data"])

pipeline_event = Signal(providing_args=["event"])
