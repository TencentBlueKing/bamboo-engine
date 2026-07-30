from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from pipeline.contrib.reliable_events import purge
from pipeline.contrib.reliable_events.constants import EventStatus
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase


class PurgeTest(ReliableEventsTestCase):
    def _mk(self, status, finished_days_ago, key):
        now = timezone.now()
        return EngineEventInbox.objects.create(
            event_type="NODE_CALLBACK", idempotency_key=key, node_id="n", version="v", source_id="1",
            concurrency_key="n:v", mode="ACTIVE", status=status,
            finished_at=now - timedelta(days=finished_days_ago),
        )

    @override_settings(PIPELINE_RELIABLE_EVENTS_EVENT_RETENTION_DAYS=30)
    def test_purges_old_applied_and_obsolete_only(self):
        self._mk(EventStatus.APPLIED, 40, "k1")       # 过期 applied -> 删
        self._mk(EventStatus.OBSOLETE, 31, "k2")      # 过期 obsolete -> 删
        self._mk(EventStatus.APPLIED, 10, "k3")       # 未过期 -> 留
        self._mk(EventStatus.MANUAL_REQUIRED, 90, "k4")  # 需人工 -> 永不清
        self._mk(EventStatus.SHADOW_MISMATCH, 90, "k5")  # 异常明细 -> 本单元不清
        deleted = purge.purge_finished_events()
        assert deleted == 2
        remaining = set(EngineEventInbox.objects.values_list("idempotency_key", flat=True))
        assert remaining == {"k3", "k4", "k5"}
