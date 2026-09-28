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

import pytest
from mock import MagicMock
from prometheus_client import REGISTRY

from bamboo_engine import states
from bamboo_engine.config import Settings
from bamboo_engine.engine import Engine
from bamboo_engine.eri import ProcessInfo, State
from bamboo_engine.interrupt import ExecuteInterrupter, ExecuteInterruptPoint, ExecuteKeyPoint
from bamboo_engine.utils.host import get_hostname

FENCE = {"from_node": "n0", "from_version": "v0"}


def drop_count(kind, reason, enforced):
    labels = {"kind": kind, "reason": reason, "enforced": enforced, "hostname": get_hostname()}
    return REGISTRY.get_sample_value("engine_fence_drop_total", labels) or 0.0


def make_state(node_id, version):
    return State(
        node_id=node_id,
        root_id="root",
        parent_id="root",
        name=states.RUNNING,
        version=version,
        loop=1,
        inner_loop=1,
        retry=0,
        skip=False,
        error_ignored=False,
        created_time=None,
        started_time=None,
        archived_time=None,
    )


@pytest.fixture
def pi():
    return ProcessInfo(process_id=1, destination_id="d", root_pipeline_id="root", pipeline_stack=["root"], parent_id=9)


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(Settings, "FENCE_ENFORCE", True)


def execute_interrupter(recover_point=None):
    return ExecuteInterrupter(
        runtime=MagicMock(),
        current_node_id="nid",
        process_id=1,
        parent_pipeline_id="root",
        root_pipeline_id="root",
        check_point=ExecuteInterruptPoint(name=ExecuteKeyPoint.ENTRY),
        recover_point=recover_point,
        headers={},
    )


def arrived_runtime(pi, state_version="v0", claimed=True):
    """进程一进入推进循环就到达终点，且父进程还不能被唤醒"""
    pi.destination_id = "nid"
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.child_process_finish = MagicMock(return_value=False)
    runtime.get_state_or_none = MagicMock(return_value=make_state("n0", state_version))
    runtime.wake_up_if_sleeping_at = MagicMock(return_value=claimed)
    return runtime


def run_execute(runtime, pi, headers, recover_point=None):
    Engine(runtime=runtime).execute(pi.process_id, "nid", "root", "root", execute_interrupter(recover_point), headers)


# 执行入口


def test_execute_without_fence_wakes_up_unconditionally(pi):
    runtime = arrived_runtime(pi)

    run_execute(runtime, pi, {"k": "v"})

    runtime.wake_up.assert_called_once_with(1)
    runtime.wake_up_if_sleeping_at.assert_not_called()
    runtime.get_state_or_none.assert_not_called()


def test_execute_claims_with_fence(pi):
    runtime = arrived_runtime(pi)

    run_execute(runtime, pi, {"fence": FENCE})

    runtime.get_state_or_none.assert_called_once_with("n0")
    runtime.wake_up_if_sleeping_at.assert_called_once_with(1, "n0")
    runtime.wake_up.assert_not_called()
    runtime.beat.assert_called_once_with(1)


@pytest.mark.parametrize(
    "state_version, claimed, reason",
    [("v1", True, "version_mismatch"), ("v0", False, "process_moved")],
)
def test_execute_drops_stale_message_when_enforced(enforce, pi, state_version, claimed, reason):
    runtime = arrived_runtime(pi, state_version=state_version, claimed=claimed)
    before = drop_count("execute", reason, "true")

    run_execute(runtime, pi, {"fence": FENCE})

    assert drop_count("execute", reason, "true") == before + 1
    runtime.wake_up.assert_not_called()
    runtime.beat.assert_not_called()
    runtime.child_process_finish.assert_not_called()


@pytest.mark.parametrize(
    "state_version, claimed, reason",
    [("v1", True, "version_mismatch"), ("v0", False, "process_moved")],
)
def test_execute_only_records_stale_message_when_not_enforced(pi, state_version, claimed, reason):
    runtime = arrived_runtime(pi, state_version=state_version, claimed=claimed)
    before = drop_count("execute", reason, "false")

    run_execute(runtime, pi, {"fence": FENCE})

    assert drop_count("execute", reason, "false") == before + 1
    runtime.wake_up.assert_called_once_with(1)
    runtime.beat.assert_called_once_with(1)


def test_execute_recovery_skips_fence(enforce, pi):
    runtime = arrived_runtime(pi, claimed=False)
    recover_point = ExecuteInterruptPoint(name=ExecuteKeyPoint.START_PUSH_NODE, version=1)

    run_execute(runtime, pi, {"fence": FENCE}, recover_point=recover_point)

    runtime.wake_up_if_sleeping_at.assert_not_called()
    runtime.wake_up.assert_called_once_with(1)
    runtime.beat.assert_called_once_with(1)


def test_execute_recovery_at_entry_still_checks_fence(enforce, pi):
    runtime = arrived_runtime(pi, claimed=False)

    run_execute(runtime, pi, {"fence": FENCE}, recover_point=ExecuteInterruptPoint(name=ExecuteKeyPoint.ENTRY))

    runtime.wake_up_if_sleeping_at.assert_called_once_with(1, "n0")
    runtime.wake_up.assert_not_called()
    runtime.beat.assert_not_called()
