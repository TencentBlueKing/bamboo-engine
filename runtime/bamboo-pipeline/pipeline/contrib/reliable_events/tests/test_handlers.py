# -*- coding: utf-8 -*-
from pipeline.contrib.reliable_events.handlers import base as handler_base
from pipeline.contrib.reliable_events.handlers.callback import CallbackShadowHandler
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase
from pipeline.eri.models import Schedule, State


class CallbackHandlerTest(ReliableEventsTestCase):
    def _event(self, node_id="node-1", version="v1"):
        return EngineEventInbox(
            event_type="NODE_CALLBACK", idempotency_key="callback:1",
            node_id=node_id, version=version, concurrency_key="{}:{}".format(node_id, version),
        )

    def test_registered_for_node_callback(self):
        self.assertIsInstance(handler_base.get_handler("NODE_CALLBACK"), CallbackShadowHandler)

    def test_obsolete_when_no_state(self):
        self.assertTrue(CallbackShadowHandler().is_obsolete(self._event()))

    def test_obsolete_when_version_changed(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v2")
        self.assertTrue(CallbackShadowHandler().is_obsolete(self._event(version="v1")))

    def test_not_obsolete_when_version_matches(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v1")
        self.assertFalse(CallbackShadowHandler().is_obsolete(self._event(version="v1")))

    def test_applied_when_schedule_finished(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=9001, type=1, process_id=1, node_id="node-1", version="v1", finished=True)
        self.assertTrue(CallbackShadowHandler().is_applied(self._event()))

    def test_not_applied_when_schedule_unfinished(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=9002, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        self.assertFalse(CallbackShadowHandler().is_applied(self._event()))
