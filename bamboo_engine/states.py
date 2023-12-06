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


# 引擎内部状态及状态相关数据定义模块


from enum import Enum

from .utils.collections import ConstantDict


class StateType(Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"
    BLOCKED = "BLOCKED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    REVOKED = "REVOKED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLL_BACK_SUCCESS = "ROLL_BACK_SUCCESS"
    ROLL_BACK_FAILED = "ROLL_BACK_FAILED"


CREATED = StateType.CREATED.value
READY = StateType.READY.value
RUNNING = StateType.RUNNING.value
SUSPENDED = StateType.SUSPENDED.value
BLOCKED = StateType.BLOCKED.value
FINISHED = StateType.FINISHED.value
FAILED = StateType.FAILED.value
REVOKED = StateType.REVOKED.value
ROLLING_BACK = StateType.ROLLING_BACK.value
ROLL_BACK_SUCCESS = StateType.ROLL_BACK_SUCCESS.value
ROLL_BACK_FAILED = StateType.ROLL_BACK_FAILED.value

ALL_STATES = frozenset([READY, RUNNING, SUSPENDED, BLOCKED, FINISHED, FAILED, REVOKED, ROLLING_BACK])

ARCHIVED_STATES = frozenset([FINISHED, FAILED, REVOKED])
SLEEP_STATES = frozenset([SUSPENDED, REVOKED])
CHILDREN_IGNORE_STATES = frozenset([BLOCKED])

INVERTED_TRANSITION = ConstantDict({RUNNING: frozenset([READY, FINISHED])})

TRANSITION = ConstantDict(
    {
        READY: frozenset([RUNNING, SUSPENDED]),
        RUNNING: frozenset([FINISHED, FAILED, REVOKED, SUSPENDED, ROLLING_BACK]),
        SUSPENDED: frozenset([READY, REVOKED, RUNNING, ROLLING_BACK]),
        BLOCKED: frozenset([]),
        FINISHED: frozenset([RUNNING, FAILED, ROLLING_BACK]),
        FAILED: frozenset([READY, FINISHED]),
        REVOKED: frozenset([]),
        ROLLING_BACK: frozenset([ROLL_BACK_SUCCESS, ROLL_BACK_FAILED]),
        ROLL_BACK_SUCCESS: frozenset([READY, FINISHED]),
        ROLL_BACK_FAILED: frozenset([READY, FINISHED, ROLLING_BACK]),
    }
)


def can_transit(from_state, to_state):
    if from_state in TRANSITION:
        if to_state in TRANSITION[from_state]:
            return True
    return False
