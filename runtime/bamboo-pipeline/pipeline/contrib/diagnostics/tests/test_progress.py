# -*- coding: utf-8 -*-

from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from pipeline.contrib.diagnostics import progress
from pipeline.eri.models import Process


def _proc(root, dead=False, beat=None, node="n"):
    p = Process.objects.create(
        root_pipeline_id=root,
        current_node_id=node,
        destination_id="",
        priority=1,
        queue="diagnostics",
        pipeline_stack="[]",
        dead=dead,
    )
    if beat is not None:
        Process.objects.filter(id=p.id).update(last_heartbeat=beat)
    return p


class ProgressTest(TransactionTestCase):
    def tearDown(self):
        Process.objects.all().delete()
        super(ProgressTest, self).tearDown()

    def test_stalled_roots_only_return_old_and_alive(self):
        now = timezone.now()
        _proc("root-stuck", beat=now - timedelta(seconds=3600))
        _proc("root-fresh", beat=now - timedelta(seconds=10))
        _proc("root-dead", dead=True, beat=now - timedelta(seconds=3600))

        roots = [r for r, _ in progress.stalled_root_candidates(1800, 100, now=now)]
        self.assertIn("root-stuck", roots)
        self.assertNotIn("root-fresh", roots)
        self.assertNotIn("root-dead", roots)

    def test_root_max_hides_when_any_branch_fresh(self):
        now = timezone.now()
        _proc("root-multi", beat=now - timedelta(seconds=3600))
        _proc("root-multi", beat=now - timedelta(seconds=5))
        roots = [r for r, _ in progress.stalled_root_candidates(1800, 100, now=now)]
        self.assertNotIn("root-multi", roots)  # M1 已知限制：root 级 Max 掩盖单条卡住分支

    def test_candidates_sorted_recently_stalled_first(self):
        now = timezone.now()
        _proc("root-a", beat=now - timedelta(seconds=2000))
        _proc("root-b", beat=now - timedelta(seconds=5000))
        roots = [r for r, _ in progress.stalled_root_candidates(1800, 100, now=now)]
        self.assertEqual(roots[0], "root-a")  # 刚跨过阈值的优先，避免历史积压占满 batch

    def test_max_silent_seconds_excludes_ancient_roots(self):
        now = timezone.now()
        _proc("root-recent", beat=now - timedelta(seconds=3600))
        _proc("root-ancient", beat=now - timedelta(days=400))

        roots = [r for r, _ in progress.stalled_root_candidates(1800, 100, now=now, max_silent_seconds=7 * 24 * 3600)]
        self.assertEqual(roots, ["root-recent"])

    def test_ancient_roots_kept_when_bound_disabled(self):
        now = timezone.now()
        _proc("root-ancient", beat=now - timedelta(days=400))

        roots = [r for r, _ in progress.stalled_root_candidates(1800, 100, now=now, max_silent_seconds=0)]
        self.assertEqual(roots, ["root-ancient"])

    def test_batch_is_not_exhausted_by_ancient_roots(self):
        """上界的核心目的：历史积压不再挤掉刚静默的 root。"""
        now = timezone.now()
        for index in range(3):
            _proc("root-ancient-{}".format(index), beat=now - timedelta(days=300 + index))
        _proc("root-new", beat=now - timedelta(seconds=1900))

        roots = [r for r, _ in progress.stalled_root_candidates(1800, 1, now=now, max_silent_seconds=7 * 24 * 3600)]
        self.assertEqual(roots, ["root-new"])

    def test_root_last_progress(self):
        now = timezone.now()
        _proc("root-x", beat=now - timedelta(seconds=100))
        self.assertIsNotNone(progress.root_last_progress("root-x"))
        self.assertIsNone(progress.root_last_progress("root-none"))
