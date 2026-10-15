# -*- coding: utf-8 -*-

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from pipeline.contrib.diagnostics.cursor import (
    EXHAUSTED_ID,
    chunks,
    load_cursor,
    process_window_pages,
    save_cursor,
    window_start,
)
from pipeline.contrib.diagnostics.tests.base import DiagnosticsTestCase
from pipeline.contrib.diagnostics.tests.factories import ago, make_process
from pipeline.eri.models import Process


class ChunksTest(SimpleTestCase):
    def test_split(self):
        self.assertEqual(list(chunks(range(5), size=2)), [[0, 1], [2, 3], [4]])

    def test_accepts_set_and_dict(self):
        self.assertEqual(sorted(sum(chunks({3, 1, 2}, size=2), [])), [1, 2, 3])
        self.assertEqual(sorted(sum(chunks({"a": 1, "b": 2}), [])), ["a", "b"])


class CursorStoreTest(DiagnosticsTestCase):
    def test_roundtrip(self):
        position = timezone.now()
        save_cursor("demo", position=position, position_id=7, extra={"high_marks": [1, 2]})
        save_cursor("demo", position=position, position_id=8, extra={"high_marks": [2, 3]})
        cursor = load_cursor("demo")
        self.assertEqual(cursor.position, position)
        self.assertEqual(cursor.position_id, 8)
        self.assertEqual(cursor.extra, {"high_marks": [2, 3]})

    def test_window_start_prefers_override_then_cursor_then_lookback(self):
        cutoff = timezone.now()
        override = cutoff - timedelta(days=3)
        self.assertEqual(window_start("demo", cutoff, 3600, start_override=override), (override, 0))
        self.assertEqual(window_start("demo", cutoff, 3600), (cutoff - timedelta(seconds=3600), 0))
        save_cursor("demo", position=cutoff - timedelta(seconds=60), position_id=9)
        self.assertEqual(window_start("demo", cutoff, 3600), (cutoff - timedelta(seconds=60), 9))


class WindowPagesTest(DiagnosticsTestCase):
    def _ids(self, start, start_id, end, page_size=10, max_rows=100):
        pages = list(process_window_pages(Process.objects.all(), start, start_id, end, page_size, max_rows))
        return [len(page) for page in pages], [process.id for page in pages for process in page]

    def test_keyset_pages_keep_ties_in_id_order(self):
        beat = ago(600)
        processes = [make_process(root="r%d" % index, beat=beat) for index in range(5)]
        late = make_process(root="late", beat=ago(10))
        sizes, ids = self._ids(beat - timedelta(seconds=1), 0, ago(300), page_size=2)
        self.assertEqual(sizes, [2, 2, 1])
        self.assertEqual(ids, [process.id for process in processes])
        self.assertNotIn(late.id, ids)

    def test_resume_from_last_row_after_cap(self):
        beat = ago(600)
        processes = [make_process(root="r%d" % index, beat=beat) for index in range(3)]
        _sizes, first = self._ids(beat - timedelta(seconds=1), 0, ago(300), max_rows=2)
        self.assertEqual(first, [processes[0].id, processes[1].id])
        _sizes, rest = self._ids(beat, processes[1].id, ago(300))
        self.assertEqual(rest, [processes[2].id])

    def test_exhausted_position_skips_rows_on_the_boundary(self):
        beat = ago(600)
        make_process(root="edge", beat=beat)
        _sizes, ids = self._ids(beat, EXHAUSTED_ID, ago(300))
        self.assertEqual(ids, [])
