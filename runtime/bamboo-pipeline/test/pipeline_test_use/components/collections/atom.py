# -*- coding: utf-8 -*-
import datetime
import logging
import pprint
import re
import time
import typing

from pipeline.component_framework.component import Component
from pipeline.core.flow.activity import Service, StaticIntervalGenerator

from bamboo_engine.eri import HookType

logger = logging.getLogger("celery")


class HookMixin:
    __need_run_hook__ = True

    def recorder(self, hook: HookType, data, parent_data, callback_data=None):
        if hasattr(hook.value, "id"):
            self.logger.info("hook_debug_node({}) id: {}".format(hook.value, self.id))
            self.logger.info("hook_debug_node({}) root_pipeline_id: {}".format(hook.value, self.root_pipeline_id))
        logger.info("hook_debug_node hook(%s) data %s ", hook.value, pprint.pformat(data.inputs))
        logger.info("hook_debug_node hook(%s) parent data %s ", hook.value, pprint.pformat(parent_data.inputs))
        logger.info("hook_debug_node hook(%s) output data %s ", hook.value, pprint.pformat(data.outputs))

        hook_call_count: int = data.get_one_of_outputs(hook.value, 0)
        data.set_outputs(hook.value, hook_call_count + 1)

        hook_call_order: typing.List[str] = data.get_one_of_outputs("hook_call_order", [])
        hook_call_order.append(hook.value)
        data.set_outputs("hook_call_order", hook_call_order)
        logger.info("hook_debug_node hook(%s) output data %s ", hook.value, pprint.pformat(data.outputs))
        return True

    def pre_execute(self, data, parent_data):
        """节点执行前"""
        return self.recorder(HookType.PRE_EXECUTE, data, parent_data)

    def execute(self, data, parent_data):
        self.recorder(hook=HookType.EXECUTE, data=data, parent_data=parent_data)
        return super().execute(data, parent_data)

    def post_execute(self, data, parent_data):
        """节点执行后"""
        return self.recorder(HookType.POST_EXECUTE, data, parent_data)

    def pre_schedule(self, data, parent_data):
        """节点调度前"""
        return self.recorder(HookType.PRE_SCHEDULE, data, parent_data)

    def schedule(self, data, parent_data, callback_data=None):
        self.recorder(hook=HookType.SCHEDULE, data=data, parent_data=parent_data, callback_data=callback_data)
        return super().schedule(data, parent_data, callback_data)

    def post_schedule(self, data, parent_data):
        """节点调度后"""
        return self.recorder(HookType.POST_SCHEDULE, data, parent_data)

    def pre_resume_node(self, data, parent_data):
        """节点继续操作前"""
        return self.recorder(HookType.PRE_RESUME_NODE, data, parent_data)

    def post_resume_node(self, data, parent_data):
        """节点继续操作后"""
        return self.recorder(HookType.POST_RESUME_NODE, data, parent_data)

    def pre_pause_node(self, data, parent_data):
        """节点暂停操作前"""
        return self.recorder(HookType.PRE_RESUME_NODE, data, parent_data)

    def post_pause_node(self, data, parent_data):
        """节点暂停操作后"""
        return self.recorder(HookType.POST_PAUSE_NODE, data, parent_data)

    def pre_retry_node(self, data, parent_data):
        """节点重试操作前"""
        return self.recorder(HookType.PRE_RETRY_NODE, data, parent_data)

    def post_retry_node(self, data, parent_data):
        """节点重试操作后"""
        return self.recorder(HookType.POST_RETRY_NODE, data, parent_data)

    def pre_skip_node(self, data, parent_data):
        """节点跳过操作前"""
        return self.recorder(HookType.PRE_SKIP_NODE, data, parent_data)

    def post_skip_node(self, data, parent_data):
        """节点跳过操作后"""
        return self.recorder(HookType.POST_SKIP_NODE, data, parent_data)

    def pre_forced_fail_activity(self, data, parent_data):
        """节点跳过操作前"""
        return self.recorder(HookType.PRE_FORCED_FAIL_ACTIVITY, data, parent_data)

    def post_forced_fail_activity(self, data, parent_data):
        """节点跳过操作后"""
        return self.recorder(HookType.POST_FORCED_FAIL_ACTIVITY, data, parent_data)

    def pre_callback(self, data, parent_data, callback_data=None):
        """节点回调前"""
        return self.recorder(HookType.PRE_CALLBACK, data, parent_data)

    def post_callback(self, data, parent_data, callback_data=None):
        """节点回调后"""
        return self.recorder(HookType.POST_CALLBACK, data, parent_data)

    def node_execute_fail(self, data, parent_data):
        """节点 execute 异常后"""
        return self.recorder(HookType.NODE_EXECUTE_FAIL, data, parent_data)

    def node_schedule_fail(self, data, parent_data, callback_data=None):
        """节点调度失败后"""
        return self.recorder(HookType.NODE_SCHEDULE_FAIL, data, parent_data)

    def node_execute_exception(self, data, parent_data):
        """节点 execute 异常后"""
        return self.recorder(HookType.NODE_EXECUTE_EXCEPTION, data, parent_data)

    def node_schedule_exception(self, data, parent_data, callback_data=None):
        """节点调度失败后"""
        return self.recorder(HookType.NODE_SCHEDULE_EXCEPTION, data, parent_data)

    def node_enter(self, data, parent_data):
        """节点 execute 前"""
        return self.recorder(HookType.NODE_ENTER, data, parent_data)

    def node_finish(self, data, parent_data):
        """节点执行结束"""
        return self.recorder(HookType.NODE_FINISH, data, parent_data)


class DebugNoScheduleService(Service):
    __need_schedule__ = False

    def execute(self, data, parent_data):
        logger.info("debug_no_schedule_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("debug_no_schedule_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        for key, val in data.inputs.items():
            data.set_outputs(key, val)
        logger.info("debug_no_schedule_node output data %s " % pprint.pformat(data.outputs))
        return True

    def outputs_format(self):
        return []


class DebugNoScheduleComponent(Component):
    name = "debug 组件"
    code = "debug_no_schedule_node"
    bound_service = DebugNoScheduleService
    form = "index.html"


class DebugService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(0)

    def execute(self, data, parent_data):
        self.logger.info("execute id: {}".format(self.id))
        self.logger.info("execute root_pipeline_id: {}".format(self.root_pipeline_id))
        logger.info("debug_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("debug_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        for key, val in data.inputs.items():
            data.set_outputs(key, val)
        logger.info("debug_node output data %s " % pprint.pformat(data.outputs))
        return True

    def schedule(self, data, parent_data, callback_data=None):
        self.logger.info("schedule id: {}".format(self.id))
        self.logger.info("schedule root_pipeline_id: {}".format(self.root_pipeline_id))
        logger.info("debug_node schedule data %s " % pprint.pformat(data.inputs))
        logger.info("debug_node schedule parent data %s " % pprint.pformat(parent_data.inputs))
        logger.info("debug_node schedule output data %s " % pprint.pformat(data.outputs))

        self.finish_schedule()
        return True

    def outputs_format(self):
        return []


class DebugComponent(Component):
    name = "debug 组件"
    code = "debug_node"
    bound_service = DebugService
    form = "index.html"


class HookDebugService(HookMixin, DebugService):
    pass


class HookDebugComponent(Component):
    name = "debug 组件"
    code = "hook_debug_node"
    bound_service = HookDebugService
    form = "index.html"


class ScheduleService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(2)

    def execute(self, data, parent_data):
        logger.info("schedule_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("schedule_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        for key, val in data.inputs.items():
            data.set_outputs(key, val)
        return True

    def schedule(self, data, parent_data, callback_data=None):
        logger.info("schedule_node schedule data %s " % pprint.pformat(data.inputs))
        logger.info("schedule_node schedule parent data %s " % pprint.pformat(parent_data.inputs))

        count = data.get_one_of_outputs("count")
        logger.info("schedule_node count %s " % count)
        if count is None:
            data.outputs.count = 1
        else:
            if count == 5:
                self.finish_schedule()
            else:
                data.outputs.count += 1

        return True

    def outputs_format(self):
        return []


class ScheduleComponent(Component):
    name = "debug 组件"
    code = "schedule_node"
    bound_service = ScheduleService
    form = "index.html"


class SleepTimerService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(1)
    #  匹配年月日 时分秒 正则 yyyy-MM-dd HH:mm:ss
    date_regex = re.compile(
        r"%s %s"
        % (
            r"^(((\d{3}[1-9]|\d{2}[1-9]\d{1}|\d{1}[1-9]\d{2}|[1-9]\d{3}))|"
            r"(29/02/((\d{2})(0[48]|[2468][048]|[13579][26])|((0[48]|[2468][048]|[3579][26])00))))-"
            r"((0[13578]|1[02])-((0[1-9]|[12]\d|3[01]))|"
            r"((0[469]|11)-(0[1-9]|[12]\d|30))|(02)-(0[1-9]|[1]\d|2[0-8]))",
            r"((0|[1])\d|2[0-3]):(0|[1-5])\d:(0|[1-5])\d$",
        )
    )

    seconds_regex = re.compile(r"^\d{1,8}$")

    def execute(self, data, parent_data):
        timing = str(data.get_one_of_inputs("bk_timing"))

        if self.date_regex.match(timing):
            eta = datetime.datetime.strptime(timing, "%Y-%m-%d %H:%M:%S")
            t = "timing"
        #  如果写成+号 可以输入无限长，或考虑前端修改
        elif self.seconds_regex.match(timing):
            eta = timing
            t = "countdown"
        else:
            message = "输入参数%s不符合【秒(s) 或 时间(%%Y-%%m-%%d %%H:%%M:%%S)】格式" % timing
            data.set_outputs("ex_data", message)
            return False
        data.set_outputs("eta", eta)
        data.set_outputs("type", t)

        return True

    def schedule(self, data, parent_data, callback_data=None):
        timing_time = data.get_one_of_outputs("timing_time", default=None)
        if not timing_time:
            eta = data.get_one_of_outputs("eta")
            timing_type = data.get_one_of_outputs("type")
            timing_time = (
                datetime.datetime.now() + datetime.timedelta(seconds=int(eta)) if timing_type == "countdown" else eta
            )
            data.set_outputs("timing_time", timing_time)

        if timing_time <= datetime.datetime.now():
            self.finish_schedule()

        return True

    def outputs_format(self):
        return []


class SleepTimerComponent(Component):
    name = "定时"
    code = "sleep_timer"
    bound_service = SleepTimerService
    form = "form.html"


class LoopCountOutputScheduleService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(1)

    def execute(self, data, parent_data):
        logger.info("loop_count_s_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("loop_count_s_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        logger.info("loop_count_s_node loop times: %s" % data.inputs._loop)

    def schedule(self, data, parent_data, callback_data=None):
        logger.info("loop_count_s_node schedule data %s " % pprint.pformat(data.inputs))
        logger.info("loop_count_s_node schedule parent data %s " % pprint.pformat(parent_data.inputs))

        count = data.get_one_of_outputs("count")
        logger.info("count %s " % count)
        if count is None:
            data.outputs.count = 1
        else:
            if count == 2:
                data.outputs.loop = data.inputs._loop
                for key, val in data.inputs.items():
                    data.set_outputs(key, val)
                self.finish_schedule()
            else:
                data.outputs.count += 1

        return True

    def outputs_format(self):
        return []


class LoopCountOutputScheduleComponent(Component):
    name = "loop count output component"
    code = "loop_count_s_node"
    bound_service = LoopCountOutputScheduleService
    form = "index.html"


class LoopCountOutputService(Service):
    def execute(self, data, parent_data):
        logger.info("loop_count_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("loop_count_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        logger.info("loop_count_node loop times: %s" % data.inputs._loop)
        data.outputs.loop = data.inputs._loop
        for key, val in data.inputs.items():
            data.set_outputs(key, val)

    def outputs_format(self):
        return []


class LoopCountOutputComponent(Component):
    name = "loop count output component"
    code = "loop_count_node"
    bound_service = LoopCountOutputService
    form = "index.html"


class FailAtSecondExecService(Service):
    def execute(self, data, parent_data):
        logger.info("fail_at_second_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("fail_at_second_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        logger.info("fail_at_second_node loop times: %s" % data.inputs._loop)

        if data.inputs._loop == 1 and not data.inputs.get("can_go", False):
            return False

        data.outputs.loop = data.inputs._loop
        for key, val in data.inputs.items():
            data.set_outputs(key, val)

    def outputs_format(self):
        return []


class FailAtSecondExecComponent(Component):
    name = "fail at second execute component"
    code = "fail_at_second_node"
    bound_service = FailAtSecondExecService
    form = "index.html"


class FailCtrlService(Service):
    def execute(self, data, parent_data):
        self.logger.info("fail_ctrl_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("fail_ctrl_node execute data %s " % pprint.pformat(data.inputs))

        bit = int(data.get_one_of_inputs("bit", 0))

        if bit == 0:
            return False

        return True

    def outputs_format(self):
        return []


class FailCtrlComponent(Component):
    name = "fail control component"
    code = "fail_ctrl_node"
    bound_service = FailCtrlService
    form = "index.html"


class HookFailCtrlService(HookMixin, FailCtrlService):
    pass


class HookFailCtrlComponent(Component):
    name = "fail control component"
    code = "hook_fail_ctrl_node"
    bound_service = HookFailCtrlService
    form = "index.html"


class DummyExecuteService(Service):
    def execute(self, data, parent_data):
        time.sleep(int(data.inputs.time))

        return True

    def outputs_format(self):
        return []


class DummyExecuteComponent(Component):
    name = "dummy execute component"
    code = "dummy_exec_node"
    bound_service = DummyExecuteService
    form = "index.html"


class CallbackService(Service):
    __need_schedule__ = True
    interval = None

    def execute(self, data, parent_data):
        return True

    def schedule(self, data, parent_data, callback_data=None):
        if callback_data:
            if int(callback_data.get("bit", 0)) == 0:
                return False

        return True

    def outputs_format(self):
        return []


class CallbackComponent(Component):
    name = "callback component"
    code = "callback_node"
    bound_service = CallbackService
    form = "index.html"


class DebugCallbackService(Service):
    __need_schedule__ = True
    interval = None

    def execute(self, data, parent_data):
        return True

    def schedule(self, data, parent_data, callback_data=None):
        if callback_data:
            if int(callback_data.get("bit", 1)) == 1:
                self.finish_schedule()
                return True

        return False

    def outputs_format(self):
        return []


class DebugCallbackComponent(Component):
    name = "callback component"
    code = "debug_callback_node"
    bound_service = DebugCallbackService
    form = "index.html"


class HookCallbackService(HookMixin, CallbackService):
    pass


class HookCallbackComponent(Component):
    name = "callback component"
    code = "hook_callback_node"
    bound_service = HookCallbackService
    form = "index.html"


class MultiCallbackService(Service):
    __need_schedule__ = True
    __multi_callback_enabled__ = True
    interval = None

    def execute(self, data, parent_data):
        return True

    def schedule(self, data, parent_data, callback_data=None):
        _scheduled_times = getattr(data.outputs, "_scheduled_times", 0)

        # do something
        time.sleep(2)

        logger.info("[{}]: callback_data={}".format(_scheduled_times, callback_data))
        if callback_data:
            if int(callback_data.get("bit", 0)) == 0:
                return False

        _scheduled_times += 1
        data.set_outputs("_scheduled_times", _scheduled_times)

        if _scheduled_times == 5:
            self.finish_schedule()

        return True

    def outputs_format(self):
        return []


class MultiCallbackComponent(Component):
    name = "multi_callback component"
    code = "multi_callback_node"
    bound_service = MultiCallbackService
    form = "index.html"


class HookMultiCallbackService(HookMixin, MultiCallbackService):
    pass


class HookMultiCallbackComponent(Component):
    name = "multi_callback component"
    code = "hook_multi_callback_node"
    bound_service = HookMultiCallbackService
    form = "index.html"


def my_failure_handler(data, parent_data):
    print("failure handler:", data)
    print("failure handler:", parent_data)


class EmptyService(Service):
    def execute(self, data, parent_data):
        return True

    def outputs_format(self):
        return []


class EmptyComponent(Component):
    name = "empty node"
    code = "empty_node"
    bound_service = EmptyService
    form = "index.html"


class InterruptService(Service):
    def __init__(self, name=None):
        super().__init__(name=name)
        self.execute_count = 0

    def execute(self, data, parent_data):
        self.logger.info("execute id: {}".format(self.id))
        self.logger.info("execute root_pipeline_id: {}".format(self.root_pipeline_id))
        logger.info("debug_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("debug_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        for key, val in data.inputs.items():
            data.set_outputs(key, val)
        logger.info("debug_node output data %s " % pprint.pformat(data.outputs))
        self.execute_count += 1
        data.set_outputs("execute_count", self.execute_count)
        return True

    def outputs_format(self):
        return []


class InterruptComponent(Component):
    name = "debug 组件"
    code = "interrupt_test"
    bound_service = InterruptService
    form = "index.html"


class InterruptScheduleService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(0)

    def __init__(self, name=None):
        super().__init__(name=name)
        self.execute_count = 0
        self.schedule_count = 0

    def execute(self, data, parent_data):
        self.logger.info("execute id: {}".format(self.id))
        self.logger.info("execute root_pipeline_id: {}".format(self.root_pipeline_id))
        logger.info("debug_node execute data %s " % pprint.pformat(data.inputs))
        logger.info("debug_node execute parent data %s " % pprint.pformat(parent_data.inputs))
        for key, val in data.inputs.items():
            data.set_outputs(key, val)
        logger.info("debug_node output data %s " % pprint.pformat(data.outputs))
        self.execute_count += 1
        data.set_outputs("execute_count", self.execute_count)
        return True

    def schedule(self, data, parent_data, callback_data=None):
        self.logger.info("schedule id: {}".format(self.id))
        self.logger.info("schedule root_pipeline_id: {}".format(self.root_pipeline_id))
        logger.info("debug_node schedule data %s " % pprint.pformat(data.inputs))
        logger.info("debug_node schedule parent data %s " % pprint.pformat(parent_data.inputs))
        logger.info("debug_node schedule output data %s " % pprint.pformat(data.outputs))
        self.schedule_count += 1
        data.set_outputs("schedule_count", self.schedule_count)

        self.finish_schedule()
        return True

    def outputs_format(self):
        return []


class InterruptScheduleComponent(Component):
    name = "debug 组件"
    code = "interrupt_schedule_test"
    bound_service = InterruptScheduleService
    form = "index.html"


class InterruptDummyExecuteService(Service):
    def __init__(self, name=None):
        super().__init__(name=name)
        self.execute_count = 0

    def execute(self, data, parent_data):
        time.sleep(int(data.inputs.time))
        self.execute_count += 1
        data.set_outputs("execute_count", self.execute_count)

        return True

    def outputs_format(self):
        return []


class InterruptDummyExecuteComponent(Component):
    name = "dummy execute component"
    code = "interrupt_dummy_exec_node"
    bound_service = InterruptDummyExecuteService
    form = "index.html"


class InterruptRaiseService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(0)

    def __init__(self, name=None):
        super().__init__(name=name)
        self.execute_count = 0
        self.schedule_count = 0

    def execute(self, data, parent_data):
        if data.get_one_of_inputs("execute_raise", False):
            raise Exception()
        self.execute_count += 1
        data.set_outputs("execute_count", self.execute_count)
        return True

    def schedule(self, data, parent_data, callback_data=None):
        if data.get_one_of_inputs("schedule_raise", False):
            raise Exception()
        self.schedule_count += 1
        data.set_outputs("schedule_count", self.schedule_count)

        self.finish_schedule()
        return True

    def outputs_format(self):
        return []


class InterruptRaiseScheduleComponent(Component):
    name = "debug 组件"
    code = "interrupt_raise_test"
    bound_service = InterruptRaiseService
    form = "index.html"


class HookInterruptRaiseService(HookMixin, InterruptRaiseService):
    pass


class HookInterruptRaiseComponent(Component):
    name = "debug 组件"
    code = "hook_interrupt_raise_test"
    bound_service = HookInterruptRaiseService
    form = "index.html"
