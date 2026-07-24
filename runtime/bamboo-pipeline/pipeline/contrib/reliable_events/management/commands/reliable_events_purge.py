# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from pipeline.contrib.reliable_events import purge


class Command(BaseCommand):
    help = "Purge finished reliable events beyond retention window."

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=None)

    def handle(self, *args, **options):
        deleted = purge.purge_finished_events(batch=options.get("batch"))
        self.stdout.write("purged {} finished reliable events".format(deleted))
