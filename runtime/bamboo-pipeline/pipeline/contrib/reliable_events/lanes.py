# -*- coding: utf-8 -*-
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from pipeline.contrib.reliable_events import conf
from pipeline.contrib.reliable_events.models import EngineEventLane


def _ensure_lane(concurrency_key):
    try:
        with transaction.atomic():
            EngineEventLane.objects.get_or_create(concurrency_key=concurrency_key)
    except IntegrityError:
        pass


def acquire_lease(concurrency_key, owner, now=None, lease_seconds=None):
    now = now or timezone.now()
    lease_seconds = conf.lease_seconds() if lease_seconds is None else lease_seconds
    lease_until = now + timedelta(seconds=lease_seconds)

    _ensure_lane(concurrency_key)

    # 空闲条件：无租约到期时间 或 已过期
    updated = EngineEventLane.objects.filter(
        concurrency_key=concurrency_key, lease_until__isnull=True
    ).update(lease_owner=owner, lease_generation=F("lease_generation") + 1, lease_until=lease_until)
    if not updated:
        updated = EngineEventLane.objects.filter(
            concurrency_key=concurrency_key, lease_until__lte=now
        ).update(lease_owner=owner, lease_generation=F("lease_generation") + 1, lease_until=lease_until)
    if not updated:
        return None
    try:
        return EngineEventLane.objects.values_list("lease_generation", flat=True).get(
            concurrency_key=concurrency_key, lease_owner=owner
        )
    except EngineEventLane.DoesNotExist:
        return None


def renew_lease(concurrency_key, owner, generation, now=None, lease_seconds=None):
    now = now or timezone.now()
    lease_seconds = conf.lease_seconds() if lease_seconds is None else lease_seconds
    lease_until = now + timedelta(seconds=lease_seconds)
    return EngineEventLane.objects.filter(
        concurrency_key=concurrency_key, lease_owner=owner, lease_generation=generation
    ).update(lease_until=lease_until) == 1


def release_lease(concurrency_key, owner, generation, now=None):
    now = now or timezone.now()
    return EngineEventLane.objects.filter(
        concurrency_key=concurrency_key, lease_owner=owner, lease_generation=generation
    ).update(lease_owner="", lease_until=None, last_progress_at=now) == 1
