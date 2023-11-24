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


import datetime
import re
from typing import Any, Callable, Dict, Optional

import isodate
from pipeline.contrib.node_timer_event.constants import TimerType
from pipeline.contrib.node_timer_event.types import TimeDefined

TIME_CYCLE_DEFINED_PATTERN = re.compile(r"(^R\d+)/")


def handle_result(timestamp: float, repetitions: int = 1, *args, **kwargs) -> TimeDefined:
    return {"timestamp": timestamp, "repetitions": repetitions}


def handle_timedate(defined: str, start: Optional[datetime.datetime] = None, *args, **kwargs) -> TimeDefined:
    return handle_result(timestamp=isodate.parse_datetime(defined).timestamp())


def handle_time_duration(defined: str, start: Optional[datetime.datetime] = None, *args, **kwargs) -> TimeDefined:
    start = start or datetime.datetime.now()
    return handle_result(timestamp=(start + isodate.parse_duration(defined)).timestamp())


def handle_time_cycle(defined: str, start: Optional[datetime.datetime] = None, *args, **kwargs) -> TimeDefined:
    repeat_match = TIME_CYCLE_DEFINED_PATTERN.match(defined)
    if repeat_match:
        repetitions: int = int(repeat_match.group(1)[1:])
        duration_string = TIME_CYCLE_DEFINED_PATTERN.sub("", defined)
    else:
        repetitions: int = 1
        duration_string = defined

    return handle_result(timestamp=handle_time_duration(duration_string, start)["timestamp"], repetitions=repetitions)


TIMER_TYPE_ROUTES: Dict[str, Callable[[str, Optional[datetime.datetime], Any, Any], TimeDefined]] = {
    TimerType.TIME_DURATION.value: handle_time_duration,
    TimerType.TIME_CYCLE.value: handle_time_cycle,
    TimerType.TIME_DATE.value: handle_timedate,
}


def parse_timer_defined(
    timer_type: str, defined: str, start: Optional[datetime.datetime] = None, *args, **kwargs
) -> TimeDefined:
    if timer_type not in TIMER_TYPE_ROUTES:
        raise ValueError(f"Unsupported timer_type -> {timer_type}")

    return TIMER_TYPE_ROUTES[timer_type](defined, start, *args, **kwargs)
