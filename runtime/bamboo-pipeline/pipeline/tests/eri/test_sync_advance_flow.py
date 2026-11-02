# -*- coding: utf-8 -*-
"""
Drive the real engine and Django runtime through synchronous continuation checkpoints.
Messages are queued in-process and handed to the celery task functions, so no broker is needed;
row locks and transaction semantics are only meaningful on the MySQL used by CI.
"""

from collections import Counter, deque

import mock
from django.db import OperationalError
from django.test import TransactionTestCase

from bamboo_engine import api, states
from bamboo_engine.builder import EmptyEndEvent, EmptyStartEvent, ServiceActivity, build_tree
from bamboo_engine.config import Settings
from pipeline.component_framework.component import Component
from pipeline.component_framework.constants import LEGACY_PLUGINS_VERSION
from pipeline.component_framework.library import ComponentLibrary
from pipeline.core.flow.activity import Service
from pipeline.eri.celery import tasks
from pipeline.eri.models import Process, State, SyncAdvanceCheckpoint
from pipeline.eri.runtime import BambooDjangoRuntime

# Register the probe component per test instead of at import time (no component table writes).
__register_ignore__ = True

CODE = "sync_advance_flow_probe"
MAX_MESSAGES = 50


class FlowControl(object):
    actions = {}
    executed = Counter()


class SyncProbeService(Service):
    __need_schedule__ = False

    def execute(self, data, parent_data):
        FlowControl.executed[self.id] += 1
        action = FlowControl.actions.pop(self.id, None)
        if action is not None:
            action()
        return True

    def outputs_format(self):
        return []


class SyncProbeComponent(Component):
    name = "sync advance flow probe"
    code = CODE
    bound_service = SyncProbeService


class SyncAdvanceFlowTestCase(TransactionTestCase):
    def setUp(self):
        self.runtime = BambooDjangoRuntime()
        self.messages = deque()
        FlowControl.actions.clear()
        FlowControl.executed.clear()
        ComponentLibrary.register_component(CODE, LEGACY_PLUGINS_VERSION, SyncProbeComponent)
        self.addCleanup(lambda: ComponentLibrary.components.pop(CODE, None))

        messages = self.messages

        def send_execute(
            runtime, process_id, node_id, root_pipeline_id, parent_pipeline_id, recover_point=None, headers=None
        ):
            messages.append(
                (
                    tasks.execute,
                    dict(
                        process_id=process_id,
                        node_id=node_id,
                        root_pipeline_id=root_pipeline_id,
                        parent_pipeline_id=parent_pipeline_id,
                        recover_point="{}" if not recover_point else recover_point.to_json(),
                        headers=headers or {},
                    ),
                )
            )

        def send_schedule(*args, **kwargs):
            raise AssertionError("synchronous probe flow must not schedule")

        for patcher in (
            mock.patch.object(BambooDjangoRuntime, "execute", send_execute),
            mock.patch.object(BambooDjangoRuntime, "schedule", send_schedule),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def drain(self):
        for _ in range(MAX_MESSAGES):
            if not self.messages:
                return
            task, kwargs = self.messages.popleft()
            task(**kwargs)
        self.fail("too many execute messages")

    def build(self):
        start, a, b, end = (
            EmptyStartEvent(),
            ServiceActivity(component_code=CODE),
            ServiceActivity(component_code=CODE),
            EmptyEndEvent(),
        )
        start.extend(a).extend(b).extend(end)
        return build_tree(start), a.id, b.id

    def run_pipeline(self, pipeline):
        result = api.run_pipeline(self.runtime, pipeline=pipeline, root_pipeline_data={})
        self.assertTrue(result.result, result.exc_trace)
        self.drain()

    def state_name(self, node_id):
        state = State.objects.filter(node_id=node_id).first()
        return state.name if state else None

    def test_pause_while_sync_node_running_suspends_process_then_resume_finishes(self):
        for enabled in (False, True):
            with self.subTest(checkpoint=enabled), mock.patch.object(
                Settings, "SYNC_ADVANCE_CHECKPOINT_ENABLED", enabled
            ):
                FlowControl.executed.clear()
                pipeline, a, b = self.build()
                root = pipeline["id"]
                FlowControl.actions[a] = lambda: api.pause_pipeline(self.runtime, root)
                self.run_pipeline(pipeline)

                process = Process.objects.get(root_pipeline_id=root)
                self.assertEqual(self.state_name(root), states.SUSPENDED)
                self.assertEqual(self.state_name(a), states.FINISHED)
                self.assertIsNone(self.state_name(b))
                self.assertTrue(process.suspended)
                self.assertEqual(process.suspended_by, root)
                self.assertEqual(process.current_node_id, b)

                self.assertTrue(api.resume_pipeline(self.runtime, root).result)
                self.drain()
                self.assertEqual(self.state_name(root), states.FINISHED)
                self.assertEqual(self.state_name(b), states.FINISHED)
                self.assertEqual(FlowControl.executed, Counter({a: 1, b: 1}))

    def test_revoke_while_sync_node_running_ends_process(self):
        for enabled in (False, True):
            with self.subTest(checkpoint=enabled), mock.patch.object(
                Settings, "SYNC_ADVANCE_CHECKPOINT_ENABLED", enabled
            ):
                FlowControl.executed.clear()
                pipeline, a, b = self.build()
                root = pipeline["id"]
                FlowControl.actions[a] = lambda: api.revoke_pipeline(self.runtime, root)
                self.run_pipeline(pipeline)

                process = Process.objects.get(root_pipeline_id=root)
                self.assertEqual(self.state_name(root), states.REVOKED)
                self.assertIsNone(self.state_name(b))
                self.assertTrue(process.dead)
                self.assertEqual(FlowControl.executed, Counter({a: 1}))

    def test_database_error_after_ready_checkpoint_retries_without_losing_message(self):
        pipeline, a, b = self.build()
        root = pipeline["id"]
        original_claim = BambooDjangoRuntime.claim_sync_advance
        failures = []

        def flaky_claim(runtime, process_id, node_id, version):
            if node_id == a and not failures:
                failures.append(SyncAdvanceCheckpoint.objects.get(process_id=process_id).phase)
                raise OperationalError(1213, "Deadlock found when trying to get lock (simulated)")
            return original_claim(runtime, process_id, node_id, version)

        with mock.patch.object(Settings, "SYNC_ADVANCE_CHECKPOINT_ENABLED", True), mock.patch.object(
            BambooDjangoRuntime, "claim_sync_advance", flaky_claim
        ):
            self.run_pipeline(pipeline)

        self.assertEqual(failures, [SyncAdvanceCheckpoint.READY])
        self.assertEqual(self.state_name(root), states.FINISHED)
        self.assertEqual(self.state_name(b), states.FINISHED)
        # The retry reuses the recorded execute result, so the plugin does not run again.
        self.assertEqual(FlowControl.executed, Counter({a: 1, b: 1}))
        process = Process.objects.get(root_pipeline_id=root)
        checkpoint = SyncAdvanceCheckpoint.objects.get(process_id=process.id)
        self.assertEqual((checkpoint.from_node, checkpoint.phase), (b, SyncAdvanceCheckpoint.CLAIMED))
