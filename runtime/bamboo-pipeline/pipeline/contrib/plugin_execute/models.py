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

from django.db import models
from django.utils.translation import ugettext_lazy as _
from pipeline.contrib.fields import SerializerField


class ScheduleManger(models.Manager):
    def apply_schedule_lock(self, task_id: int) -> bool:
        """
        获取 Schedule 对象的调度锁，返回是否成功获取锁

        :return: True or False
        """
        return self.filter(id=task_id, scheduling=False).update(scheduling=True) == 1

    def release_schedule_lock(self, task_id: int) -> None:
        """
        释放指定 Schedule 的调度锁
        :return:
        """
        self.filter(id=task_id, scheduling=True).update(scheduling=False)


class ScheduleLock(object):
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.locked = False

    def __enter__(self):
        self.locked = PluginExecuteTask.objects.apply_schedule_lock(self.task_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.locked:
            PluginExecuteTask.objects.release_schedule_lock(self.task_id)


def get_schedule_lock(task_id: int) -> ScheduleLock:
    """
    获取 schedule lock 的 context 对象
    :param task_id:
    :return:
    """
    return ScheduleLock(task_id)


class PluginExecuteTask(models.Model):
    """
    单节点执行任务
    """

    state = models.CharField(_("状态名"), null=False, max_length=64)
    invoke_count = models.IntegerField("invoke count", default=1)
    component_code = models.CharField(_("组件编码"), max_length=255, db_index=True)
    version = models.CharField(_("插件版本"), max_length=255, default="legacy")
    inputs = SerializerField(verbose_name=_("node inputs"), default={})
    outputs = SerializerField(verbose_name=_("node outputs"), default={})
    callback_data = SerializerField(verbose_name=_("callback data"), default={})
    contexts = SerializerField(verbose_name=_("pipeline context values"), default={})
    runtime_attrs = SerializerField(verbose_name=_("runtime attr"), default={})
    scheduling = models.BooleanField("是否正在调度", default=False, db_index=True)
    created_at = models.DateTimeField("create time", auto_now_add=True)
    finish_at = models.DateTimeField("finish time", null=True)

    objects = ScheduleManger()

    class Meta:
        indexes = [models.Index(fields=["id", "scheduling"])]
