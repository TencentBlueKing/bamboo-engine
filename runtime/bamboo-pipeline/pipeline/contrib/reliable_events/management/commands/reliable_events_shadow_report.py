# -*- coding: utf-8 -*-
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from pipeline.contrib.reliable_events import metrics


class Command(BaseCommand):
    help = "Report reliable-event shadow stats (coverage / mismatch)."

    def add_arguments(self, parser):
        parser.add_argument("--since-hours", type=int, default=None)

    def handle(self, *args, **options):
        since = None
        if options.get("since_hours"):
            since = timezone.now() - timedelta(hours=options["since_hours"])
        stats = metrics.shadow_stats(since=since)
        metrics.emit_shadow_report(stats)
        self.stdout.write(
            "total={} applied={} obsolete={} mismatch={} pending={}".format(
                stats["total"], stats["applied"], stats["obsolete"], stats["mismatch"], stats["pending"]
            )
        )
