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

from django.test import TestCase

from pipeline.eri.utils import caculate_final_references


class CaculateFinalReferencesTestCase(TestCase):
    def test_normal(self):
        original_references = {
            "a": {"c", "d", "not_exist"},
            "b": {"d", "e"},
            "c": {"f"},
            "d": {"f", "g"},
            "e": {},
            "f": {"g", "h", "i"},
            "h": {},
            "i": {},
        }
        final_references = caculate_final_references(original_references)
        self.assertEqual(
            final_references,
            {
                "a": {"c", "d", "not_exist", "f", "g", "h", "i"},
                "b": {"d", "e", "f", "g", "h", "i"},
                "c": {"f", "g", "h", "i"},
                "d": {"f", "g", "h", "i"},
                "e": set(),
                "f": {"g", "h", "i"},
                "h": set(),
                "i": set(),
            },
        )

    def test_circle(self):
        original_references = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        final_references = caculate_final_references(original_references)
        self.assertEqual(final_references, {"a": {"a", "b", "c"}, "b": {"a", "b", "c"}, "c": {"a", "b", "c"}})
