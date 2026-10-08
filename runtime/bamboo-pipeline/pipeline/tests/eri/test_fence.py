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

from django.test import TransactionTestCase

from bamboo_engine import fence, states
from bamboo_engine.eri import ScheduleType
from bamboo_engine.fence import ExecuteFence, ScheduleFence
from bamboo_engine.utils.string import unique_id

from pipeline.eri.models import Process, Schedule, State
from pipeline.eri.runtime import BambooDjangoRuntime


class FenceGateTestCase(TransactionTestCase):
    def setUp(self):
        self.runtime = BambooDjangoRuntime()
        self.node_id = unique_id("n")
        self.process = Process.objects.create(priority=1, queue="queue", current_node_id=self.node_id)

    def test_runtime_implements_fence_interfaces(self):
        # ERI 的 mixin 不是 ABCMeta，漏实现不会在实例化时报错，调用时会静默返回 None 并被门禁当成抢占失败
        for name in (
            "wake_up_if_sleeping_at",
            "get_current_node_id",
            "batch_get_state_version",
            "apply_schedule_lock_with_times",
        ):
            self.assertFalse(getattr(getattr(BambooDjangoRuntime, name), "__isabstractmethod__", False), name)

    def test_claim_execute_only_once(self):
        token = ExecuteFence(self.node_id, None)

        self.assertIsNone(fence.claim_execute(self.runtime, self.process.id, token))
        self.assertEqual(fence.claim_execute(self.runtime, self.process.id, token), fence.REASON_PROCESS_MOVED)
        self.process.refresh_from_db()
        self.assertFalse(self.process.asleep)

    def test_claim_execute_rejects_reentered_node(self):
        State.objects.create(node_id=self.node_id, root_id="r", parent_id="r", name=states.RUNNING, version="v2")

        self.assertEqual(
            fence.claim_execute(self.runtime, self.process.id, ExecuteFence(self.node_id, "v1")),
            fence.REASON_VERSION_MISMATCH,
        )
        self.process.refresh_from_db()
        self.assertTrue(self.process.asleep)
        self.assertIsNone(fence.claim_execute(self.runtime, self.process.id, ExecuteFence(self.node_id, "v2")))

    def test_claim_execute_allows_first_arrival_after_appoint(self):
        self.runtime.set_state(node_id=self.node_id, to_state=states.SUSPENDED)

        self.assertIsNone(fence.claim_execute(self.runtime, self.process.id, ExecuteFence(self.node_id, None)))

    def test_claim_execute_allows_first_arrival_after_appoint_and_resume(self):
        self.runtime.set_state(node_id=self.node_id, to_state=states.SUSPENDED)
        self.runtime.set_state(node_id=self.node_id, to_state=states.READY)

        self.assertIsNone(fence.claim_execute(self.runtime, self.process.id, ExecuteFence(self.node_id, None)))

    def test_claim_execute_rejects_first_arrival_token_after_execution_or_retry(self):
        token = ExecuteFence(self.node_id, None)
        self.runtime.set_state(node_id=self.node_id, to_state=states.RUNNING, set_started_time=True)
        self.runtime.set_state(node_id=self.node_id, to_state=states.SUSPENDED)

        self.assertEqual(fence.claim_execute(self.runtime, self.process.id, token), fence.REASON_VERSION_MISMATCH)

        State.objects.filter(node_id=self.node_id).update(name=states.READY, started_time=None, retry=1)

        self.assertEqual(fence.claim_execute(self.runtime, self.process.id, token), fence.REASON_VERSION_MISMATCH)
        self.process.refresh_from_db()
        self.assertTrue(self.process.asleep)

    def test_apply_schedule_lock(self):
        schedule = Schedule.objects.create(
            process_id=self.process.id,
            node_id=self.node_id,
            version="v1",
            type=ScheduleType.POLL.value,
            schedule_times=1,
        )

        self.assertIsNone(fence.apply_schedule_lock(self.runtime, schedule.id, ScheduleFence(0)))
        self.assertTrue(fence.apply_schedule_lock(self.runtime, schedule.id, ScheduleFence(1)))
        self.assertFalse(fence.apply_schedule_lock(self.runtime, schedule.id, ScheduleFence(1)))

        self.runtime.add_schedule_times(schedule.id)
        self.runtime.release_schedule_lock(schedule.id)

        self.assertIsNone(fence.apply_schedule_lock(self.runtime, schedule.id, ScheduleFence(1)))
        self.assertTrue(fence.apply_schedule_lock(self.runtime, schedule.id, ScheduleFence(2)))
