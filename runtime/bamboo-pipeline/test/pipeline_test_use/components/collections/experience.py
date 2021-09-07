# -*- coding: utf-8 -*-

import time

from pipeline.component_framework.component import Component
from pipeline.core.flow.activity import Service, StaticIntervalGenerator


class TheService(Service):
    def execute(self, data, parent_data):

        if data.inputs.get("fail", False):
            return False

        for k, v in data.inputs.items():
            data.outputs[k] = v

        data.outputs.parent_data = {}
        for k, v in parent_data.inputs.items():
            data.outputs.parent_data[k] = v

        return True

    def outputs_format(self):
        pass


class TheComponent(Component):
    name = u"the component"
    code = "the_component"
    bound_service = TheService


class TheScheduleService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(1)

    def execute(self, data, parent_data):

        if data.inputs.get("fail", False):
            return False

        for k, v in data.inputs.items():
            data.outputs[k] = v

        data.outputs.parent_data = {}
        for k, v in parent_data.inputs.items():
            data.outputs.parent_data[k] = v

        return True

    def schedule(self, data, parent_data, callback_data=None):

        if data.inputs.get("schedule_fail", False):
            return False

        count = data.get_one_of_outputs("count")
        if count is None:
            data.outputs.count = 1
        else:
            if count == 2:
                self.finish_schedule()
            else:
                data.outputs.count += 1

        return True


class TheScheduleComponent(Component):
    name = u"the schedule component"
    code = "the_schedule_component"
    bound_service = TheScheduleService


class TheException(Exception):
    pass


class TheCallbackService(Service):
    __need_schedule__ = True

    def execute(self, data, parent_data):
        if data.inputs.get("fail", False):
            return False

        for k, v in data.inputs.items():
            data.outputs[k] = v

        data.outputs.parent_data = {}
        for k, v in parent_data.inputs.items():
            data.outputs.parent_data[k] = v

        return True

    def schedule(self, data, parent_data, callback_data=None):

        if not callback_data:
            return False

        for k, v in callback_data.items():
            data.outputs[k] = v

        return True

    def outputs_format(self):
        return []


class TheCallbackComponent(Component):
    name = "the callback component"
    code = "the_callback_component"
    bound_service = TheCallbackService


def need_patch_1():
    raise Exception()


def need_patch_2():
    raise Exception()


class ThePatchService(Service):
    def execute(self, data, parent_data):
        for k, v in need_patch_1().items():
            data.outputs[k] = v

        for k, v in need_patch_2().items():
            data.outputs[k] = v

    def outputs_format(self):
        return []


class ThePatchComponent(Component):
    name = "the patch component"
    code = "the_patch_component"
    bound_service = ThePatchService


class TheCallAssertionService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(1)

    def execute(self, data, parent_data):

        if data.inputs.get("e_call_1", False):
            need_patch_1()

        if data.inputs.get("e_call_2", False):
            need_patch_2()

        return True

    def schedule(self, data, parent_data, callback_data=None):

        if data.inputs.get("s_call_1", False):
            need_patch_1()

        if data.inputs.get("s_call_2", False):
            need_patch_2()

        count = data.get_one_of_outputs("count")
        if count is None:
            data.outputs.count = 1
        else:
            if count == 2:
                self.finish_schedule()
            else:
                data.outputs.count += 1

        return True


class TheCallAssertionComponent(Component):
    name = "the call assertion component"
    code = "the_call_assertion_component"
    bound_service = TheCallAssertionService


class SleepService(Service):
    __need_schedule__ = True
    interval = StaticIntervalGenerator(1)

    def execute(self, data, parent_data):
        print("execute start")

        time.sleep(30)

        return True

    def schedule(self, data, parent_data, callback_data=None):
        print("schedule start")

        time.sleep(30)
        self.finish_schedule()

        return True


class SleepComponent(Component):
    name = "sleep component"
    code = "sleep_component"
    bound_service = SleepService
