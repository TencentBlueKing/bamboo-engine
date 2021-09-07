# -*- coding: utf-8 -*-
from pipeline.component_framework.component import Component
from pipeline.core.flow.activity import Service


class ItsmService(Service):
    __need_schedule__ = True

    def execute(self, data, parent_data):
        print("itsm excute %s " % data)
        return True

    def schedule(self, data, parent_data, callback_data=None):
        # 扩展多种操作的事情
        try:
            instance = callback_data["instance"]
            print("itsm schedule %s" % instance.current_state["name"])
            transition_id = callback_data["data"]["transition_id"]
            next_step = instance.transition(transition_id)["name"]
            print("next_step is " + next_step)
            data.set_outputs("next_step", next_step)
        except Exception:
            pass
        return True

    def outputs_format(self):
        return []

    def deliver(self):
        return True


class ITSMComponent(Component):
    name = u"工单"
    code = "itsm_node"
    bound_service = ItsmService
    form = "index.html"


class MockItsmService(Service):
    __need_schedule__ = True

    def execute(self, data, parent_data):
        print("itsm excute %s " % data)
        return True

    def schedule(self, data, parent_data, callback_data=None):
        # 扩展多种操作的事情
        try:

            next_step = callback_data
            print("next_step is " + next_step)
            data.set_outputs("next_step", next_step)
        except Exception:
            pass
        return True

    def outputs_format(self):
        return []

    def deliver(self):
        return True


class MockITSMComponent(Component):
    name = u"模拟工单"
    code = "mock_itsm_node"
    bound_service = MockItsmService
    form = "index.html"
