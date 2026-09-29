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

# 引擎门禁：派发 execute/schedule 消息时附带令牌，入口据此识别并丢弃过期或重复的消息

import logging
from typing import Optional

from . import states
from .config import Settings
from .metrics import ENGINE_FENCE_DROP
from .utils.host import get_hostname

logger = logging.getLogger("bamboo_engine")

FENCE_HEADER = "fence"

KIND_EXECUTE = "execute"
KIND_SCHEDULE = "schedule"

REASON_VERSION_MISMATCH = "version_mismatch"
REASON_PROCESS_MOVED = "process_moved"
REASON_SCHEDULE_TIMES_MISMATCH = "schedule_times_mismatch"


class ExecuteFence:
    """期望进程仍休眠在 from_node，且 from_node 的状态版本仍为 from_version（没有状态时为 None）"""

    def __init__(self, from_node: str, from_version: Optional[str]):
        self.from_node = from_node
        self.from_version = from_version

    def to_dict(self) -> dict:
        return {"from_node": self.from_node, "from_version": self.from_version}

    def __eq__(self, other):
        return isinstance(other, ExecuteFence) and self.to_dict() == other.to_dict()

    def __repr__(self):
        return "ExecuteFence(from_node={!r}, from_version={!r})".format(self.from_node, self.from_version)


class ScheduleFence:
    """期望调度对象的调度次数仍为 schedule_times"""

    def __init__(self, schedule_times: int):
        self.schedule_times = schedule_times

    def to_dict(self) -> dict:
        return {"schedule_times": self.schedule_times}

    def __eq__(self, other):
        return isinstance(other, ScheduleFence) and self.schedule_times == other.schedule_times

    def __repr__(self):
        return "ScheduleFence(schedule_times={!r})".format(self.schedule_times)


def emit_enabled() -> bool:
    return bool(Settings.FENCE_EMIT_ENABLED)


def enforce_enabled() -> bool:
    return bool(Settings.FENCE_ENFORCE)


def _raw_fence(headers: Optional[dict]) -> Optional[dict]:
    raw = (headers or {}).get(FENCE_HEADER)
    return raw if isinstance(raw, dict) else None


def read_execute_fence(headers: Optional[dict]) -> Optional[ExecuteFence]:
    """格式不对的令牌按没有令牌处理，消息走原有逻辑"""
    raw = _raw_fence(headers)
    if raw is None:
        return None
    from_node = raw.get("from_node")
    from_version = raw.get("from_version")
    if not isinstance(from_node, str) or not from_node:
        return None
    if from_version is not None and not isinstance(from_version, str):
        return None
    return ExecuteFence(from_node, from_version)


def read_schedule_fence(headers: Optional[dict]) -> Optional[ScheduleFence]:
    """格式不对的令牌按没有令牌处理，消息走原有逻辑"""
    raw = _raw_fence(headers)
    if raw is None:
        return None
    schedule_times = raw.get("schedule_times")
    if isinstance(schedule_times, bool) or not isinstance(schedule_times, int) or schedule_times < 0:
        return None
    return ScheduleFence(schedule_times)


def dispatch_headers(headers: Optional[dict], token=None) -> dict:
    """
    生成下一条消息的 headers。入站令牌只对当前这条消息有效，无论是否附带新令牌都要去掉，
    否则父进程、子进程会继承一个与自己无关的令牌而被误丢。运行时会原地改写 headers，所以总是返回新字典。
    """
    outgoing = {key: value for key, value in (headers or {}).items() if key != FENCE_HEADER}
    if token is not None and emit_enabled():
        outgoing[FENCE_HEADER] = token.to_dict()
    return outgoing


def record_drop(kind: str, reason: str, enforced: bool, **context):
    ENGINE_FENCE_DROP.labels(
        kind=kind, reason=reason, enforced="true" if enforced else "false", hostname=get_hostname()
    ).inc()
    logger.warning(
        "[fence] %s message %s, reason=%s, %s",
        kind,
        "dropped" if enforced else "would be dropped",
        reason,
        ", ".join("{}={}".format(key, context[key]) for key in sorted(context)),
    )


def claim_execute(runtime, process_id: int, token: ExecuteFence) -> Optional[str]:
    """
    按令牌抢占进程：先比对 from_node 的状态版本，排除循环流程里"又回到同一节点休眠"的情况，
    再用条件更新唤醒。成功返回 None；失败返回丢弃原因，且不改动任何数据。
    """
    state = runtime.get_state_or_none(token.from_node)
    if not _version_matches(state, token.from_version):
        return REASON_VERSION_MISMATCH
    if not runtime.wake_up_if_sleeping_at(process_id, token.from_node):
        return REASON_PROCESS_MOVED
    return None


def _version_matches(state, from_version: Optional[str]) -> bool:
    """
    令牌版本为空表示派发时节点还没有状态（子进程首次到达分支首节点）。抢占前用户预约暂停（及随后继续）会新建状态和版本，
    但节点从未执行过，不能因此丢弃启动消息；执行过的节点有 started_time，重试会把 retry 加 1，都不在此列。
    """
    if (state.version if state else None) == from_version:
        return True
    return (
        from_version is None
        and state.name in (states.SUSPENDED, states.READY)
        and state.retry == 0
        and state.started_time is None
    )


def apply_schedule_lock(runtime, schedule_id, token: ScheduleFence) -> Optional[bool]:
    """按令牌获取调度锁：True 为拿到锁，False 为锁被占用（沿用原有处理），None 为调度次数不符（应丢弃）"""
    if runtime.apply_schedule_lock_with_times(schedule_id, token.schedule_times):
        return True
    if runtime.get_schedule(schedule_id).times == token.schedule_times:
        return False
    return None
