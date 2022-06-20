# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from mock import MagicMock
from bamboo_engine.eri.models.interrupt import ScheduleInterruptPoint

from bamboo_engine.interrupt import ScheduleInterrupter, InterruptException


@pytest.fixture
def interrupter():
    runtime = MagicMock()
    runtime.interrupt_errors = MagicMock(return_value=(ValueError,))
    return ScheduleInterrupter(
        runtime=runtime,
        current_node_id="node1",
        process_id=1,
        schedule_id=2,
        callback_data_id=3,
        check_point=ScheduleInterruptPoint(name="s1"),
        recover_point=None,
        headers={},
    )


def test_call(interrupter):
    try:
        with interrupter():
            raise Exception
    except Exception:
        interrupter.runtime.schedule.assert_not_called()
    else:
        assert False

    try:
        with interrupter():
            raise ValueError()
    except InterruptException:
        interrupter.runtime.schedule.assert_called_once_with(
            process_id=interrupter.process_id,
            node_id=interrupter.current_node_id,
            schedule_id=interrupter.schedule_id,
            callback_data_id=interrupter.callback_data_id,
            recover_point=interrupter.latest_recover_point,
            headers=interrupter.headers,
        )
        interrupter.runtime.handle_schedule_interrupt_event.assert_called_once()
    else:
        assert False
