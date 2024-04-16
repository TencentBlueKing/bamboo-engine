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

import logging
import traceback

from celery import current_app
from django.utils import timezone
from pipeline.component_framework.library import ComponentLibrary
from pipeline.conf.default_settings import PLUGIN_EXECUTE_QUEUE
from pipeline.contrib.plugin_execute.contants import State
from pipeline.contrib.plugin_execute.models import PluginExecuteTask
from pipeline.core.data.base import DataObject

logger = logging.getLogger("celery")


@current_app.task
def execute(task_id):
    try:
        plugin_execute_task = PluginExecuteTask.objects.get(id=task_id)
    except PluginExecuteTask.DoesNotExist:
        logger.exception("[plugin_execute] execute error, task not exist, task_id={}".format(task_id))
        return

    # 更新插件的状态
    plugin_execute_task.state = State.RUNNING
    plugin_execute_task.save(update_fields=["state"])

    # 封装data
    data = DataObject(inputs=plugin_execute_task.inputs, outputs={})
    parent_data = DataObject(inputs=plugin_execute_task.contexts, outputs={})

    try:
        # 获取 component
        comp_cls = ComponentLibrary.get_component_class(plugin_execute_task.component_code, plugin_execute_task.version)
        # 获取service
        service = comp_cls.bound_service(name=plugin_execute_task.runtime_attrs.get("name", None))

        # 封装运行时
        service.setup_runtime_attrs(**plugin_execute_task.runtime_attrs, logger=logger)
        execute_success = service.execute(data, parent_data)
        # 在 pipeline 中，如果插件返回为None,则表示成功
        if execute_success is None:
            execute_success = True
        plugin_execute_task.outputs = data.outputs
        plugin_execute_task.save()
    except Exception as e:
        # 处理异常情况
        ex_data = traceback.format_exc()
        data.outputs.ex_data = ex_data
        logger.exception("[plugin_execute] plugin execute failed, err={}".format(e))
        plugin_execute_task.outputs = data.outputs
        plugin_execute_task.state = State.FAILED
        plugin_execute_task.save()
        return

    # 单纯的执行失败, 更新状态和输出信息
    if not execute_success:
        plugin_execute_task.state = State.FAILED
        plugin_execute_task.save()
        return

    # 执行成功, 需要判断是否需要调度
    need_schedule = service.need_schedule()
    if not need_schedule:
        plugin_execute_task.state = State.FINISHED
        plugin_execute_task.finish_at = timezone.now()
        plugin_execute_task.save()
        return

    # 需要调度，则调度自身
    if service.interval:
        schedule.apply_async(
            kwargs={"task_id": task_id},
            queue=PLUGIN_EXECUTE_QUEUE,
            countdown=service.interval.next(),
            ignore_result=True,
        )


@current_app.task
def schedule(task_id):
    try:
        plugin_execute_task = PluginExecuteTask.objects.get(id=task_id)
    except PluginExecuteTask.DoesNotExist:
        logger.exception("[plugin_execute] schedule error, task not exist, task_id={}".format(task_id))
        return

    # 只有处于运行状态的节点才允许被调度
    if plugin_execute_task.state != State.RUNNING:
        logger.exception("[plugin_execute] schedule error, task not exist, task_id={}".format(task_id))
        return

    data = DataObject(inputs=plugin_execute_task.inputs, outputs=plugin_execute_task.outputs)
    parent_data = DataObject(inputs=plugin_execute_task.contexts, outputs={})

    try:
        comp_cls = ComponentLibrary.get_component_class(plugin_execute_task.component_code, plugin_execute_task.version)
        # 获取service
        service = comp_cls.bound_service(name=plugin_execute_task.runtime_attrs.get("name", None))
        # 封装运行时
        service.setup_runtime_attrs(**plugin_execute_task.runtime_attrs, logger=logger)
        schedule_success = service.schedule(
            data=data, parent_data=parent_data, callback_data=plugin_execute_task.callback_data
        )
        # 在 pipeline 中，如果插件返回为None,则表示成功
        if schedule_success is None:
            schedule_success = True
        plugin_execute_task.outputs = data.outputs
        plugin_execute_task.save()
    except Exception as e:
        # 处理异常情况
        ex_data = traceback.format_exc()
        data.outputs.ex_data = ex_data
        logger.exception("[plugin_execute] plugin execute failed, err={}".format(e))
        plugin_execute_task.outputs = data.outputs
        plugin_execute_task.state = State.FAILED
        plugin_execute_task.save()
        return

    if not schedule_success:
        plugin_execute_task.state = State.FAILED
        plugin_execute_task.save()
        return

    if service.is_schedule_finished():
        plugin_execute_task.state = State.FINISHED
        plugin_execute_task.finish_at = timezone.now()
        plugin_execute_task.save()
        return

    # 还需要下一次的调度
    # 需要调度，则调度自身
    if service.interval:
        schedule.apply_async(
            kwargs={"task_id": task_id},
            queue=PLUGIN_EXECUTE_QUEUE,
            countdown=service.interval.next(),
            ignore_result=True,
        )
