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

import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pipeline.contrib.diagnostics.recovery_runner import recovery_report


class Command(BaseCommand):
    help = "只读：按形态汇总恢复台账的预演结果、阻断原因、自愈比例和重放结果"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **options):
        hours = options["hours"]
        if hours <= 0:
            raise CommandError("--hours must be positive")
        since = timezone.now() - timedelta(hours=hours)
        report = {"since": since.isoformat(), "types": recovery_report(since)}
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
