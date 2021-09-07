from django.test import TestCase
from pipeline_test_use.components.collections.experience import TheCallAssertionComponent

from pipeline.component_framework.test import (
    Call,
    CallAssertion,
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    Patcher,
    ScheduleAssertion,
)


class TheCallAssertionComponentTest(TestCase, ComponentTestMixin):
    def cases(self):
        return [
            ComponentTestCase(
                name="not call any case",
                inputs={},
                parent_data={},
                execute_assertion=ExecuteAssertion(success=True, outputs={}),
                schedule_assertion=[
                    ScheduleAssertion(success=True, outputs={"count": 1}, callback_data=None),
                    ScheduleAssertion(success=True, outputs={"count": 2}, callback_data=None),
                    ScheduleAssertion(success=True, schedule_finished=True, outputs={"count": 2}, callback_data=None),
                ],
                patchers=[
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_1"),
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_2"),
                ],
                execute_call_assertion=[
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[]),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
                schedule_call_assertion=[
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[]),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
            ),
            ComponentTestCase(
                name="execute call 1 case",
                inputs={"e_call_1": True},
                parent_data={},
                execute_assertion=ExecuteAssertion(success=True, outputs={}),
                schedule_assertion=[
                    ScheduleAssertion(success=True, outputs={"count": 1}, callback_data=None),
                    ScheduleAssertion(success=True, outputs={"count": 2}, callback_data=None),
                    ScheduleAssertion(success=True, schedule_finished=True, outputs={"count": 2}, callback_data=None),
                ],
                patchers=[
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_1"),
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_2"),
                ],
                execute_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[Call()]
                    ),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
                schedule_call_assertion=[
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[]),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
            ),
            ComponentTestCase(
                name="schedule call 1 case",
                inputs={"s_call_1": True},
                parent_data={},
                execute_assertion=ExecuteAssertion(success=True, outputs={}),
                schedule_assertion=[
                    ScheduleAssertion(success=True, outputs={"count": 1}, callback_data=None),
                    ScheduleAssertion(success=True, outputs={"count": 2}, callback_data=None),
                    ScheduleAssertion(success=True, schedule_finished=True, outputs={"count": 2}, callback_data=None),
                ],
                patchers=[
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_1"),
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_2"),
                ],
                execute_call_assertion=[
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[]),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
                schedule_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1",
                        calls=[Call(), Call(), Call()],
                    ),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
            ),
            ComponentTestCase(
                name="call 1 case",
                inputs={"s_call_1": True, "e_call_1": True},
                parent_data={},
                execute_assertion=ExecuteAssertion(success=True, outputs={}),
                schedule_assertion=[
                    ScheduleAssertion(success=True, outputs={"count": 1}, callback_data=None),
                    ScheduleAssertion(success=True, outputs={"count": 2}, callback_data=None),
                    ScheduleAssertion(success=True, schedule_finished=True, outputs={"count": 2}, callback_data=None),
                ],
                patchers=[
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_1"),
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_2"),
                ],
                execute_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[Call()]
                    ),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
                schedule_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1",
                        calls=[Call(), Call(), Call()],
                    ),
                    CallAssertion(func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[]),
                ],
            ),
            ComponentTestCase(
                name="all call case",
                inputs={"s_call_1": True, "e_call_1": True, "s_call_2": True, "e_call_2": True},
                parent_data={},
                execute_assertion=ExecuteAssertion(success=True, outputs={}),
                schedule_assertion=[
                    ScheduleAssertion(success=True, outputs={"count": 1}, callback_data=None),
                    ScheduleAssertion(success=True, outputs={"count": 2}, callback_data=None),
                    ScheduleAssertion(success=True, schedule_finished=True, outputs={"count": 2}, callback_data=None),
                ],
                patchers=[
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_1"),
                    Patcher(target="pipeline_test_use.components.collections.experience.need_patch_2"),
                ],
                execute_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[Call()]
                    ),
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[Call()]
                    ),
                ],
                schedule_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1",
                        calls=[Call(), Call(), Call()],
                    ),
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_2",
                        calls=[Call(), Call(), Call()],
                    ),
                ],
            ),
        ]

    def component_cls(self):
        return TheCallAssertionComponent
