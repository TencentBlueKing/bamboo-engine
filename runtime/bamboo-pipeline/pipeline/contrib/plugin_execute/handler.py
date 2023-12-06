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

from pipeline.conf.default_settings import PLUGIN_EXECUTE_QUEUE
from pipeline.contrib.exceptions import PluginExecuteException
from pipeline.contrib.plugin_execute.contants import State
from pipeline.contrib.plugin_execute.models import PluginExecuteTask, get_schedule_lock
from pipeline.contrib.plugin_execute.tasks import execute, schedule

logger = logging.getLogger("celery")


def _retry_once(action: callable):
    try:
        action()
    except Exception:
        try:
            action()
        except Exception as e:
            raise e


class PluginExecuteHandler:
    @classmethod
    def run(cls, component_code: str, version: str, inputs: dict, contexts: dict, runtime_attrs: dict = None):
        if runtime_attrs is None:
            runtime_attrs = {}

        if not (isinstance(inputs, dict) and isinstance(contexts, dict) and isinstance(runtime_attrs, dict)):
            raise PluginExecuteException("[plugin_execute_run] error, the inputs, contexts, runtime_attrs must be dict")
        plugin_execute_task = PluginExecuteTask.objects.create(
            state=State.READY,
            inputs=inputs,
            version=version,
            component_code=component_code,
            contexts=contexts,
            runtime_attrs=runtime_attrs,
        )

        def action():
            # 发送执行任务
            execute.apply_async(
                kwargs={"task_id": plugin_execute_task.id}, queue=PLUGIN_EXECUTE_QUEUE, ignore_result=True
            )
            logger.info(
                "[plugin_execute_run] send execute task, plugin_execute_task_id = {}".format(plugin_execute_task.id)
            )

        try:
            _retry_once(action=action)
        except Exception as e:
            # 如果任务启动出现异常，则删除任务
            plugin_execute_task.delete()
            raise e

        return plugin_execute_task.id

    @classmethod
    def get_state(cls, task_id):
        """
        获取任务状态
        @param task_id:
        @return:
        """
        # 直接抛出异常让上层去捕获
        plugin_execute_task = PluginExecuteTask.objects.get(id=task_id)
        return {
            "task_id": plugin_execute_task.id,
            "state": plugin_execute_task.state,
            "component_code": plugin_execute_task.component_code,
            "version": plugin_execute_task.version,
            "invoke_count": plugin_execute_task.invoke_count,
            "inputs": plugin_execute_task.inputs,
            "outputs": plugin_execute_task.outputs,
            "callback_data": plugin_execute_task.callback_data,
            "contexts": plugin_execute_task.contexts,
            "runtime_attrs": plugin_execute_task.runtime_attrs,
            "create_at": plugin_execute_task.created_at,
            "finish_at": plugin_execute_task.finish_at,
        }

    @classmethod
    def forced_fail(cls, task_id):
        plugin_execute_task = PluginExecuteTask.objects.get(id=task_id)
        if plugin_execute_task.state != State.RUNNING:
            raise PluginExecuteException(
                "[forced_fail] error, the plugin_execute_task.state is not RUNNING, state={}".format(
                    plugin_execute_task.state
                )
            )
        # 插件状态改成 FAILED, 在schdule会自动停止
        plugin_execute_task.state = State.FAILED
        plugin_execute_task.save()

    @classmethod
    def callback(cls, task_id: int, callback_data: dict = None):

        if callback_data is None:
            callback_data = {}

        if not isinstance(callback_data, dict):
            raise PluginExecuteException("[plugin_execute_callback] error, the callback must be dict")

        plugin_execute_task = PluginExecuteTask.objects.get(id=task_id)
        if plugin_execute_task.state != State.RUNNING:
            raise PluginExecuteException(
                "[callback] error, the plugin_execute_task.state is not RUNNING, state={}".format(
                    plugin_execute_task.state
                )
            )

        def action():
            # 需要加锁，防止流程处在回调的过程中
            with get_schedule_lock(task_id) as locked:
                if not locked:
                    raise PluginExecuteException("[plugin_execute_callback] error, it`s have callback task, please try")
                plugin_execute_task.callback_data = callback_data
                plugin_execute_task.save()
                schedule.apply_async(
                    kwargs={"task_id": plugin_execute_task.id}, queue=PLUGIN_EXECUTE_QUEUE, ignore_result=True
                )
                logger.info("[plugin_execute_callback] send callback task, plugin_execute_task_id = {}".format(task_id))

        _retry_once(action=action)

    @classmethod
    def retry_node(cls, task_id: int, inputs: dict = None, contexts: dict = None, runtime_attrs: dict = None):

        plugin_execute_task = PluginExecuteTask.objects.get(id=task_id)
        if plugin_execute_task.state != State.FAILED:
            raise PluginExecuteException(
                "[retry_node] error, the plugin_execute_task.state is not FAILED, state={}".format(
                    plugin_execute_task.state
                )
            )

        if contexts and isinstance(contexts, dict):
            plugin_execute_task.contexts = contexts
        if inputs and isinstance(inputs, dict):
            plugin_execute_task.inputs = inputs
        if runtime_attrs and isinstance(runtime_attrs, dict):
            plugin_execute_task.runtime_attrs = runtime_attrs

        plugin_execute_task.state = State.READY
        plugin_execute_task.inputs = inputs
        plugin_execute_task.invoke_count += 1
        # 清空输出和callback_data
        plugin_execute_task.outputs = {}
        plugin_execute_task.callback_data = {}
        plugin_execute_task.save()

        def action():
            execute.apply_async(kwargs={"task_id": plugin_execute_task.id}, queue=PLUGIN_EXECUTE_QUEUE)
            logger.info(
                "[plugin_execute_retry_node] send retry_node task,  plugin_execute_task_id = {}".format(task_id)
            )

        _retry_once(action=action)
