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

from bamboo_engine.eri import interfaces
from bamboo_engine.eri.interfaces import ProcessMixin, ScheduleMixin, StateMixin


def test_eri_version():
    assert interfaces.__version__ == "7.2.0"


def test_fence_interfaces_declared():
    for mixin, name in (
        (ProcessMixin, "wake_up_if_sleeping_at"),
        (ProcessMixin, "get_current_node_id"),
        (StateMixin, "batch_get_state_version"),
        (ScheduleMixin, "apply_schedule_lock_with_times"),
    ):
        assert getattr(mixin, name).__isabstractmethod__ is True
