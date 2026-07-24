# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.reliable_events import collector, conf
from pipeline.contrib.reliable_events.constants import EventMode
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


class ModeResolutionTest(ReliableEventsTestCase):
    @override_settings(PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=True)
    def test_default_is_shadow_when_no_resolver(self):
        event = collector.record_callback_receipt(node_id="n1", version="v1", callback_data_id=1)
        assert event is not None
        assert event.mode == EventMode.SHADOW
        assert event.next_attempt_at is not None

    @override_settings(
        PIPELINE_RELIABLE_EVENTS_ACTIVE_ENABLED=True,
        PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=True,
        PIPELINE_RELIABLE_EVENTS_ACTIVE_INITIAL_DELAY_SECONDS=30,
    )
    def test_resolver_active_promotes_and_delays(self):
        with mock.patch.object(conf, "mode_resolver", return_value=lambda node_id, version: "ACTIVE"):
            before = timezone.now()
            event = collector.record_callback_receipt(node_id="n2", version="v1", callback_data_id=2)
        assert event.mode == EventMode.ACTIVE
        # ACTIVE 首个 next_attempt_at 相对 accepted 有 ~30s 延迟
        assert event.next_attempt_at >= before + timedelta(seconds=25)

    @override_settings(PIPELINE_RELIABLE_EVENTS_SHADOW_ENABLED=True)
    def test_resolver_active_but_active_disabled_falls_back_to_shadow(self):
        with mock.patch.object(conf, "mode_resolver", return_value=lambda node_id, version: "ACTIVE"):
            event = collector.record_callback_receipt(node_id="n3", version="v1", callback_data_id=3)
        assert event.mode == EventMode.SHADOW

    def test_all_flags_off_returns_none(self):
        event = collector.record_callback_receipt(node_id="n4", version="v1", callback_data_id=4)
        assert event is None

    @override_settings(PIPELINE_RELIABLE_EVENTS_ACTIVE_ENABLED=True)
    def test_resolver_exception_is_swallowed_and_falls_back(self):
        def boom(node_id, version):
            raise ValueError("resolver boom")

        with mock.patch.object(conf, "mode_resolver", return_value=boom):
            # active_enabled 但 shadow 关；resolver 抛错 → raw=None → 非 ACTIVE 且 shadow 关 → None（不崩）
            event = collector.record_callback_receipt(node_id="n5", version="v1", callback_data_id=5)
        assert event is None
