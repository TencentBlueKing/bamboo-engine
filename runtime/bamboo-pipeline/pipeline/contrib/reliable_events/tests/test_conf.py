# -*- coding: utf-8 -*-
from django.test import override_settings

from pipeline.contrib.reliable_events import conf


def test_active_enabled_default_false():
    assert conf.active_enabled() is False


@override_settings(PIPELINE_RELIABLE_EVENTS_ACTIVE_ENABLED=True)
def test_active_enabled_can_be_turned_on():
    assert conf.active_enabled() is True


def test_active_initial_delay_default():
    assert conf.active_initial_delay_seconds() == 10


def test_mode_resolver_absent_returns_none():
    assert conf.mode_resolver() is None


@override_settings(PIPELINE_RELIABLE_EVENTS_MODE_RESOLVER="pipeline.contrib.reliable_events.conf.active_enabled")
def test_mode_resolver_imports_dotted_path():
    resolver = conf.mode_resolver()
    assert callable(resolver)


@override_settings(PIPELINE_RELIABLE_EVENTS_MODE_RESOLVER="not.a.real.path")
def test_mode_resolver_bad_path_returns_none():
    assert conf.mode_resolver() is None
