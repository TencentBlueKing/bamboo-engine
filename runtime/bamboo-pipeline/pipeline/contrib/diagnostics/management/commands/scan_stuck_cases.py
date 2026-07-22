# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from pipeline.contrib.diagnostics.scanner import scan_stalled_roots


class Command(BaseCommand):
    help = "Scan live ERI roots for stall and upsert stuck diagnostic cases."

    def add_arguments(self, parser):
        parser.add_argument("--threshold", dest="threshold", type=int, default=None)
        parser.add_argument("--batch", dest="batch", type=int, default=None)
        parser.add_argument("--confirm", dest="confirm", type=int, default=None)

    def handle(self, *args, **options):
        cases = scan_stalled_roots(
            threshold_seconds=options.get("threshold"),
            batch=options.get("batch"),
            confirm_seconds=options.get("confirm"),
        )
        self.stdout.write("upserted cases: {}".format(len(cases)))
