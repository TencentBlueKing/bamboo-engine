# -*- coding: utf-8 -*-
from pipeline.contrib.reliable_events.constants import EventMode, EventStatus

TERMINAL = {
    EventStatus.APPLIED,
    EventStatus.OBSOLETE,
    EventStatus.MANUAL_REQUIRED,
    EventStatus.SHADOW_MISMATCH,
}

_ALLOWED = {
    EventStatus.PENDING: {EventStatus.PROCESSING, EventStatus.MANUAL_REQUIRED},
    EventStatus.PROCESSING: {
        EventStatus.APPLIED,
        EventStatus.OBSOLETE,
        EventStatus.PENDING,
        EventStatus.MANUAL_REQUIRED,
        EventStatus.SHADOW_MISMATCH,
    },
}


def validate_transition(current, target, mode):
    if current in TERMINAL:
        return False
    if target == EventStatus.SHADOW_MISMATCH and mode != EventMode.SHADOW:
        return False
    return target in _ALLOWED.get(current, set())
