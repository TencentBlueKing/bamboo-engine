# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import mock
from django.test import TestCase

from pipeline.models import PipelineTemplate
from pipeline.signals import handlers


class MockPipelineTemplate(object):
    def __init__(self, is_deleted):
        self.is_deleted = is_deleted
        self.template_id = "f7ec3227634c90871a4a62e02ea3c6c7"
        self.snapshot = None
        self.version = "3ba8297710b4224b879b6c8adf074cd1"
        self.data = {
            "activities": {
                "node6a56932956995e242ed478fc31fa": {
                    "type": "ServiceActivity",
                },
                "node997d3026641415e56e8e1389a733": {
                    "id": "node997d3026641415e56e8e1389a733",
                    "type": "SubProcess",
                    "version": "99b1d38ab9d4b9bf9dc0b1c7d725e27b",
                    "template_id": "neff788d4d033b77b5b02eaf3373ed4c",
                    "scheme_id_list": [1, 2, 3],
                },
            }
        }

        self.set_has_subprocess_bit = mock.MagicMock()


class MockQuerySet(object):
    def __init__(self, filter_result=None):
        self.filter = filter_result
        self.delete = mock.MagicMock(return_value=None)
        self.index = 0

    def __iter__(self):
        return iter(self.filter)

    def __next__(self):
        if self.index < len(self.filter):
            ret = self.filter[self.index]
            self.index += 1
            return ret
        else:
            raise StopIteration


class RelationShip(object):
    def __init__(self):
        self.descendant_template_id = "neff788d4d033b77b5b02eaf3373ed4c"
        self.templatescheme_set = mock.MagicMock()
        self.templatescheme_set.add = mock.MagicMock()


class PipelineSignalHandlerTestCase(TestCase):
    def test_template_pre_save_handler(self):
        template_to_be_delete = MockPipelineTemplate(is_deleted=True)
        handlers.pipeline_template_pre_save_handler(sender=PipelineTemplate, instance=template_to_be_delete)
        template_to_be_delete.set_has_subprocess_bit.assert_not_called()

        template_to_be_save = MockPipelineTemplate(is_deleted=False)
        handlers.pipeline_template_pre_save_handler(sender=PipelineTemplate, instance=template_to_be_save)
        template_to_be_save.set_has_subprocess_bit.assert_called_once()

    def test_template_post_save_handler(self):
        template_to_be_delete = MockPipelineTemplate(is_deleted=True)
        handlers.pipeline_template_post_save_handler(
            sender=PipelineTemplate, instance=template_to_be_delete, created=None
        )

        template_to_be_save = MockPipelineTemplate(is_deleted=False)
        relation = RelationShip()
        TemplateRelationship = mock.MagicMock()
        TemplateRelationship.objects.filter = mock.MagicMock(return_value=MockQuerySet(filter_result=[relation]))
        with mock.patch("pipeline.signals.handlers.TemplateRelationship", TemplateRelationship):
            handlers.pipeline_template_post_save_handler(
                sender=PipelineTemplate, instance=template_to_be_save, created=None
            )
            TemplateRelationship.objects.filter.assert_has_calls(
                [
                    mock.call(ancestor_template_id="f7ec3227634c90871a4a62e02ea3c6c7"),
                    mock.call(ancestor_template_id="f7ec3227634c90871a4a62e02ea3c6c7")
                ]
            )
            relation.templatescheme_set.add.assert_called_once_with(1, 2, 3)
