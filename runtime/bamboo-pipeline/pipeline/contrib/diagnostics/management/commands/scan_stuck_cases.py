# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from pipeline.contrib.diagnostics.scanner import scan_open_processes


class Command(BaseCommand):
    help = "Scan live ERI processes and upsert stuck diagnostic cases."

    def add_arguments(self, parser):
        parser.add_argument("--limit", dest="limit", type=int, default=100)

    def handle(self, *args, **options):
        cases = scan_open_processes(limit=options.get("limit", 100))
        self.stdout.write("upserted cases: {}".format(len(cases)))
