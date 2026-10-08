# -*- coding: utf-8 -*-

from unittest import mock

from django.test import SimpleTestCase

from pipeline.contrib.diagnostics import metrics
from pipeline.contrib.diagnostics.types import DiagnosticHit, ScanReport


def _report(scanner, **fields):
    values = {
        "scanner": scanner,
        "rows": 3,
        "candidates": 1,
        "hits": [],
        "cases": 0,
        "cursor_lag_seconds": 12,
        "capped": False,
        "dry_run": False,
        "outcomes": {},
    }
    values.update(fields)
    return ScanReport(**values)


def _hit(stuck_type):
    return DiagnosticHit(stuck_type, "critical", 0.95, {}, {}, [], [], "")


def _value(metric, **labels):
    return metric.labels(hostname=metrics.HOST_NAME, **labels)._value.get()


class RecordScanReportTest(SimpleTestCase):
    def test_records_rows_hits_and_lag(self):
        rows_before = _value(metrics.DIAGNOSTICS_SCAN_ROWS, scanner="t_record")
        hits_before = _value(metrics.DIAGNOSTICS_SCAN_HITS, scanner="t_record", stuck_type="demo")
        metrics.record_scan_report(_report("t_record", hits=[("r", "n", _hit("demo"))]))
        self.assertEqual(_value(metrics.DIAGNOSTICS_SCAN_ROWS, scanner="t_record") - rows_before, 3)
        self.assertEqual(_value(metrics.DIAGNOSTICS_SCAN_HITS, scanner="t_record", stuck_type="demo") - hits_before, 1)
        self.assertEqual(_value(metrics.DIAGNOSTICS_SCAN_CURSOR_LAG, scanner="t_record"), 12)

    def test_dry_run_only_logs(self):
        before = _value(metrics.DIAGNOSTICS_SCAN_ROWS, scanner="t_dry")
        metrics.record_scan_report(_report("t_dry", dry_run=True))
        self.assertEqual(_value(metrics.DIAGNOSTICS_SCAN_ROWS, scanner="t_dry"), before)

    def test_id_lag_is_used_when_there_is_no_time_lag(self):
        metrics.record_scan_report(_report("t_id", cursor_lag_seconds=None, outcomes={"id_lag": 40}))
        self.assertEqual(_value(metrics.DIAGNOSTICS_SCAN_CURSOR_LAG, scanner="t_id"), 40)

    def test_metric_errors_are_swallowed(self):
        with mock.patch.object(metrics.DIAGNOSTICS_SCAN_ROWS, "labels", side_effect=RuntimeError("boom")):
            metrics.record_scan_report(_report("t_err"))

    def test_observe_hit(self):
        metrics.observe_hit("demo_latency", 90)
        child = metrics.DIAGNOSTICS_DETECT_LATENCY.labels(stuck_type="demo_latency", hostname=metrics.HOST_NAME)
        self.assertEqual(child._sum.get(), 90)


class RecordRecoveryTest(SimpleTestCase):
    def test_counts_by_type_trigger_and_result(self):
        labels = {"stuck_type": "t_recovery", "trigger": "auto", "result": "applied"}
        before = _value(metrics.DIAGNOSTICS_RECOVERY, **labels)
        metrics.record_recovery("t_recovery", "auto", "applied")
        self.assertEqual(_value(metrics.DIAGNOSTICS_RECOVERY, **labels) - before, 1)

    def test_metric_errors_are_swallowed(self):
        with mock.patch.object(metrics.DIAGNOSTICS_RECOVERY, "labels", side_effect=RuntimeError("boom")):
            metrics.record_recovery("t_recovery", "auto", "applied")


class RecordBreakerOpenTest(SimpleTestCase):
    def test_counts_breaker_open(self):
        before = _value(metrics.DIAGNOSTICS_RECOVERY_BREAKER_OPEN)
        metrics.record_breaker_open()
        self.assertEqual(_value(metrics.DIAGNOSTICS_RECOVERY_BREAKER_OPEN) - before, 1)

    def test_metric_errors_are_swallowed(self):
        with mock.patch.object(metrics.DIAGNOSTICS_RECOVERY_BREAKER_OPEN, "labels", side_effect=RuntimeError("boom")):
            metrics.record_breaker_open()
