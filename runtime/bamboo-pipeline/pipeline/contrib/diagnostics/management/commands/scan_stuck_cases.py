# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from pipeline.contrib.diagnostics.scanner import scan_stalled_roots


class Command(BaseCommand):
    help = "Scan live ERI roots for stall and upsert stuck diagnostic cases."

    def add_arguments(self, parser):
        parser.add_argument("--threshold", dest="threshold", type=int, default=None)
        parser.add_argument("--batch", dest="batch", type=int, default=None)
        parser.add_argument("--confirm", dest="confirm", type=int, default=None)
        parser.add_argument(
            "--max-silent",
            dest="max_silent",
            type=int,
            default=None,
            help="静默上界（秒），0 表示不设上界，用于一次性回扫历史积压",
        )

    def handle(self, *args, **options):
        cases = scan_stalled_roots(
            threshold_seconds=options.get("threshold"),
            batch=options.get("batch"),
            confirm_seconds=options.get("confirm"),
            max_silent_seconds=options.get("max_silent"),
        )
        self.stdout.write("upserted cases: {}".format(len(cases)))
