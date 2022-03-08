# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bamboo_engine.eri.models import ExecuteInterruptEvent, ScheduleInterruptEvent

from pipeline.eri import signals


class EventMixin:
    def handle_execute_interrupt_event(self, event: ExecuteInterruptEvent):
        """
        execute 中断事件出现后的处理钩子
        """
        signals.execute_interrupt.send(sender=event, event=event)

    def handle_schedule_interrupt_event(self, event: ScheduleInterruptEvent):
        """
        schedule 中断事件出现后的处理钩子
        """
        signals.schedule_interrupt.send(sender=event, event=event)
