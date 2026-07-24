# -*- coding: utf-8 -*-
from pipeline.contrib.reliable_events.constants import EventType
from pipeline.contrib.reliable_events.handlers.base import EventHandler, register
from pipeline.eri.models import Schedule, State


class CallbackShadowHandler(EventHandler):
    def is_applicable(self, event):
        return True

    def apply(self, event):
        raise NotImplementedError("shadow mode must not drive engine state")

    def is_obsolete(self, event):
        state = State.objects.filter(node_id=event.node_id).first()
        if state is None:
            return True
        return state.version != event.version

    def is_applied(self, event):
        schedule = Schedule.objects.filter(node_id=event.node_id, version=event.version).first()
        if schedule is None:
            return False
        return bool(schedule.finished)


register(EventType.NODE_CALLBACK, CallbackShadowHandler())
