# -*- coding: utf-8 -*-

from unittest import mock

from django.test import TestCase

from pipeline.contrib.diagnostics import collector


class CollectorAtomicTest(TestCase):
    def test_scoped_snapshot_wrapped_in_atomic(self):
        with mock.patch("pipeline.contrib.diagnostics.collector.transaction.atomic") as m_atomic:
            collector.collect_runtime_snapshot(root_pipeline_id="root-none")
        self.assertTrue(m_atomic.called)

    def test_no_scope_returns_without_transaction(self):
        with mock.patch("pipeline.contrib.diagnostics.collector.transaction.atomic") as m_atomic:
            snapshot = collector.collect_runtime_snapshot()
        self.assertFalse(m_atomic.called)
        self.assertEqual(snapshot.processes, [])
