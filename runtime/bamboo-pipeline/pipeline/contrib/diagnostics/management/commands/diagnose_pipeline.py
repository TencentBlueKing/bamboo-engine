# -*- coding: utf-8 -*-

import json

from django.core.management.base import BaseCommand

from pipeline.contrib.diagnostics.scanner import diagnose_pipeline


class Command(BaseCommand):
    help = "Diagnose one pipeline runtime snapshot."

    def add_arguments(self, parser):
        parser.add_argument("root_pipeline_id", nargs="?", default="")
        parser.add_argument("--node-id", dest="node_id", default="")
        parser.add_argument("--process-id", dest="process_id", type=int, default=None)

    def handle(self, *args, **options):
        hits = diagnose_pipeline(
            root_pipeline_id=options.get("root_pipeline_id") or "",
            node_id=options.get("node_id") or "",
            process_id=options.get("process_id"),
        )
        self.stdout.write(
            json.dumps([hit._asdict() for hit in hits], ensure_ascii=False, indent=2, sort_keys=True)
        )
