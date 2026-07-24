# -*- coding: utf-8 -*-
from unittest import mock

from django.test import override_settings

from pipeline.contrib.reliable_events import collector
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase


class CollectorTest(ReliableEventsTestCase):
    @override_settings(PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=False)
    def test_disabled_writes_nothing(self):
        self.assertIsNone(collector.record_callback_receipt("node-1", "v1", 1))
        self.assertEqual(EngineEventInbox.objects.count(), 0)

    @override_settings(PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=True)
    def test_enabled_writes_shadow_event(self):
        e = collector.record_callback_receipt("node-1", "v1", 7, root_pipeline_id="root-1", schedule_id=9)
        self.assertIsNotNone(e)
        self.assertEqual(e.idempotency_key, "callback:7")
        self.assertEqual(e.mode, "SHADOW")
        self.assertEqual(e.status, "PENDING")
        self.assertEqual(e.concurrency_key, "node-1:v1")
        self.assertEqual(e.payload_ref, "eri_callbackdata:7")
        self.assertIsNotNone(e.next_attempt_at)
        self.assertIsNotNone(e.converge_deadline_at)

    @override_settings(PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=True)
    def test_duplicate_callback_data_id_dedup(self):
        collector.record_callback_receipt("node-1", "v1", 7)
        collector.record_callback_receipt("node-1", "v1", 7)
        self.assertEqual(EngineEventInbox.objects.filter(idempotency_key="callback:7").count(), 1)

    @override_settings(PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=True)
    def test_failure_is_swallowed(self):
        # 强制 guarded body 内部写库抛错，确认被 collector 的 try/except 吞掉：返回 None 且不外抛。
        # 影子门禁已由 override_settings 打开；建表探测缓存以 patch 强制为 True，保证走到 write 分支。
        with mock.patch.object(collector, "_inbox_table_available", return_value=True), mock.patch.object(
            EngineEventInbox.objects, "get_or_create", side_effect=Exception("boom")
        ):
            result = collector.record_callback_receipt("node-1", "v1", 8, data={"foo": "bar"})
        self.assertIsNone(result)
        self.assertEqual(EngineEventInbox.objects.count(), 0)
