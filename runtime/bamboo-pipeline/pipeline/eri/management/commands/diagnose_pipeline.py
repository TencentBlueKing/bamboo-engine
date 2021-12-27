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
from typing import Any, Optional

from django.core.management.base import BaseCommand, CommandParser

from pipeline.eri.doctor import PipelineDoctor


class Command(BaseCommand):
    help = "Diagnose a stuck pipeline and heal it"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(dest="pipeline_id", help="ID of pipeline which need to diagnose")
        parser.add_argument(
            "--heal", action="store_true", dest="heal_it", default=False, help="Whether to try to fix the pipeline"
        )

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        doctor = PipelineDoctor(heal_it=options["heal_it"])
        summary = doctor.diagnose(pipeline_id=options["pipeline_id"])
        print(summary)
