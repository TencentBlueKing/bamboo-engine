from django.test import TestCase
from pipeline_test_use.components.collections.experience import TheScheduleComponent

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
                schedule_assertion=[
                    ScheduleAssertion(
                        success=True,
                        outputs={"k1": "v1", "k2": "v2", "count": 1, "parent_data": {"k": "v"}},
                        callback_data=None,
                    ),
                    ScheduleAssertion(
                        success=True,
                        outputs={"k1": "v1", "k2": "v2", "count": 2, "parent_data": {"k": "v"}},
                        callback_data=None,
                    ),
                    ScheduleAssertion(
                        success=True,
                        schedule_finished=True,
                        outputs={"k1": "v1", "k2": "v2", "count": 2, "parent_data": {"k": "v"}},
                        callback_data=None,
                    ),
                ],
            ),
            ComponentTestCase(
                name="execute fail case",
                inputs={"k1": "v1", "k2": "v2", "fail": True},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(success=False, outputs={}),
                schedule_assertion=None,
            ),
            ComponentTestCase(
                name="schedule fail case",
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
        return TheScheduleComponent
