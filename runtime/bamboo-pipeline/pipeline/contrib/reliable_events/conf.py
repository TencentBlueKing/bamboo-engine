# -*- coding: utf-8 -*-
from django.conf import settings


def _get_setting(name, default):
    return getattr(settings, "PIPELINE_RELIABLE_EVENTS_{}".format(name), default)


def shadow_enabled():
    return _get_setting("SHADOW_ENABLED", False)


def dispatch_enabled():
    return _get_setting("DISPATCH_ENABLED", False)


def compensation_enabled():
    return _get_setting("COMPENSATION_ENABLED", False)


def converge_seconds():
    return _get_setting("CONVERGE_SECONDS", 600)


def discover_seconds():
    return _get_setting("DISCOVER_SECONDS", 180)


def lease_seconds():
    return _get_setting("LEASE_SECONDS", 120)


def max_attempts():
    return _get_setting("MAX_ATTEMPTS", 20)


def backoff_base_seconds():
    return _get_setting("BACKOFF_BASE_SECONDS", 5)


def backoff_max_seconds():
    return _get_setting("BACKOFF_MAX_SECONDS", 300)


def compensation_batch():
    return _get_setting("COMPENSATION_BATCH", 200)


def event_retention_days():
    return _get_setting("EVENT_RETENTION_DAYS", 30)
