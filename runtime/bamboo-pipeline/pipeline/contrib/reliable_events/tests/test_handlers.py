# -*- coding: utf-8 -*-
from unittest import mock

from bamboo_engine.eri import ScheduleType

from pipeline.contrib.reliable_events.constants import EventType
from pipeline.contrib.reliable_events.handlers import base as handler_base
from pipeline.contrib.reliable_events.handlers.callback import CallbackHandler, NoScheduleError, NotEligibleError
from pipeline.contrib.reliable_events.models import EngineEventInbox
from pipeline.contrib.reliable_events.tests.base import ReliableEventsTestCase
from pipeline.eri.models import CallbackData, Schedule, State


class _Evt(object):
    def __init__(self, node_id, version, source_id):
        self.node_id = node_id
        self.version = version
        self.source_id = source_id


class CallbackHandlerTest(ReliableEventsTestCase):
    def _event(self, node_id="node-1", version="v1"):
        return EngineEventInbox(
            event_type="NODE_CALLBACK", idempotency_key="callback:1",
            node_id=node_id, version=version, concurrency_key="{}:{}".format(node_id, version),
        )

    def test_registered_for_node_callback(self):
        self.assertIsInstance(handler_base.get_handler("NODE_CALLBACK"), CallbackHandler)

    def test_obsolete_when_no_state(self):
        self.assertTrue(CallbackHandler().is_obsolete(self._event()))

    def test_obsolete_when_version_changed(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v2")
        self.assertTrue(CallbackHandler().is_obsolete(self._event(version="v1")))

    def test_not_obsolete_when_version_matches(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v1")
        self.assertFalse(CallbackHandler().is_obsolete(self._event(version="v1")))

    def test_applied_when_schedule_finished(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=9001, type=1, process_id=1, node_id="node-1", version="v1", finished=True)
        self.assertTrue(CallbackHandler().is_applied(self._event()))

    def test_not_applied_when_schedule_unfinished(self):
        State.objects.create(node_id="node-1", root_id="root-1", parent_id="", name="RUNNING", version="v1")
        Schedule.objects.create(id=9002, type=1, process_id=1, node_id="node-1", version="v1", finished=False)
        self.assertFalse(CallbackHandler().is_applied(self._event()))


class CallbackApplyTest(ReliableEventsTestCase):
    def test_registered_for_node_callback(self):
        assert isinstance(handler_base.get_handler(EventType.NODE_CALLBACK), CallbackHandler)

    def test_apply_redispatches_existing_callback(self):
        State.objects.create(node_id="na", version="v1", root_id="r1", parent_id="r1", name="x", loop=1, inner_loop=1)
        sch = Schedule.objects.create(type=1, process_id=7, node_id="na", version="v1", finished=False)
        cb = CallbackData.objects.create(node_id="na", version="v1", data="{}")
        evt = _Evt("na", "v1", str(cb.id))

        with mock.patch("pipeline.contrib.reliable_events.handlers.callback.BambooDjangoRuntime") as m_rt:
            CallbackHandler().apply(evt)
            m_rt.return_value.schedule.assert_called_once_with(
                process_id=7, node_id="na", schedule_id=str(sch.id), callback_data_id=cb.id
            )

    def test_apply_without_schedule_raises(self):
        cb = CallbackData.objects.create(node_id="nb", version="v1", data="{}")
        evt = _Evt("nb", "v1", str(cb.id))
        try:
            CallbackHandler().apply(evt)
            assert False, "expected NoScheduleError"
        except NoScheduleError:
            pass

    def test_is_applied_true_when_schedule_finished(self):
        Schedule.objects.create(type=1, process_id=1, node_id="nc", version="v1", finished=True)
        assert CallbackHandler().is_applied(_Evt("nc", "v1", "1")) is True

    def test_is_obsolete_true_when_version_moved(self):
        State.objects.create(node_id="nd", version="v2", root_id="r", parent_id="r", name="x", loop=1, inner_loop=1)
        assert CallbackHandler().is_obsolete(_Evt("nd", "v1", "1")) is True

    def test_apply_multiple_callback_raises_not_eligible(self):
        State.objects.create(node_id="ne", version="v1", root_id="r", parent_id="r", name="x", loop=1, inner_loop=1)
        Schedule.objects.create(
            type=ScheduleType.MULTIPLE_CALLBACK.value, process_id=1, node_id="ne", version="v1", finished=False
        )
        cb = CallbackData.objects.create(node_id="ne", version="v1", data="{}")
        evt = _Evt("ne", "v1", str(cb.id))

        with mock.patch("pipeline.contrib.reliable_events.handlers.callback.BambooDjangoRuntime") as m_rt:
            try:
                CallbackHandler().apply(evt)
                assert False, "expected NotEligibleError"
            except NotEligibleError:
                pass
            m_rt.return_value.schedule.assert_not_called()
