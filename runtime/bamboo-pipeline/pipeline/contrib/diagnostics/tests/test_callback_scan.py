# -*- coding: utf-8 -*-

from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from pipeline.contrib.diagnostics.callback_scan import (
    CURSOR_NAME,
    OUTCOME_CONSUMED,
    OUTCOME_MULTIPLE,
    OUTCOME_PENDING,
    OUTCOME_ROOT_INACTIVE,
    OUTCOME_SCHEDULING,
    OUTCOME_STALE_VERSION,
    backfill_callbacks,
    classify,
    scan_callbacks,
)
from pipeline.contrib.diagnostics.case_types import CALLBACK_DISPATCH_LOST
from pipeline.contrib.diagnostics.cursor import load_cursor, save_cursor
from pipeline.contrib.diagnostics.models import DiagnosticCase
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import (
    CALLBACK,
    MULTIPLE_CALLBACK,
    callback_shape,
    running_root,
)
from pipeline.eri.models import CallbackData, Schedule, State


def _shape(state_version="v1", state_name="RUNNING", schedule_type=CALLBACK, **schedule_fields):
    schedule = {"type": schedule_type, "finished": False, "expired": False, "scheduling": False, "schedule_times": 0}
    schedule.update(schedule_fields)
    return (
        SimpleNamespace(id=1, node_id="cb", version="v1"),
        SimpleNamespace(version=state_version, name=state_name, root_id="root-1"),
        SimpleNamespace(**schedule),
    )


class ClassifyTest(SimpleTestCase):
    def test_pending(self):
        self.assertEqual(classify(*_shape(), root_state="RUNNING"), OUTCOME_PENDING)

    def test_consumed(self):
        self.assertEqual(classify(*_shape(finished=True)), OUTCOME_CONSUMED)
        self.assertEqual(classify(*_shape(schedule_times=1)), OUTCOME_CONSUMED)
        self.assertEqual(classify(*_shape(state_name="FAILED")), OUTCOME_CONSUMED)

    def test_stale_version(self):
        self.assertEqual(classify(*_shape(state_version="v2")), OUTCOME_STALE_VERSION)

    def test_multiple_callback_is_count_only(self):
        self.assertEqual(classify(*_shape(schedule_type=MULTIPLE_CALLBACK)), OUTCOME_MULTIPLE)

    def test_scheduling_and_inactive_root(self):
        self.assertEqual(classify(*_shape(scheduling=True), root_state="RUNNING"), OUTCOME_SCHEDULING)
        self.assertEqual(classify(*_shape(), root_state="REVOKED"), OUTCOME_ROOT_INACTIVE)

    def test_missing_root_state_is_inactive(self):
        self.assertEqual(classify(*_shape(), root_state=None), OUTCOME_ROOT_INACTIVE)


def _prime():
    top = CallbackData.objects.order_by("-id").values_list("id", flat=True).first() or 0
    save_cursor(CURSOR_NAME, position_id=0, extra={"high_marks": [top, top]})


@override_settings(PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED=True)
class CallbackScanTest(DiagnosticsTestCase):
    def setUp(self):
        super(CallbackScanTest, self).setUp()
        running_root()
        self.now = timezone.now()

    def later(self, seconds):
        return self.now + timedelta(seconds=seconds)

    def test_first_run_starts_from_current_max(self):
        _process, _schedule, callback = callback_shape()
        report = scan_callbacks(now=self.now)
        self.assertEqual(report.rows, 0)
        self.assertEqual(load_cursor(CURSOR_NAME).position_id, callback.id)

    def test_pending_callback_becomes_case_after_confirm_window(self):
        callback_shape()
        _prime()
        first = scan_callbacks(now=self.now)
        self.assertEqual((first.rows, first.hits), (1, []))
        second = scan_callbacks(now=self.later(130))
        [(root_id, node_id, hit)] = second.hits
        self.assertEqual((root_id, node_id, hit.type), ("root-1", "cb", CALLBACK_DISPATCH_LOST))
        self.assertIn("callback_data_id=", hit.evidence["derived_message"])
        self.assertTrue(DiagnosticCase.objects.filter(stuck_type=CALLBACK_DISPATCH_LOST).exists())

    def test_age_equal_to_confirm_window_stays_pending(self):
        now = self.now.replace(microsecond=0)
        _process, _schedule, callback = callback_shape()
        _prime()
        scan_callbacks(now=now)
        report = scan_callbacks(now=now + timedelta(seconds=120))
        self.assertEqual(report.hits, [])
        self.assertIn(str(callback.id), load_cursor(CURSOR_NAME).extra["pending"])

    def test_missing_root_state_opens_no_case(self):
        State.objects.filter(node_id="root-1").delete()
        callback_shape()
        _prime()
        scan_callbacks(now=self.now)
        self.assertEqual(scan_callbacks(now=self.later(130)).hits, [])
        self.assertFalse(DiagnosticCase.objects.exists())

    def test_consumed_callback_is_not_tracked(self):
        callback_shape(finished=True)
        _prime()
        scan_callbacks(now=self.now)
        self.assertEqual(scan_callbacks(now=self.later(130)).hits, [])

    def test_callback_consumed_during_confirm_window(self):
        _process, schedule, _callback = callback_shape()
        _prime()
        scan_callbacks(now=self.now)
        Schedule.objects.filter(id=schedule.id).update(finished=True)
        self.assertEqual(scan_callbacks(now=self.later(130)).hits, [])

    def test_case_closes_after_schedule_finishes(self):
        _process, schedule, _callback = callback_shape()
        _prime()
        scan_callbacks(now=self.now)
        scan_callbacks(now=self.later(130))
        Schedule.objects.filter(id=schedule.id).update(finished=True)
        report = scan_callbacks(now=self.later(160))
        self.assertEqual(report.outcomes["closed"], 1)
        self.assertEqual(DiagnosticCase.objects.get().status, DiagnosticCase.STATUS_RESOLVED)

    def test_multiple_callback_is_counted_only(self):
        callback_shape(schedule_type=MULTIPLE_CALLBACK)
        _prime()
        report = scan_callbacks(now=self.now)
        self.assertEqual(report.outcomes[OUTCOME_MULTIPLE], 1)
        self.assertEqual(load_cursor(CURSOR_NAME).extra["pending"], {})

    def test_backfill_dry_run_reports_without_writing(self):
        _process, _schedule, callback = callback_shape()
        report = backfill_callbacks(callback.id, now=self.now, confirm_seconds=0)
        self.assertEqual(len(report.hits), 1)
        self.assertTrue(report.dry_run)
        self.assertFalse(DiagnosticCase.objects.exists())

    def test_backfill_drops_callback_consumed_while_confirming(self):
        _process, schedule, callback = callback_shape()

        def consume(_seconds):
            Schedule.objects.filter(id=schedule.id).update(schedule_times=1)

        with mock.patch("pipeline.contrib.diagnostics.callback_scan.time.sleep", side_effect=consume) as sleep:
            report = backfill_callbacks(callback.id, now=self.now, confirm_seconds=120)
        sleep.assert_called_once_with(120)
        self.assertEqual(report.hits, [])
        self.assertEqual(report.outcomes["backfill_unconfirmed"], 1)

    def test_backfill_reports_callback_still_pending_after_confirm(self):
        _process, _schedule, callback = callback_shape()
        with mock.patch("pipeline.contrib.diagnostics.callback_scan.time.sleep") as sleep:
            report = backfill_callbacks(callback.id, now=self.now, confirm_seconds=120)
        sleep.assert_called_once_with(120)
        self.assertEqual(len(report.hits), 1)
        self.assertEqual(report.outcomes["backfill_unconfirmed"], 0)

    @override_settings(PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED=False)
    def test_disabled_by_default(self):
        self.assertIsNone(scan_callbacks(now=self.now))
