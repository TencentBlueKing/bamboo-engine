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

import mock
import pytest
from mock import MagicMock, call
from prometheus_client import REGISTRY

from bamboo_engine import states
from bamboo_engine.config import Settings
from bamboo_engine.engine import Engine
from bamboo_engine.eri import (
    DispatchProcess,
    NodeType,
    ProcessInfo,
    Schedule,
    ScheduleType,
    ServiceActivity,
    State,
)
from bamboo_engine.eri.models.interrupt import ScheduleInterruptPoint
from bamboo_engine.handler import ExecuteResult, ScheduleResult
from bamboo_engine.interrupt import (
    ExecuteInterrupter,
    ExecuteInterruptPoint,
    ExecuteKeyPoint,
    ScheduleInterrupter,
    ScheduleKeyPoint,
)
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


# 调度入口


@pytest.fixture
def node():
    return ServiceActivity(
        id="nid",
        type=NodeType.ServiceActivity,
        target_flows=["f1"],
        target_nodes=["t1"],
        targets={"f1": "t1"},
        root_pipeline_id="root",
        parent_pipeline_id="root",
        code="",
        version="",
        error_ignorable=False,
    )


POLL_AGAIN = ScheduleResult(has_next_schedule=True, schedule_after=5, schedule_done=False, next_node_id=None)


def make_schedule(times=0, schedule_type=ScheduleType.POLL):
    return Schedule(
        id=2,
        type=schedule_type,
        process_id=1,
        node_id="nid",
        finished=False,
        expired=False,
        version="v",
        times=times,
    )


def schedule_runtime(pi, node, schedule, locked=True):
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.get_state = MagicMock(return_value=make_state("nid", "v"))
    runtime.get_schedule = MagicMock(return_value=schedule)
    runtime.get_node = MagicMock(return_value=node)
    runtime.apply_schedule_lock = MagicMock(return_value=True)
    runtime.apply_schedule_lock_with_times = MagicMock(return_value=locked)
    return runtime


def run_schedule(runtime, pi, headers, schedule_result, recover_point=None):
    interrupter = ScheduleInterrupter(
        runtime=MagicMock(),
        process_id=pi.process_id,
        current_node_id="nid",
        schedule_id=2,
        callback_data_id=None,
        check_point=ScheduleInterruptPoint(name=ScheduleKeyPoint.ENTRY),
        recover_point=recover_point,
        headers=headers,
    )
    handler = MagicMock()
    handler.schedule = MagicMock(return_value=schedule_result)
    with mock.patch("bamboo_engine.engine.HandlerFactory.get_handler", MagicMock(return_value=handler)):
        Engine(runtime=runtime).schedule(pi.process_id, "nid", 2, interrupter, headers)
    return handler


def test_schedule_without_fence_uses_plain_lock(pi, node):
    runtime = schedule_runtime(pi, node, make_schedule())

    handler = run_schedule(runtime, pi, {"k": "v"}, POLL_AGAIN)

    runtime.apply_schedule_lock.assert_called_once_with(2)
    runtime.apply_schedule_lock_with_times.assert_not_called()
    handler.schedule.assert_called_once()


def test_schedule_locks_with_times(pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=3))

    handler = run_schedule(runtime, pi, {"fence": {"schedule_times": 3}}, POLL_AGAIN)

    runtime.apply_schedule_lock_with_times.assert_called_once_with(2, 3)
    runtime.apply_schedule_lock.assert_not_called()
    handler.schedule.assert_called_once()


def test_schedule_lock_busy_keeps_existing_handling(enforce, pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=3), locked=False)
    before = drop_count("schedule", "schedule_times_mismatch", "true")

    handler = run_schedule(runtime, pi, {"fence": {"schedule_times": 3}}, POLL_AGAIN)

    assert drop_count("schedule", "schedule_times_mismatch", "true") == before
    handler.schedule.assert_not_called()
    runtime.set_next_schedule.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()


@mock.patch("bamboo_engine.engine.random.randint", return_value=5)
def test_schedule_lock_busy_retry_keeps_fence(randint, pi, node):
    schedule = make_schedule(times=3, schedule_type=ScheduleType.MULTIPLE_CALLBACK)
    runtime = schedule_runtime(pi, node, schedule, locked=False)

    run_schedule(runtime, pi, {"k": "v", "fence": {"schedule_times": 3}}, POLL_AGAIN)

    runtime.set_next_schedule.assert_called_once_with(
        process_id=1,
        node_id="nid",
        schedule_id=2,
        callback_data_id=None,
        schedule_after=5,
        headers={"k": "v", "fence": {"schedule_times": 3}},
    )


def test_schedule_drops_times_mismatch_when_enforced(enforce, pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=4), locked=False)
    before = drop_count("schedule", "schedule_times_mismatch", "true")

    handler = run_schedule(runtime, pi, {"fence": {"schedule_times": 3}}, POLL_AGAIN)

    assert drop_count("schedule", "schedule_times_mismatch", "true") == before + 1
    runtime.apply_schedule_lock.assert_not_called()
    runtime.beat.assert_not_called()
    runtime.set_next_schedule.assert_not_called()
    handler.schedule.assert_not_called()


def test_schedule_only_records_times_mismatch_when_not_enforced(pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=4), locked=False)
    before = drop_count("schedule", "schedule_times_mismatch", "false")

    handler = run_schedule(runtime, pi, {"fence": {"schedule_times": 3}}, POLL_AGAIN)

    assert drop_count("schedule", "schedule_times_mismatch", "false") == before + 1
    runtime.apply_schedule_lock.assert_called_once_with(2)
    handler.schedule.assert_called_once()


def test_schedule_recovery_skips_fence(enforce, pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=4), locked=False)
    recover_point = ScheduleInterruptPoint(name=ScheduleKeyPoint.APPLY_LOCK_DONE, version=1, lock_get=True)

    handler = run_schedule(runtime, pi, {"fence": {"schedule_times": 3}}, POLL_AGAIN, recover_point=recover_point)

    runtime.apply_schedule_lock_with_times.assert_not_called()
    runtime.apply_schedule_lock.assert_not_called()
    handler.schedule.assert_called_once()


# 派发点附带令牌

SCHEDULE_DONE = ScheduleResult(has_next_schedule=False, schedule_after=-1, schedule_done=True, next_node_id="nid2")


@pytest.fixture
def emit(monkeypatch):
    monkeypatch.setattr(Settings, "FENCE_EMIT_ENABLED", True)


def test_schedule_done_dispatches_execute_fence(emit, pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=3))

    run_schedule(runtime, pi, {"k": "v", "fence": {"schedule_times": 3}}, SCHEDULE_DONE)

    runtime.execute.assert_called_once_with(
        process_id=1,
        node_id="nid2",
        root_pipeline_id="root",
        parent_pipeline_id="root",
        headers={"k": "v", "fence": {"from_node": "nid", "from_version": "v"}},
    )


def test_poll_continuation_dispatches_reread_times(emit, pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=3))
    runtime.get_schedule = MagicMock(side_effect=[make_schedule(times=3), make_schedule(times=4)])

    run_schedule(runtime, pi, {"k": "v", "fence": {"schedule_times": 3}}, POLL_AGAIN)

    runtime.set_next_schedule.assert_called_once_with(
        process_id=1,
        node_id="nid",
        schedule_id=2,
        schedule_after=5,
        headers={"k": "v", "fence": {"schedule_times": 4}},
    )


def test_schedule_dispatch_strips_fence_when_emit_disabled(pi, node):
    runtime = schedule_runtime(pi, node, make_schedule(times=3))

    run_schedule(runtime, pi, {"k": "v", "fence": {"schedule_times": 3}}, POLL_AGAIN)

    runtime.set_next_schedule.assert_called_once_with(
        process_id=1, node_id="nid", schedule_id=2, schedule_after=5, headers={"k": "v"}
    )
    runtime.get_schedule.assert_called_once_with(2)


def test_parent_wake_dispatches_parent_fence(emit, pi):
    runtime = arrived_runtime(pi)
    runtime.child_process_finish = MagicMock(return_value=True)
    runtime.get_current_node_id = MagicMock(return_value="pg")
    runtime.get_state_or_none = MagicMock(side_effect=lambda node_id: make_state(node_id, node_id + "_v"))

    run_execute(runtime, pi, {"k": "v", "fence": {"from_node": "n0", "from_version": "n0_v"}})

    runtime.get_current_node_id.assert_called_once_with(9)
    runtime.execute.assert_called_once_with(
        process_id=9,
        node_id="nid",
        root_pipeline_id="root",
        parent_pipeline_id="root",
        headers={"k": "v", "fence": {"from_node": "pg", "from_version": "pg_v"}},
    )


def test_parent_wake_strips_fence_when_emit_disabled(pi):
    runtime = arrived_runtime(pi)
    runtime.child_process_finish = MagicMock(return_value=True)

    run_execute(runtime, pi, {"k": "v", "fence": FENCE})

    runtime.get_current_node_id.assert_not_called()
    runtime.execute.assert_called_once_with(
        process_id=9, node_id="nid", root_pipeline_id="root", parent_pipeline_id="root", headers={"k": "v"}
    )


def test_parent_wake_dispatches_without_fence_when_read_fails(emit, pi):
    runtime = arrived_runtime(pi)
    runtime.child_process_finish = MagicMock(return_value=True)
    runtime.get_current_node_id = MagicMock(side_effect=RuntimeError("db error"))

    run_execute(runtime, pi, {"k": "v", "fence": FENCE})

    runtime.get_current_node_id.assert_called_once_with(9)
    runtime.get_state_or_none.assert_called_once_with("n0")
    runtime.execute.assert_called_once_with(
        process_id=9, node_id="nid", root_pipeline_id="root", parent_pipeline_id="root", headers={"k": "v"}
    )


def fenced_state_only(node_id):
    return make_state("n0", "v0") if node_id == "n0" else None


def loop_runtime(pi, node):
    """进程带着令牌抢占成功，然后执行 node"""
    runtime = MagicMock()
    runtime.get_process_info = MagicMock(return_value=pi)
    runtime.batch_get_state_name = MagicMock(return_value={"root": states.RUNNING})
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state_or_none = MagicMock(side_effect=fenced_state_only)
    runtime.wake_up_if_sleeping_at = MagicMock(return_value=True)
    runtime.set_state = MagicMock(return_value="v")
    runtime.set_schedule = MagicMock(return_value=make_schedule(times=0))
    return runtime


def run_node(runtime, pi, headers, execute_result):
    handler = MagicMock()
    handler.execute = MagicMock(return_value=execute_result)
    with mock.patch("bamboo_engine.engine.HandlerFactory.get_handler", MagicMock(return_value=handler)):
        run_execute(runtime, pi, headers)


def test_first_poll_dispatches_schedule_fence(emit, pi, node):
    runtime = loop_runtime(pi, node)
    result = ExecuteResult(
        should_sleep=True,
        schedule_ready=True,
        schedule_type=ScheduleType.POLL,
        schedule_after=5,
        dispatch_processes=[],
        next_node_id=None,
        should_die=False,
    )

    run_node(runtime, pi, {"k": "v", "fence": FENCE}, result)

    runtime.wake_up.assert_not_called()
    runtime.schedule.assert_called_once_with(
        process_id=1, node_id="nid", schedule_id=2, headers={"k": "v", "fence": {"schedule_times": 0}}
    )


def fork_result():
    return ExecuteResult(
        should_sleep=True,
        schedule_ready=False,
        schedule_type=None,
        schedule_after=-1,
        dispatch_processes=[DispatchProcess(process_id=3, node_id="n3"), DispatchProcess(process_id=4, node_id="n4")],
        next_node_id=None,
        should_die=False,
    )


def test_fork_dispatches_children_fences(emit, pi, node):
    runtime = loop_runtime(pi, node)
    runtime.batch_get_state_version = MagicMock(return_value={"n3": "v3"})

    run_node(runtime, pi, {"k": "v", "fence": FENCE}, fork_result())

    runtime.batch_get_state_version.assert_called_once_with(["n3", "n4"])
    runtime.execute.assert_has_calls(
        [
            call(
                process_id=3,
                node_id="n3",
                root_pipeline_id="root",
                parent_pipeline_id="root",
                headers={"k": "v", "fence": {"from_node": "n3", "from_version": "v3"}},
            ),
            call(
                process_id=4,
                node_id="n4",
                root_pipeline_id="root",
                parent_pipeline_id="root",
                headers={"k": "v", "fence": {"from_node": "n4", "from_version": None}},
            ),
        ]
    )


def test_fork_strips_fence_when_emit_disabled(pi, node):
    runtime = loop_runtime(pi, node)

    run_node(runtime, pi, {"k": "v", "fence": FENCE}, fork_result())

    runtime.batch_get_state_version.assert_not_called()
    runtime.execute.assert_has_calls(
        [
            call(process_id=3, node_id="n3", root_pipeline_id="root", parent_pipeline_id="root", headers={"k": "v"}),
            call(process_id=4, node_id="n4", root_pipeline_id="root", parent_pipeline_id="root", headers={"k": "v"}),
        ]
    )


# 人工操作


def test_skip_conditional_parallel_gateway_refreshes_version_before_dispatch(pi):
    node = MagicMock()
    node.type = NodeType.ConditionalParallelGateway
    node.targets = {"f1": "n3"}
    state = MagicMock()
    state.node_id = "cpg"
    state.name = states.FAILED
    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=pi)
    runtime.fork = MagicMock(return_value=[DispatchProcess(process_id=3, node_id="n3")])

    Engine(runtime=runtime).skip_conditional_parallel_gateway("cpg", ["f1"], "cg")

    names = [name for name, _, _ in runtime.method_calls]
    assert names.index("set_state") < names.index("execute")
    runtime.execute.assert_called_once_with(
        process_id=3, node_id="n3", root_pipeline_id="root", parent_pipeline_id="root"
    )
