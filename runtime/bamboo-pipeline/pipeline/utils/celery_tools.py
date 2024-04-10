# -*- coding: utf-8 -*-
from celery import Task, current_app
from celery.schedules import maybe_schedule


class PipelinePeriodicTask(Task):
    """A task that adds itself to the :setting:`beat_schedule` setting."""

    abstract = True
    ignore_result = True
    relative = False
    options = None
    compat = True

    def __init__(self):
        if not hasattr(self, 'run_every'):
            raise NotImplementedError(
                'Periodic tasks must have a run_every attribute')
        self.run_every = maybe_schedule(self.run_every, self.relative)
        super(PipelinePeriodicTask, self).__init__()

    @classmethod
    def on_bound(cls, app):
        app.conf.beat_schedule[cls.name] = {
            'task': cls.name,
            'schedule': cls.run_every,
            'args': (),
            'kwargs': {},
            'options': cls.options or {},
            'relative': cls.relative,
        }


def periodic_task(*args, **options):
    """Deprecated decorator, please use :setting:`beat_schedule`."""
    return current_app.task(**dict({'base': PipelinePeriodicTask}, **options))

