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

pipeline_ready = Signal()
pipeline_end = Signal()
pipeline_revoke = Signal()
child_process_ready = Signal()
process_ready = Signal()
batch_process_ready = Signal()
wake_from_schedule = Signal()
schedule_ready = Signal()
process_unfreeze = Signal()
# activity failed signal
activity_failed = Signal()

# signal for developer (do not use valve to pass them!)
service_schedule_fail = Signal()
service_schedule_success = Signal()
node_skip_call = Signal()
node_retry_ready = Signal()

service_activity_timeout_monitor_start = Signal()
service_activity_timeout_monitor_end = Signal()
