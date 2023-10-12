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
from typing import Any, Dict, List, Optional, Set

from bamboo_engine import metrics, states
from bamboo_engine.config import Settings
from bamboo_engine.context import Context
from bamboo_engine.eri import (
    CallbackData,
    ContextValue,
    ContextValueType,
    Data,
    ExecuteInterruptPoint,
    ExecutionData,
    FancyDict,
    HookType,
    NodeType,
    ProcessInfo,
    Schedule,
    ScheduleType,
    Service,
)
from bamboo_engine.eri.models.interrupt import ScheduleInterruptPoint
from bamboo_engine.handler import (
    ExecuteResult,
    NodeHandler,
    ScheduleResult,
    register_handler,
)
from bamboo_engine.interrupt import ExecuteKeyPoint, ScheduleKeyPoint
from bamboo_engine.metrics import (
    ENGINE_EXECUTE_EXCEPTION_COUNT,
    ENGINE_EXECUTE_FAILED_COUNT,
    ENGINE_SCHEDULE_EXCEPTION_COUNT,
    ENGINE_SCHEDULE_FAILED_COUNT,
)
from bamboo_engine.template import Template

logger = logging.getLogger("bamboo_engine")


@register_handler(NodeType.ServiceActivity)
class ServiceActivityHandler(NodeHandler):
    """
    其中所有 set_state 调用都会传入 state version 来确保能够在用户强制失败节点后放弃后续无效的任务执行
    """

    def prepare_data(
        self,
        process_info: ProcessInfo,
        loop: int,
        inner_loop: int,
    ) -> Dict[str, Any]:
        """
        准备执行数据
        :param process_info: 进程信息
        :param loop: 循环次数, 为 -1 时表示不设置
        :param inner_loop: 当前流程循环次数, 为 -1 时表示不设置
        :return:
        """

        top_pipeline_id: str = process_info.top_pipeline_id
        root_pipeline_id: str = process_info.root_pipeline_id

        data: Data = self.runtime.get_data(self.node.id)
        root_pipeline_inputs: Dict[str, Any] = self._get_plain_inputs(process_info.root_pipeline_id)
        need_render_inputs: Dict[str, Any] = data.need_render_inputs()
        render_escape_inputs: Dict[str, Any] = data.render_escape_inputs()

        logger.info(
            "root_pipeline[%s] node(%s) activity execute data: %s, root inputs: %s",
            root_pipeline_id,
            self.node.id,
            data,
            root_pipeline_inputs,
        )

        # resolve inputs context references
        inputs_refs: Set[str] = set(Template(need_render_inputs).get_reference())
        logger.info(
            "root_pipeline[%s] node(%s) activity original refs: %s",
            root_pipeline_id,
            self.node.id,
            inputs_refs,
        )

        # 获取直接或间接引用其他变量的键
        additional_refs: Set[str] = self.runtime.get_context_key_references(
            pipeline_id=top_pipeline_id, keys=inputs_refs
        )
        inputs_refs = inputs_refs.union(additional_refs)
        logger.info(
            "root_pipeline[%s] node(%s) activity final refs: %s",
            root_pipeline_id,
            self.node.id,
            inputs_refs,
        )

        # prepare context
        context_values: List[ContextValue] = self.runtime.get_context_values(
            pipeline_id=top_pipeline_id, keys=inputs_refs
        )

        # pre extract loop outputs
        loop_value = loop + Settings.RERUN_INDEX_OFFSET
        need_render_inputs[self.LOOP_KEY] = loop_value
        if self.LOOP_KEY in data.outputs:
            loop_output_key = data.outputs[self.LOOP_KEY]
            context_values.append(ContextValue(key=loop_output_key, type=ContextValueType.PLAIN, value=loop_value))

        # pre extract inner_loop outputs
        inner_loop_value = inner_loop + Settings.RERUN_INDEX_OFFSET
        need_render_inputs[self.INNER_LOOP_KEY] = inner_loop_value
        if self.INNER_LOOP_KEY in data.outputs:
            inner_loop_output_key = data.outputs[self.INNER_LOOP_KEY]
            context_values.append(
                ContextValue(
                    key=inner_loop_output_key,
                    type=ContextValueType.PLAIN,
                    value=inner_loop_value,
                )
            )

        logger.info(
            "root_pipeline[%s] node(%s) activity context values: %s",
            root_pipeline_id,
            self.node.id,
            context_values,
        )

        context: Context = Context(self.runtime, context_values, root_pipeline_inputs)

        return {
            "context": context,
            "data": data,
            "need_render_inputs": need_render_inputs,
            "render_escape_inputs": render_escape_inputs,
            "root_pipeline_inputs": root_pipeline_inputs,
        }

    def execute(
        self,
        process_info: ProcessInfo,
        loop: int,
        inner_loop: int,
        version: str,
        recover_point: Optional[ExecuteInterruptPoint] = None,
    ) -> ExecuteResult:
        """
        节点的 execute 处理逻辑
        :param process_info: 进程信息
        :param loop: 循环次数, 为 -1 时表示不设置
        :param inner_loop: 当前流程循环次数, 为 -1 时表示不设置
        :param version: 目标状态版本
        :param recover_point:
        :return:
        """

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_PRE_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            top_pipeline_id = process_info.top_pipeline_id
            root_pipeline_id = process_info.root_pipeline_id

            run_data: Dict[str, Any] = self.prepare_data(process_info, loop, inner_loop)
            context: Context = run_data["context"]
            data: Data = run_data["data"]
            need_render_inputs: Dict[str, Any] = run_data["need_render_inputs"]
            render_escape_inputs: Dict[str, Any] = run_data["render_escape_inputs"]
            root_pipeline_inputs: Dict[str, Any] = run_data["root_pipeline_inputs"]

            # hydrate will call user code, use try to catch unexpected error
            try:
                hydrated_context = context.hydrate(deformat=True)
            except Exception as e:
                logger.exception(
                    "root_pipeline[%s] node(%s) activity context hydrate error",
                    root_pipeline_id,
                    self.node.id,
                )
                service_data = ExecutionData(inputs=data.plain_inputs(), outputs={})
                service_data.outputs.ex_data = "inputs hydrate failed(%s), check node log for details" % e
                service_data.outputs._result = False
                service_data.outputs._loop = loop
                service_data.outputs._inner_loop = inner_loop

                self.runtime.set_execution_data(node_id=self.node.id, data=service_data)
                self.runtime.set_state(
                    node_id=self.node.id,
                    version=version,
                    to_state=states.FAILED,
                    set_archive_time=True,
                    ignore_boring_set=recover_point is not None,
                )
                return ExecuteResult(
                    should_sleep=True,
                    schedule_ready=False,
                    schedule_type=None,
                    schedule_after=-1,
                    dispatch_processes=[],
                    next_node_id=None,
                )

            logger.info(
                "root_pipeline[%s] node(%s) actvity hydrated context: %s",
                root_pipeline_id,
                self.node.id,
                hydrated_context,
            )

            # resolve inputs
            execute_inputs = Template(need_render_inputs).render(hydrated_context)
            execute_inputs.update(render_escape_inputs)

            # data prepare
            service_data = ExecutionData(inputs=execute_inputs, outputs={})
            root_pipeline_data = ExecutionData(inputs=root_pipeline_inputs, outputs={})

            # execute
            service = self.runtime.get_service(code=self.node.code, version=self.node.version, name=self.node.name)
            service.setup_runtime_attributes(
                id=self.node.id,
                version=version,
                top_pipeline_id=top_pipeline_id,
                root_pipeline_id=root_pipeline_id,
                loop=loop,
                inner_loop=inner_loop,
            )

        # excute
        logger.debug(
            "root_pipeline[%s] node(%s) service data before execute: %s",
            self.node.id,
            root_pipeline_id,
            service_data,
        )
        logger.debug(
            "root_pipeline[%s] node(%s) root pipeline data before execute: %s",
            self.node.id,
            root_pipeline_id,
            root_pipeline_data,
        )
        # build_node_type: sleep_timer_legacy
        node_type = "{}_{}".format(self.node.code, self.node.version)
        # try recover from executed recover point
        execute_success = False
        if recover_point and recover_point.handler_data.service_executed:
            execute_success = not recover_point.handler_data.service_execute_fail
            service_data.outputs = FancyDict(
                self.runtime.deserialize_execution_data(
                    recover_point.handler_data.execute_serialize_outputs,
                    recover_point.handler_data.execute_outputs_serializer,
                )
            )
        else:
            self.runtime.node_enter(root_pipeline_id=root_pipeline_id, node_id=self.node.id)
            self.hook_dispatch(
                hook=HookType.NODE_ENTER,
                root_pipeline_id=root_pipeline_id,
                service=service,
                service_data=service_data,
                root_pipeline_data=root_pipeline_data,
            )
            try:
                execute_success = service.execute(data=service_data, root_pipeline_data=root_pipeline_data)
            except Exception:
                ENGINE_EXECUTE_EXCEPTION_COUNT.labels(type=node_type, hostname=self._hostname).inc()
                ex_data = traceback.format_exc()
                service_data.outputs.ex_data = ex_data
                logger.warning("root_pipeline[%s]service execute fail: %s", process_info.root_pipeline_id, ex_data)
                self.runtime.node_execute_exception(root_pipeline_id, self.node.id, ex_data=ex_data)
                self.hook_dispatch(
                    hook=HookType.NODE_EXECUTE_EXCEPTION,
                    root_pipeline_id=root_pipeline_id,
                    service=service,
                    service_data=service_data,
                    root_pipeline_data=root_pipeline_data,
                )
            logger.debug("root_pipeline[%s] service data after execute: %s", root_pipeline_id, service_data)

        if not execute_success:
            ENGINE_EXECUTE_FAILED_COUNT.labels(type=node_type, hostname=self._hostname).inc()

        with metrics.observe(
            metrics.ENGINE_NODE_EXECUTE_POST_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            serialize_outputs, outputs_serializer = self.runtime.serialize_execution_data(service_data.outputs)
            self.interrupter.check_and_set(
                ExecuteKeyPoint.SA_SERVICE_EXECUTE_DONE,
                service_executed=True,
                service_execute_fail=not execute_success,
                execute_serialize_outputs=serialize_outputs,
                execute_outputs_serializer=outputs_serializer,
                from_handler=True,
            )

            service_data.outputs._result = execute_success
            service_data.outputs._loop = loop
            service_data.outputs._inner_loop = inner_loop

            # execute success
            if execute_success:

                need_schedule = service.need_schedule()
                next_node_id = None

                if not need_schedule:
                    self.runtime.set_state(
                        node_id=self.node.id,
                        version=version,
                        to_state=states.FINISHED,
                        set_archive_time=True,
                        ignore_boring_set=recover_point is not None,
                    )

                    context.extract_outputs(
                        pipeline_id=top_pipeline_id,
                        data_outputs=data.outputs,
                        execution_data_outputs=service_data.outputs,
                    )
                    next_node_id = self.node.target_nodes[0]

                self.runtime.set_execution_data(node_id=self.node.id, data=service_data)

                return ExecuteResult(
                    should_sleep=need_schedule,
                    schedule_ready=need_schedule,
                    schedule_type=service.schedule_type(),
                    schedule_after=service.schedule_after(
                        schedule=None,
                        data=service_data,
                        root_pipeline_data=root_pipeline_data,
                    ),
                    dispatch_processes=[],
                    next_node_id=next_node_id,
                )

            if not self.node.error_ignorable:

                self.runtime.node_execute_fail(root_pipeline_id, self.node.id)
                self.hook_dispatch(
                    hook=HookType.NODE_EXECUTE_FAIL,
                    root_pipeline_id=root_pipeline_id,
                    service=service,
                    service_data=service_data,
                    root_pipeline_data=root_pipeline_data,
                )

                self.runtime.set_state(
                    node_id=self.node.id,
                    version=version,
                    to_state=states.FAILED,
                    set_archive_time=True,
                    ignore_boring_set=recover_point is not None,
                )

                self.runtime.set_execution_data(node_id=self.node.id, data=service_data)

                context.extract_outputs(
                    pipeline_id=top_pipeline_id,
                    data_outputs=data.outputs,
                    execution_data_outputs=service_data.outputs,
                )

                return ExecuteResult(
                    should_sleep=True,
                    schedule_ready=False,
                    schedule_type=None,
                    schedule_after=-1,
                    dispatch_processes=[],
                    next_node_id=None,
                )

            # execute failed and error ignore
            self.runtime.set_state(
                node_id=self.node.id,
                version=version,
                to_state=states.FINISHED,
                set_archive_time=True,
                error_ignored=True,
                ignore_boring_set=recover_point is not None,
            )

            self.runtime.set_execution_data(node_id=self.node.id, data=service_data)

            context.extract_outputs(
                pipeline_id=top_pipeline_id,
                data_outputs=data.outputs,
                execution_data_outputs=service_data.outputs,
            )

            return ExecuteResult(
                should_sleep=False,
                schedule_ready=False,
                schedule_type=None,
                schedule_after=-1,
                dispatch_processes=[],
                next_node_id=self.node.target_nodes[0],
            )

    def _finish_schedule(
        self,
        process_info: ProcessInfo,
        schedule: Schedule,
        data_outputs: dict,
        execution_data: ExecutionData,
        error_ignored: bool,
        root_pipeline_inputs: dict,
        recover_point: Optional[ScheduleInterruptPoint] = None,
    ) -> ScheduleResult:
        self.runtime.set_state(
            node_id=self.node.id,
            version=schedule.version,
            to_state=states.FINISHED,
            set_archive_time=True,
            error_ignored=error_ignored,
            ignore_boring_set=recover_point is not None,
        )

        context = Context(self.runtime, [], root_pipeline_inputs)
        context.extract_outputs(
            pipeline_id=process_info.top_pipeline_id,
            data_outputs=data_outputs,
            execution_data_outputs=execution_data.outputs,
        )

        return ScheduleResult(
            has_next_schedule=False,
            schedule_after=-1,
            schedule_done=True,
            next_node_id=self.node.target_nodes[0],
        )

    def schedule(
        self,
        process_info: ProcessInfo,
        loop: int,
        inner_loop: int,
        schedule: Schedule,
        callback_data: Optional[CallbackData] = None,
        recover_point: Optional[ScheduleInterruptPoint] = None,
    ) -> ScheduleResult:
        """
        节点的 schedule 处理逻辑

        :param process_id: 进程 ID
        :type process_id: int
        :param schedule: Schedule 实例
        :type schedule: Schedule
        :param callback_data: 回调数据, defaults to None
        :type callback_data: Optional[CallbackData], optional
        :return: 调度结果
        :rtype: ScheduleResult
        """
        with metrics.observe(
            metrics.ENGINE_NODE_SCHEDULE_PRE_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            # data prepare
            top_pipeline_id = process_info.top_pipeline_id
            root_pipeline_id = process_info.root_pipeline_id

            data_outputs = self.runtime.get_data_outputs(self.node.id)
            service_data = self.runtime.get_execution_data(self.node.id)

            root_pipeline_inputs = self._get_plain_inputs(root_pipeline_id)
            root_pipeline_data = ExecutionData(inputs=root_pipeline_inputs, outputs={})
            logger.info(
                "root_pipeline[%s] node(%s) activity schedule data: %s, root inputs: %s",
                root_pipeline_id,
                self.node.id,
                service_data,
                root_pipeline_inputs,
            )

            service = self.runtime.get_service(code=self.node.code, version=self.node.version, name=self.node.name)
            service.setup_runtime_attributes(
                id=self.node.id,
                version=schedule.version,
                top_pipeline_id=top_pipeline_id,
                root_pipeline_id=root_pipeline_id,
                loop=loop,
                inner_loop=inner_loop,
            )

        # build_node_type: sleep_timer_legacy
        node_type = "{}_{}".format(self.node.code, self.node.version)
        # schedule
        schedule_success = False
        is_schedule_done = False
        schedule.times += 1
        if recover_point and recover_point.handler_data.service_scheduled:
            schedule_success = not recover_point.handler_data.service_schedule_fail
            is_schedule_done = recover_point.handler_data.is_schedule_done
            service_data.outputs = FancyDict(
                self.runtime.deserialize_execution_data(
                    recover_point.handler_data.schedule_serialize_outputs,
                    recover_point.handler_data.schedule_outputs_serializer,
                )
            )
        else:
            try:
                schedule_success = service.schedule(
                    schedule=schedule,
                    data=service_data,
                    root_pipeline_data=root_pipeline_data,
                    callback_data=callback_data,
                )
            except Exception:
                ENGINE_SCHEDULE_EXCEPTION_COUNT.labels(type=node_type, hostname=self._hostname).inc()
                service_data.outputs.ex_data = traceback.format_exc()
                self.runtime.node_schedule_exception(root_pipeline_id, self.node.id, ex_data=traceback.format_exc())
                self.hook_dispatch(
                    hook=HookType.NODE_SCHEDULE_EXCEPTION,
                    root_pipeline_id=root_pipeline_id,
                    service=service,
                    service_data=service_data,
                    root_pipeline_data=root_pipeline_data,
                    callback_data=callback_data,
                )
            else:
                is_schedule_done = service.is_schedule_done()

        if not schedule_success:
            ENGINE_SCHEDULE_FAILED_COUNT.labels(type=node_type, hostname=self._hostname).inc()

        with metrics.observe(
            metrics.ENGINE_NODE_SCHEDULE_POST_PROCESS_DURATION, type=self.node.type.value, hostname=self._hostname
        ):
            serialize_outputs, outputs_serializer = self.runtime.serialize_execution_data(service_data.outputs)
            self.interrupter.check_and_set(
                ScheduleKeyPoint.SA_SERVICE_SCHEDULE_DONE,
                service_scheduled=True,
                is_schedule_done=is_schedule_done,
                service_schedule_fail=not schedule_success,
                schedule_serialize_outputs=serialize_outputs,
                schedule_outputs_serializer=outputs_serializer,
                from_handler=True,
            )

            service_data.outputs._result = schedule_success
            service_data.outputs._loop = loop
            service_data.outputs._inner_loop = inner_loop

            if not recover_point or not recover_point.handler_data.schedule_times_added:
                self.runtime.add_schedule_times(schedule.id)
            self.interrupter.check_and_set(
                ScheduleKeyPoint.SA_SERVICE_SCHEDULE_TIME_ADDED, schedule_times_added=True, from_handler=True
            )
            self.runtime.set_execution_data(node_id=self.node.id, data=service_data)

            schedule_type = service.schedule_type()

            # schedule success
            if schedule_success:
                if schedule_type == ScheduleType.CALLBACK:
                    return self._finish_schedule(
                        process_info=process_info,
                        schedule=schedule,
                        data_outputs=data_outputs,
                        execution_data=service_data,
                        error_ignored=False,
                        root_pipeline_inputs=root_pipeline_inputs,
                        recover_point=recover_point,
                    )
                else:
                    # poll or multi-callback finished
                    if is_schedule_done:
                        return self._finish_schedule(
                            process_info=process_info,
                            schedule=schedule,
                            data_outputs=data_outputs,
                            execution_data=service_data,
                            error_ignored=False,
                            root_pipeline_inputs=root_pipeline_inputs,
                            recover_point=recover_point,
                        )

                    has_next_schedule = schedule_type == ScheduleType.POLL
                    return ScheduleResult(
                        has_next_schedule=has_next_schedule,
                        schedule_after=service.schedule_after(
                            schedule=schedule,
                            data=service_data,
                            root_pipeline_data=root_pipeline_data,
                        ),
                        schedule_done=False,
                        next_node_id=None,
                    )

            # schedule fail
            if not self.node.error_ignorable:

                self.runtime.node_schedule_fail(root_pipeline_id, self.node.id)
                self.hook_dispatch(
                    hook=HookType.NODE_SCHEDULE_FAIL,
                    root_pipeline_id=root_pipeline_id,
                    service=service,
                    service_data=service_data,
                    root_pipeline_data=root_pipeline_data,
                    callback_data=callback_data,
                )

                self.runtime.set_state(
                    node_id=self.node.id,
                    version=schedule.version,
                    to_state=states.FAILED,
                    set_archive_time=True,
                    ignore_boring_set=recover_point is not None,
                )

                context = Context(self.runtime, [], root_pipeline_inputs)
                context.extract_outputs(
                    pipeline_id=process_info.top_pipeline_id,
                    data_outputs=data_outputs,
                    execution_data_outputs=service_data.outputs,
                )

                return ScheduleResult(
                    has_next_schedule=False,
                    schedule_after=-1,
                    schedule_done=False,
                    next_node_id=None,
                )

            # schedule fail and error ignore
            return self._finish_schedule(
                process_info=process_info,
                schedule=schedule,
                data_outputs=data_outputs,
                execution_data=service_data,
                error_ignored=True,
                root_pipeline_inputs=root_pipeline_inputs,
                recover_point=recover_point,
            )

    def hook_dispatch(
        self,
        hook: HookType,
        root_pipeline_id: str,
        service: Service,
        service_data: ExecutionData,
        root_pipeline_data: ExecutionData,
        callback_data: Optional[CallbackData] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        hook 分发逻辑
        :param hook: 钩子
        :type hook: HookType
        :param root_pipeline_id: 根 ID
        :type root_pipeline_id: str
        :param service: 服务类
        :type service: Service
        :param service_data: 节点数据
        :type service_data: ExecutionData
        :param root_pipeline_data: 根流程执行数据
        :type root_pipeline_data: ExecutionData
        :param callback_data: 回调数据
        :type callback_data: CallbackData
        :return: [description]
        :rtype: bool
        """
        if service.need_run_hook():
            logger.info("root_pipeline[%s] node(%s) start to run hook(%s)", root_pipeline_id, service_data, hook.value)
            try:
                dispatch_success: bool = service.hook_dispatch(
                    hook=hook, data=service_data, root_pipeline_data=root_pipeline_data, callback_data=callback_data
                )
                logger.info(
                    "root_pipeline[%s] node(%s) dispatch(%s) result -> (%s)",
                    root_pipeline_id,
                    self.node.id,
                    hook.value,
                    dispatch_success,
                )
                if dispatch_success:
                    # hook 执行成功，设置的数据需要保存
                    logger.info("root_pipeline[%s] node(%s) reset service_data", root_pipeline_id, self.node.id)
                    self.runtime.set_execution_data(node_id=self.node.id, data=service_data)
                    return True

            except Exception:
                logger.exception(
                    "root_pipeline[%s] node(%s) dispatch(%) fail, but skip", root_pipeline_id, self.node.id, hook.value
                )
        else:
            logger.info("root_pipeline[%s] node(%s) skip dispatch(%s)", root_pipeline_id, self.node.id, hook.value)

        return False
