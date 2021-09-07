from django.test import TestCase
from pipeline_test_use.components.collections.experience import ThePatchComponent

from pipeline.component_framework.test import (
    Call,
    CallAssertion,
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    Patcher,
)


class TheComponentTest(TestCase, ComponentTestMixin):
    def cases(self):
        return [
            ComponentTestCase(
                name="execute success case 1",
                inputs={"k1": "v1", "k2": "v2"},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(success=True, outputs={"k1": "v1", "k2": "v2", "k3": "v3"}),
                schedule_assertion=None,
                patchers=[
                    Patcher(
                        target="pipeline_test_use.components.collections.experience.need_patch_1",
                        return_value={"k1": "v1", "k2": "v2"},
                    ),
                    Patcher(
                        target="pipeline_test_use.components.collections.experience.need_patch_2",
                        return_value={"k3": "v3"},
                    ),
                ],
                execute_call_assertion=[
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_1", calls=[Call()]
                    ),
                    CallAssertion(
                        func="pipeline_test_use.components.collections.experience.need_patch_2", calls=[Call()]
                    ),
                ],
            ),
            ComponentTestCase(
                name="execute success case 2",
                inputs={"k1": "v1", "k2": "v2"},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(success=True, outputs={"k1": "v1", "k2": "v2", "k3": "v3"}),
                schedule_assertion=None,
                patchers=[
                    Patcher(
                        target="pipeline_test_use.components.collections.experience.need_patch_1",
                        return_value={"k1": "v1", "k2": "v2"},
                    ),
                    Patcher(
                        target="pipeline_test_use.components.collections.experience.need_patch_2",
                        return_value={"k3": "v3"},
                    ),
                ],
            ),
        ]

    def component_cls(self):
        return ThePatchComponent
