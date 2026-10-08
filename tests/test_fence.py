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

import logging

import pytest
from mock import MagicMock
from prometheus_client import REGISTRY

from bamboo_engine import fence, states
from bamboo_engine.config import Settings
from bamboo_engine.eri import Schedule, ScheduleType
from bamboo_engine.fence import ExecuteFence, ScheduleFence
from bamboo_engine.utils.host import get_hostname


def drop_count(kind, reason, enforced):
    labels = {"kind": kind, "reason": reason, "enforced": enforced, "hostname": get_hostname()}
    return REGISTRY.get_sample_value("engine_fence_drop_total", labels) or 0.0


def state_with_version(version):
    state = MagicMock()
    state.version = version
    return state


def appointed_state(name, retry=0, started_time=None):
    state = MagicMock()
    state.name = name
    state.version = "v2"
    state.retry = retry
    state.started_time = started_time
    return state


def schedule_with_times(times):
    return Schedule(
        id=2,
        type=ScheduleType.POLL,
        process_id=1,
        node_id="n1",
        finished=False,
        expired=False,
        version="v1",
        times=times,
    )


@pytest.fixture
def emit(monkeypatch):
    monkeypatch.setattr(Settings, "FENCE_EMIT_ENABLED", True)


def test_switches_default_off():
    assert Settings.FENCE_EMIT_ENABLED is False
    assert Settings.FENCE_ENFORCE is False
    assert fence.emit_enabled() is False
    assert fence.enforce_enabled() is False


def test_token_to_dict():
    assert ExecuteFence("n1", "v1").to_dict() == {"from_node": "n1", "from_version": "v1"}
    assert ExecuteFence("n1", None).to_dict() == {"from_node": "n1", "from_version": None}
    assert ScheduleFence(3).to_dict() == {"schedule_times": 3}


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"fence": {"from_node": "n1", "from_version": "v1"}}, ExecuteFence("n1", "v1")),
        ({"fence": {"from_node": "n1", "from_version": None}}, ExecuteFence("n1", None)),
        ({"fence": {"from_node": "n1"}}, ExecuteFence("n1", None)),
        (None, None),
        ({}, None),
        ({"fence": "n1"}, None),
        ({"fence": {"from_node": "", "from_version": "v1"}}, None),
        ({"fence": {"from_node": 1, "from_version": "v1"}}, None),
        ({"fence": {"from_node": "n1", "from_version": 1}}, None),
        ({"fence": {"schedule_times": 1}}, None),
    ],
)
def test_read_execute_fence(headers, expected):
    assert fence.read_execute_fence(headers) == expected


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"fence": {"schedule_times": 0}}, ScheduleFence(0)),
        ({"fence": {"schedule_times": 5}}, ScheduleFence(5)),
        (None, None),
        ({"fence": {"schedule_times": True}}, None),
        ({"fence": {"schedule_times": -1}}, None),
        ({"fence": {"schedule_times": "1"}}, None),
        ({"fence": {"from_node": "n1", "from_version": "v1"}}, None),
    ],
)
def test_read_schedule_fence(headers, expected):
    assert fence.read_schedule_fence(headers) == expected


def test_dispatch_headers_strips_incoming_fence_when_emit_disabled():
    headers = {"k": "v", "fence": {"from_node": "n0", "from_version": "v0"}}

    assert fence.dispatch_headers(headers, ExecuteFence("n1", "v1")) == {"k": "v"}
    assert headers == {"k": "v", "fence": {"from_node": "n0", "from_version": "v0"}}


def test_dispatch_headers_returns_new_dict(emit):
    headers = {"k": "v"}

    outgoing = fence.dispatch_headers(headers)

    assert outgoing == {"k": "v"}
    assert outgoing is not headers
    assert fence.dispatch_headers(None) == {}


def test_dispatch_headers_replaces_fence_when_emit_enabled(emit):
    headers = {"k": "v", "fence": {"schedule_times": 1}}

    assert fence.dispatch_headers(headers, ExecuteFence("n1", None)) == {
        "k": "v",
        "fence": {"from_node": "n1", "from_version": None},
    }
    assert fence.dispatch_headers(headers, ScheduleFence(2)) == {"k": "v", "fence": {"schedule_times": 2}}
    assert fence.dispatch_headers(headers) == {"k": "v"}


def test_record_drop(caplog):
    before = drop_count("execute", "process_moved", "false")
    with caplog.at_level(logging.WARNING, logger="bamboo_engine"):
        fence.record_drop(kind="execute", reason="process_moved", enforced=False, process_id=1, node_id="n1")

    assert drop_count("execute", "process_moved", "false") == before + 1
    assert "[fence] execute message would be dropped, reason=process_moved, node_id=n1, process_id=1" in caplog.text

    before = drop_count("schedule", "schedule_times_mismatch", "true")
    with caplog.at_level(logging.WARNING, logger="bamboo_engine"):
        fence.record_drop(kind="schedule", reason="schedule_times_mismatch", enforced=True, schedule_id=2)

    assert drop_count("schedule", "schedule_times_mismatch", "true") == before + 1
    assert "[fence] schedule message dropped, reason=schedule_times_mismatch, schedule_id=2" in caplog.text


def test_claim_execute_success():
    runtime = MagicMock()
    runtime.get_state_or_none = MagicMock(return_value=state_with_version("v1"))
    runtime.wake_up_if_sleeping_at = MagicMock(return_value=True)

    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", "v1")) is None
    runtime.get_state_or_none.assert_called_once_with("n1")
    runtime.wake_up_if_sleeping_at.assert_called_once_with(1, "n1")
    runtime.wake_up.assert_not_called()


def test_claim_execute_without_state():
    runtime = MagicMock()
    runtime.get_state_or_none = MagicMock(return_value=None)
    runtime.wake_up_if_sleeping_at = MagicMock(return_value=True)

    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", None)) is None
    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", "v1")) == fence.REASON_VERSION_MISMATCH


def test_claim_execute_version_mismatch():
    runtime = MagicMock()
    runtime.get_state_or_none = MagicMock(return_value=state_with_version("v2"))

    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", "v1")) == fence.REASON_VERSION_MISMATCH
    runtime.wake_up_if_sleeping_at.assert_not_called()


def test_claim_execute_process_moved():
    runtime = MagicMock()
    runtime.get_state_or_none = MagicMock(return_value=state_with_version("v1"))
    runtime.wake_up_if_sleeping_at = MagicMock(return_value=False)

    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", "v1")) == fence.REASON_PROCESS_MOVED


@pytest.mark.parametrize("name", [states.SUSPENDED, states.READY])
def test_claim_execute_allows_first_arrival_after_appoint(name):
    runtime = MagicMock()
    runtime.get_state_or_none = MagicMock(return_value=appointed_state(name))
    runtime.wake_up_if_sleeping_at = MagicMock(return_value=True)

    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", None)) is None
    runtime.wake_up_if_sleeping_at.assert_called_once_with(1, "n1")


@pytest.mark.parametrize(
    "state, from_version",
    [
        (appointed_state(states.READY, retry=1), None),
        (appointed_state(states.SUSPENDED, started_time="t"), None),
        (appointed_state(states.RUNNING), None),
        (appointed_state(states.FINISHED), None),
        (appointed_state(states.SUSPENDED), "v1"),
    ],
)
def test_claim_execute_rejects_executed_or_retried_node(state, from_version):
    runtime = MagicMock()
    runtime.get_state_or_none = MagicMock(return_value=state)

    assert fence.claim_execute(runtime, 1, ExecuteFence("n1", from_version)) == fence.REASON_VERSION_MISMATCH
    runtime.wake_up_if_sleeping_at.assert_not_called()


def test_apply_schedule_lock_success():
    runtime = MagicMock()
    runtime.apply_schedule_lock_with_times = MagicMock(return_value=True)

    assert fence.apply_schedule_lock(runtime, 2, ScheduleFence(3)) is True
    runtime.apply_schedule_lock_with_times.assert_called_once_with(2, 3)
    runtime.get_schedule.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()


def test_apply_schedule_lock_busy():
    runtime = MagicMock()
    runtime.apply_schedule_lock_with_times = MagicMock(return_value=False)
    runtime.get_schedule = MagicMock(return_value=schedule_with_times(3))

    assert fence.apply_schedule_lock(runtime, 2, ScheduleFence(3)) is False
    runtime.get_schedule.assert_called_once_with(2)


def test_apply_schedule_lock_times_mismatch():
    runtime = MagicMock()
    runtime.apply_schedule_lock_with_times = MagicMock(return_value=False)
    runtime.get_schedule = MagicMock(return_value=schedule_with_times(4))

    assert fence.apply_schedule_lock(runtime, 2, ScheduleFence(3)) is None
    runtime.apply_schedule_lock.assert_not_called()
