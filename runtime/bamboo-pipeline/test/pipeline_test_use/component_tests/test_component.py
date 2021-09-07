from django.test import TestCase
from pipeline_test_use.components.collections.experience import TheComponent

from pipeline.component_framework.test import ComponentTestCase, ComponentTestMixin, ExecuteAssertion


class TheComponentTest(TestCase, ComponentTestMixin):
    def cases(self):
        return [
            ComponentTestCase(
                name="execute success case",
                inputs={"k1": "v1", "k2": "v2"},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(
                    success=True, outputs={"k1": "v1", "k2": "v2", "parent_data": {"k": "v"}}
                ),
                schedule_assertion=None,
            ),
            ComponentTestCase(
                name="execute fail case",
                inputs={"k1": "v1", "k2": "v2", "fail": True},
                parent_data={"k": "v"},
                execute_assertion=ExecuteAssertion(success=False, outputs={}),
                schedule_assertion=None,
            ),
        ]

    def component_cls(self):
        return TheComponent
