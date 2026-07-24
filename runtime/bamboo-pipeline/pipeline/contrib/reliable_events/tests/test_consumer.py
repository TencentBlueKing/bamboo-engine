# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.reliable_events import consumer
from pipeline.contrib.reliable_events.constants import EventMode, EventStatus
from pipeline.contrib.reliable_events.handlers.callback import NotEligibleError
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase
from pipeline.eri.models import Schedule, State


class ConsumerTest(ReliableEventsTestCase):
    def _event(self, node_id="node-1", version="v1", **kwargs):
        now = timezone.now()
        defaults = dict(
            event_type="NODE_CALLBACK", idempotency_key="callback:1", node_id=node_id, version=version,
            concurrency_key="{}:{}".format(node_id, version), status="PENDING", mode="SHADOW",
            next_attempt_at=now, converge_deadline_at=now + timedelta(seconds=600),
        )
        defaults.update(kwargs)
        return EngineEventInbox.objects.create(**defaults)

    def test_applied_when_schedule_finished(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=True)
        e = self._event()
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "APPLIED")
        self.assertEqual(EngineEventInbox.objects.get(id=e.id).status, "APPLIED")

    def test_obsolete_when_version_changed(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v2")
        e = self._event(version="v1")
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "OBSOLETE")

    def test_retry_before_deadline(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        e = self._event()
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "PENDING")
        reloaded = EngineEventInbox.objects.get(id=e.id)
        self.assertEqual(reloaded.attempts, 1)
        self.assertGreater(reloaded.next_attempt_at, timezone.now())

    def test_shadow_mismatch_after_deadline(self):
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        past = timezone.now() - timedelta(seconds=1)
        e = self._event(converge_deadline_at=past)
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "SHADOW_MISMATCH")
        self.assertEqual(EngineEventInbox.objects.get(id=e.id).status, "SHADOW_MISMATCH")

    def test_lease_busy_keeps_pending(self):
        from pipeline.contrib.reliable_events import lanes
        State.objects.create(node_id="node-1", root_id="r", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=1, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        e = self._event()
        lanes.acquire_lease("node-1:v1", "other-worker")  # 占用同通道
        self.assertEqual(consumer.process_event(e.id, owner="w-a"), "PENDING")

    def test_backoff_seconds_caps_at_max(self):
        with override_settings(PIPELINE_RELIABLE_EVENTS_BACKOFF_BASE_SECONDS=5,
                               PIPELINE_RELIABLE_EVENTS_BACKOFF_MAX_SECONDS=300):
            self.assertEqual(consumer.backoff_seconds(0), 5)
            self.assertEqual(consumer.backoff_seconds(3), 40)
            self.assertEqual(consumer.backoff_seconds(20), 300)


def _mk(mode=EventMode.ACTIVE, **kw):
    now = timezone.now()
    base = dict(
        event_type="NODE_CALLBACK", idempotency_key="callback:{}".format(id(object())),
        node_id="n", version="v1", source_id="1", concurrency_key="n:v1",
        mode=mode, status=EventStatus.PENDING, next_attempt_at=now,
        converge_deadline_at=now + timedelta(seconds=600),
    )
    base.update(kw)
    return EngineEventInbox.objects.create(**base)


class ActiveConsumerTest(ReliableEventsTestCase):
    def _patch_handler(self, is_applied=False, is_obsolete=False, apply_side_effect=None):
        h = mock.Mock()
        h.is_applied.return_value = is_applied
        h.is_obsolete.return_value = is_obsolete
        if apply_side_effect is not None:
            h.apply.side_effect = apply_side_effect
        return h

    def test_active_already_applied_short_circuits(self):
        evt = _mk()
        with mock.patch.object(consumer, "get_handler", return_value=self._patch_handler(is_applied=True)) as _:
            status = consumer.process_event(evt.id)
        assert status == EventStatus.APPLIED

    def test_active_calls_apply_then_pending_for_recheck(self):
        evt = _mk()
        h = self._patch_handler(is_applied=False, is_obsolete=False)
        with mock.patch.object(consumer, "get_handler", return_value=h):
            status = consumer.process_event(evt.id)
        h.apply.assert_called_once()
        evt.refresh_from_db()
        assert status == EventStatus.PENDING
        assert evt.attempts == 1
        assert evt.next_attempt_at > timezone.now()

    def test_active_deadline_exceeded_goes_manual(self):
        past = timezone.now() - timedelta(seconds=1)
        evt = _mk(converge_deadline_at=past)
        h = self._patch_handler(is_applied=False, is_obsolete=False)
        with mock.patch.object(consumer, "get_handler", return_value=h):
            status = consumer.process_event(evt.id)
        assert status == EventStatus.MANUAL_REQUIRED  # ACTIVE 到期转人工,非 SHADOW_MISMATCH
        h.apply.assert_not_called()

    def test_active_apply_error_retries_with_error_code(self):
        evt = _mk()
        h = self._patch_handler(is_applied=False, is_obsolete=False, apply_side_effect=RuntimeError("boom"))
        with mock.patch.object(consumer, "get_handler", return_value=h):
            status = consumer.process_event(evt.id)
        assert status == EventStatus.PENDING
        evt.refresh_from_db()
        assert evt.last_error_code == "APPLY_FAILED"

    def test_active_not_due_defers_without_apply(self):
        # next_attempt_at 在未来:立即调度(dispatch_enabled)撞上兜底时,不得抢跑直接驱动。
        future = timezone.now() + timedelta(seconds=60)
        evt = _mk(next_attempt_at=future)
        h = self._patch_handler(is_applied=False, is_obsolete=False)
        with mock.patch.object(consumer, "get_handler", return_value=h):
            status = consumer.process_event(evt.id)
        assert status == EventStatus.PENDING
        h.apply.assert_not_called()
        evt.refresh_from_db()
        assert evt.attempts == 0
        assert evt.status == EventStatus.PENDING
        assert evt.next_attempt_at == future

    def test_active_non_single_callback_goes_manual(self):
        evt = _mk()
        h = self._patch_handler(is_applied=False, is_obsolete=False, apply_side_effect=NotEligibleError("x"))
        with mock.patch.object(consumer, "get_handler", return_value=h):
            status = consumer.process_event(evt.id)
        assert status == EventStatus.MANUAL_REQUIRED

    def test_shadow_unchanged_marks_mismatch_on_deadline(self):
        past = timezone.now() - timedelta(seconds=1)
        evt = _mk(mode=EventMode.SHADOW, converge_deadline_at=past)
        h = self._patch_handler(is_applied=False, is_obsolete=False)
        with mock.patch.object(consumer, "get_handler", return_value=h):
            status = consumer.process_event(evt.id)
        assert status == EventStatus.SHADOW_MISMATCH
        h.apply.assert_not_called()
