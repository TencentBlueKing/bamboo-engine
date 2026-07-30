# -*- coding: utf-8 -*-
from django.apps import AppConfig


class ReliableEventsConfig(AppConfig):
    name = "pipeline.contrib.reliable_events"
    label = "pipeline_reliable_events"
    verbose_name = "PipelineContribReliableEvents"

    def ready(self):
        try:
            from pipeline.contrib.reliable_events import tasks  # noqa
        except Exception:  # celery 未装/未配时不阻断 app 加载
            pass
