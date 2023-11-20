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

from enum import Enum


class TimerType(Enum):

    # 时间日期（Time date）ISO 8601 组合日期和时间格式
    # 2019-10-01T12:00:00Z - UTC 时间
    # 2019-10-02T08:09:40+02:00 - UTC 加上两小时时区偏移
    # 2019-10-02T08:09:40+02:00[Europe/Berlin] - UTC 加上柏林两小时时区偏移
    TIME_DATE = "time_date"

    # 时间周期（Time cycle）ISO 8601 重复间隔格式，包含重复次数模式：R(n) 及持续时间模式：P(n)Y(n)M(n)DT(n)H(n)M(n)S
    # R5/PT10S - 每10秒一次，最多五次
    # R/P1D - 每天，无限
    TIME_CYCLE = "time_cycle"

    # 持续时间（Time duration）ISO 8601 持续时间格式，模式：P(n)Y(n)M(n)DT(n)H(n)M(n)S
    # PT15S - 15 秒
    # PT1H30M - 1 小时 30 分钟
    # P14D - 14 天
    # P14DT1H30M - 14 天 1 小时 30 分钟
    TIME_DURATION = "time_duration"
