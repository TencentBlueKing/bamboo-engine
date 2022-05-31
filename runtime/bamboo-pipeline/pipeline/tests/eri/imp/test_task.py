# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from mock import patch, MagicMock

from django.test import TransactionTestCase

from pipeline.eri.imp.task import TaskMixin
from pipeline.eri.models import Process


class StateMixinTestCase(TransactionTestCase):
    def setUp(self) -> None:
        self.mixin = TaskMixin()
        return super().setUp()

    def test_execute__headers_is_none(self):
        celery_app = MagicMock()
        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async = MagicMock()
        time = MagicMock()
        time.time = MagicMock(return_value=1234)

        Process.objects.create(id=1, priority=100, queue="test")

        with patch("pipeline.eri.imp.task.current_app", celery_app):
            with patch("pipeline.eri.imp.task.time", time):
                self.mixin.execute(
                    process_id=1,
                    node_id="nid",
                    root_pipeline_id="root_id",
                    parent_pipeline_id="parent_id",
                )

        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async.assert_called_once_with(
            kwargs={
                "process_id": 1,
                "node_id": "nid",
                "root_pipeline_id": "root_id",
                "parent_pipeline_id": "parent_id",
                "recover_point": "{}",
                "headers": {"timestamp": 1234, "route_info": {"queue": "test", "priority": 100}},
            },
            queue="er_execute_test",
            priority=100,
            routing_key="er_execute_test",
        )

    def test_execute__headers_is_not_none(self):
        celery_app = MagicMock()
        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async = MagicMock()
        time = MagicMock()
        time.time = MagicMock(return_value=1234)

        with patch("pipeline.eri.imp.task.current_app", celery_app):
            with patch("pipeline.eri.imp.task.time", time):
                self.mixin.execute(
                    process_id=1,
                    node_id="nid",
                    root_pipeline_id="root_id",
                    parent_pipeline_id="parent_id",
                    headers={"route_info": {"queue": "test", "priority": 50}},
                )

        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async.assert_called_once_with(
            kwargs={
                "process_id": 1,
                "node_id": "nid",
                "root_pipeline_id": "root_id",
                "parent_pipeline_id": "parent_id",
                "recover_point": "{}",
                "headers": {"timestamp": 1234, "route_info": {"queue": "test", "priority": 50}},
            },
            queue="er_execute_test",
            priority=50,
            routing_key="er_execute_test",
        )

    def test_schedule__headers_is_none(self):
        celery_app = MagicMock()
        celery_app.tasks["pipeline.eri.celery.tasks.schedule"].apply_async = MagicMock()
        time = MagicMock()
        time.time = MagicMock(return_value=1234)

        Process.objects.create(id=1, priority=100, queue="test")

        with patch("pipeline.eri.imp.task.current_app", celery_app):
            with patch("pipeline.eri.imp.task.time", time):
                self.mixin.schedule(
                    process_id=1,
                    node_id="nid",
                    schedule_id="schedule_id",
                )

        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async.assert_called_once_with(
            kwargs={
                "process_id": 1,
                "node_id": "nid",
                "schedule_id": "schedule_id",
                "callback_data_id": None,
                "recover_point": "{}",
                "headers": {"timestamp": 1234, "route_info": {"queue": "test", "priority": 100}},
            },
            queue="er_schedule_test",
            priority=100,
            routing_key="er_schedule_test",
        )

    def test_schedule__headers_is_not_none(self):
        celery_app = MagicMock()
        celery_app.tasks["pipeline.eri.celery.tasks.schedule"].apply_async = MagicMock()
        time = MagicMock()
        time.time = MagicMock(return_value=1234)

        with patch("pipeline.eri.imp.task.current_app", celery_app):
            with patch("pipeline.eri.imp.task.time", time):
                self.mixin.schedule(
                    process_id=1,
                    node_id="nid",
                    schedule_id="schedule_id",
                    headers={"route_info": {"queue": "test", "priority": 50}},
                )

        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async.assert_called_once_with(
            kwargs={
                "process_id": 1,
                "node_id": "nid",
                "schedule_id": "schedule_id",
                "callback_data_id": None,
                "recover_point": "{}",
                "headers": {"timestamp": 1234, "route_info": {"queue": "test", "priority": 50}},
            },
            queue="er_schedule_test",
            priority=50,
            routing_key="er_schedule_test",
        )

    def test_set_schedule__headers_is_none(self):
        celery_app = MagicMock()
        celery_app.tasks["pipeline.eri.celery.tasks.schedule"].apply_async = MagicMock()
        time = MagicMock()
        time.time = MagicMock(return_value=1234)

        Process.objects.create(id=1, priority=100, queue="test")

        with patch("pipeline.eri.imp.task.current_app", celery_app):
            with patch("pipeline.eri.imp.task.time", time):
                self.mixin.set_next_schedule(
                    process_id=1,
                    node_id="nid",
                    schedule_id="schedule_id",
                    schedule_after=1000,
                )

        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async.assert_called_once_with(
            kwargs={
                "process_id": 1,
                "node_id": "nid",
                "schedule_id": "schedule_id",
                "callback_data_id": None,
                "recover_point": "{}",
                "headers": {"timestamp": 2234, "route_info": {"queue": "test", "priority": 100}},
            },
            countdown=1000,
            queue="er_schedule_test",
            priority=100,
            routing_key="er_schedule_test",
        )

    def test_set_schedule__headers_is_not_none(self):
        celery_app = MagicMock()
        celery_app.tasks["pipeline.eri.celery.tasks.schedule"].apply_async = MagicMock()
        time = MagicMock()
        time.time = MagicMock(return_value=1234)

        with patch("pipeline.eri.imp.task.current_app", celery_app):
            with patch("pipeline.eri.imp.task.time", time):
                self.mixin.set_next_schedule(
                    process_id=1,
                    node_id="nid",
                    schedule_id="schedule_id",
                    schedule_after=1000,
                    headers={"route_info": {"queue": "test", "priority": 50}},
                )

        celery_app.tasks["pipeline.eri.celery.tasks.execute"].apply_async.assert_called_once_with(
            kwargs={
                "process_id": 1,
                "node_id": "nid",
                "schedule_id": "schedule_id",
                "callback_data_id": None,
                "recover_point": "{}",
                "headers": {"timestamp": 2234, "route_info": {"queue": "test", "priority": 50}},
            },
            countdown=1000,
            queue="er_schedule_test",
            priority=50,
            routing_key="er_schedule_test",
        )
