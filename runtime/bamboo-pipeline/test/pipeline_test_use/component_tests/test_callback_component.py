from django.test import TestCase
from pipeline_test_use.components.collections.experience import TheCallbackComponent

from pipeline.component_framework.test import ComponentTestCase, ComponentTestMixin, ExecuteAssertion, ScheduleAssertion


class TheScheduleComponentTest(TestCase, ComponentTestMixin):
    def cases(self):
        return [
            ComponentTestCase(
                name="success case",
                inputs={"k1": "v1", "k2": "v2"},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(
                    success=True, outputs={"k1": "v1", "k2": "v2", "parent_data": {"k": "v"}}
                ),
                schedule_assertion=ScheduleAssertion(
                    success=True,
                    outputs={"k1": "v1", "k2": "v2", "k3": "v3", "parent_data": {"k": "v"}},
                    callback_data={"k3": "v3"},
                ),
            ),
            ComponentTestCase(
                name="execute fail case",
                inputs={"k1": "v1", "k2": "v2", "fail": True},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(success=False, outputs={}),
                schedule_assertion=None,
            ),
            ComponentTestCase(
                name="callback fail case",
                inputs={"k1": "v1", "k2": "v2", "schedule_fail": True},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(
                    success=True, outputs={"k1": "v1", "k2": "v2", "schedule_fail": True, "parent_data": {"k": "v"}}
                ),
                schedule_assertion=ScheduleAssertion(
                    success=False,
                    outputs={"k1": "v1", "k2": "v2", "schedule_fail": True, "parent_data": {"k": "v"}},
                    callback_data=None,
                ),
            ),
        ]

    def component_cls(self):
        return TheCallbackComponent
