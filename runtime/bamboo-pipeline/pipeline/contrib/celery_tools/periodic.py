# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
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
