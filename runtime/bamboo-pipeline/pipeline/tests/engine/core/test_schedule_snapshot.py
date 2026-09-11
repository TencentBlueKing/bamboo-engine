# -*- coding: utf-8 -*-
"""A callback must use state committed before it acquires the scheduling lock."""
from unittest import mock

from django.test import TestCase
from pipeline.core.data.base import DataObject
from pipeline.core.flow import Service, ServiceActivity
from pipeline.engine import states
from pipeline.engine.core import schedule
from pipeline.engine.models import ScheduleService, Status


class CountingCallbackService(Service):
    __need_schedule__ = True
    __multi_callback_enabled__ = True
    interval = None

    def execute(self, data, parent_data):
        return True

    def schedule(self, data, parent_data, callback_data=None):
        data.set_outputs("count", data.get_one_of_outputs("count", 0) + 1)
        return True


class ScheduleSnapshotTestCase(TestCase):
    def setUp(self):
        self.node_id = "a" * 32
        self.version = "b" * 32
        self.schedule_id = self.node_id + self.version
        self.node = ServiceActivity(self.node_id, CountingCallbackService(), data=DataObject({}))
        Status.objects.create(id=self.node_id, state=states.RUNNING, version=self.version)
        ScheduleService.objects.create(
            id=self.schedule_id,
            activity_id=self.node_id,
            version=self.version,
            process_id="c" * 32,
            service_act=self.node,
            wait_callback=True,
            multi_callback_enabled=True,
        )
        for patcher in (
            mock.patch("pipeline.engine.core.schedule.get_schedule_parent_data", return_value=DataObject({})),
            mock.patch("pipeline.engine.core.schedule.set_schedule_data"),
            mock.patch("pipeline.engine.models.Data.objects.write_node_data"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_after_other_callback_commits(self, **updates):
        real_get = ScheduleService.objects.get
        first_read = True

        def read_then_commit(*args, **kwargs):
            nonlocal first_read
            stale = real_get(*args, **kwargs)
            if first_read:
                first_read = False
                # Deterministically place another worker's commit between our read and lock acquisition.
                ScheduleService.objects.filter(id=self.schedule_id).update(**updates)
            return stale

        with mock.patch.object(ScheduleService.objects, "get", side_effect=read_then_commit):
            schedule.schedule("c" * 32, self.schedule_id)
        return real_get(id=self.schedule_id)

    def test_callback_preserves_preceding_committed_count(self):
        self.node.data.set_outputs("count", 4)
        result = self.run_after_other_callback_commits(service_act=self.node, schedule_times=4)
        self.assertEqual(result.service_act.data.get_one_of_outputs("count"), 5)
        self.assertEqual(result.schedule_times, 5)
        self.assertFalse(result.is_scheduling)

    def test_callback_does_not_reopen_a_finished_schedule(self):
        result = self.run_after_other_callback_commits(is_finished=True, service_act=None, schedule_times=5)
        self.assertTrue(result.is_finished)
        self.assertIsNone(result.service_act)
        self.assertEqual(result.schedule_times, 5)
        self.assertFalse(result.is_scheduling)
