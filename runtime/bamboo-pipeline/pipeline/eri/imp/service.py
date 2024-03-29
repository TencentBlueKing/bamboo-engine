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
import typing
from typing import Callable, Optional

from pipeline.core.data.base import DataObject
from pipeline.core.flow.activity import Service
from pipeline.eri.log import get_logger
from pipeline.eri.signals import pre_service_execute, pre_service_schedule

from bamboo_engine.eri import (
    CallbackData,
    ExecutionData,
    HookType,
    Schedule,
    ScheduleType,
)
from bamboo_engine.eri import Service as ServiceInterface


class ServiceWrapper(ServiceInterface):
    def __init__(self, service: Service):
        self.service = service

    def execute(self, data: ExecutionData, root_pipeline_data: ExecutionData) -> bool:
        """
        execute 逻辑

        :param data: 节点执行数据
        :type data: ExecutionData
        :param root_pipeline_data: 根流程执行数据
        :type root_pipeline_data: ExecutionData
        :return: 是否执行成功
        :rtype: bool
        """
        data_obj = DataObject(inputs=data.inputs, outputs=data.outputs)
        parent_data_obj = DataObject(inputs=root_pipeline_data.inputs, outputs=root_pipeline_data.outputs)

        pre_service_execute.send(
            sender=ServiceWrapper, service=self.service, data=data_obj, parent_data=parent_data_obj
        )

        try:
            execute_res = self.service.execute(data_obj, parent_data_obj)
        finally:
            # sync data object modification to execution data
            data.inputs = data_obj.inputs
            data.outputs = data_obj.outputs

        if execute_res is None:
            execute_res = True

        return execute_res

    def hook_dispatch(
        self,
        hook: HookType,
        data: ExecutionData,
        root_pipeline_data: ExecutionData,
        callback_data: Optional[CallbackData] = None,
    ) -> bool:
        """
        hook 分发逻辑
        :param hook: 钩子
        :type hook: HookType
        :param data: 节点执行数据
        :type data: ExecutionData
        :param root_pipeline_data: 根流程执行数据
        :type root_pipeline_data: ExecutionData
        :param callback_data: 回调数据, defaults to None
        :type callback_data: Optional[CallbackData], optional
        :return: [description]
        :rtype: bool
        """
        data_obj = DataObject(inputs=data.inputs, outputs=data.outputs)
        parent_data_obj = DataObject(inputs=root_pipeline_data.inputs, outputs=root_pipeline_data.outputs)

        hook_res: Optional[bool] = False

        call_params: typing.Dict[str, typing.Any] = {"data": data_obj, "parent_data": parent_data_obj}
        if callback_data is not None:
            call_params["callback_data"] = callback_data
        try:
            hook_func: Optional[Callable[..., bool]] = getattr(self.service, hook.value, None)
            if hook_func:
                hook_res = hook_func(**call_params)
        finally:
            data.inputs = data_obj.inputs
            data.outputs = data_obj.outputs

        if hook_res is None:
            hook_res = True
        return hook_res

    def schedule(
        self,
        schedule: Schedule,
        data: ExecutionData,
        root_pipeline_data: ExecutionData,
        callback_data: Optional[CallbackData] = None,
    ) -> bool:
        """
        schedule 逻辑

        :param schedule: Schedule 对象
        :type schedule: Schedule
        :param data: 节点执行数据
        :type data: ExecutionData
        :param root_pipeline_data: 根流程执行数据
        :type root_pipeline_data: ExecutionData
        :param callback_data: 回调数据, defaults to None
        :type callback_data: Optional[CallbackData], optional
        :return: [description]
        :rtype: bool
        """
        data_obj = DataObject(inputs=data.inputs, outputs=data.outputs)
        parent_data_obj = DataObject(inputs=root_pipeline_data.inputs, outputs=root_pipeline_data.outputs)

        pre_service_schedule.send(
            sender=ServiceWrapper,
            service=self.service,
            data=data_obj,
            parent_data=parent_data_obj,
            callback_data=callback_data,
        )

        try:
            schedule_res = self.service.schedule(
                data_obj, parent_data_obj, callback_data.data if callback_data else None
            )
        except Exception as e:
            raise e
        finally:
            # sync data object modification to execution data
            data.inputs = data_obj.inputs
            data.outputs = data_obj.outputs

        if schedule_res is None:
            schedule_res = True

        return schedule_res

    def need_schedule(self) -> bool:
        """
        服务是否需要调度

        :return: 是否需要调度
        :rtype: bool
        """
        return self.service.need_schedule()

    def need_run_hook(self) -> bool:
        return self.service.need_run_hook()

    def schedule_type(self) -> Optional[ScheduleType]:
        """
        服务调度类型

        :return: 调度类型
        :rtype: Optional[ScheduleType]
        """
        if not self.service.need_schedule():
            return None

        if self.service.interval:
            return ScheduleType.POLL

        if not self.service.multi_callback_enabled():
            return ScheduleType.CALLBACK

        return ScheduleType.MULTIPLE_CALLBACK

    def is_schedule_done(self) -> bool:
        """
        调度是否完成

        :return: 调度是否完成
        :rtype: bool
        """
        return self.service.is_schedule_finished()

    def schedule_after(
        self, schedule: Optional[Schedule], data: ExecutionData, root_pipeline_data: ExecutionData
    ) -> int:
        """
        计算下一次调度间隔

        :param schedule: 调度对象，未进行调度时传入为空
        :type schedule: Optional[Schedule]
        :param data: 节点执行数据
        :type data: ExecutionData
        :param root_pipeline_data: 根流程执行数据
        :type root_pipeline_data: ExecutionData
        :return: 调度间隔，单位为秒
        :rtype: int
        """
        if self.service.interval is None:
            return -1

        if schedule is None:
            return self.service.interval.next()

        # count will add in next, so minus 1 at here
        self.service.interval.count = schedule.times - 1

        return self.service.interval.next()

    def setup_runtime_attributes(self, **attrs):
        """
        装载运行时属性

        :param attrs: 运行时属性
        :type attrs: Dict[str, Any]
        """

        attrs["logger"] = get_logger(node_id=attrs["id"], loop=attrs["loop"], version=attrs["version"])
        self.service.setup_runtime_attrs(**attrs)
