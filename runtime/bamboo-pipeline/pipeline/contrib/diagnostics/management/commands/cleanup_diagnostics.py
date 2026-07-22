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

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from pipeline.contrib.diagnostics import conf
from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticEvent, DiagnosticOperationAudit


class Command(BaseCommand):
    help = "Cleanup expired pipeline diagnostics records."

    def handle(self, *args, **options):
        now = timezone.now()
        event_queryset = DiagnosticEvent.objects.filter(
            created_at__lt=now - datetime.timedelta(days=conf.event_retention_days())
        )
        case_queryset = (
            DiagnosticCase.objects.exclude(status=DiagnosticCase.STATUS_OPEN)
            .filter(updated_at__lt=now - datetime.timedelta(days=conf.case_retention_days()))
        )
        audit_queryset = DiagnosticOperationAudit.objects.filter(
            created_at__lt=now - datetime.timedelta(days=conf.audit_retention_days())
        )

        event_deleted = event_queryset.count()
        case_deleted = case_queryset.count()
        audit_deleted = audit_queryset.count()

        event_queryset.delete()
        DiagnosticOperationAudit.objects.filter(case_id__in=case_queryset.values_list("id", flat=True)).update(
            case=None
        )
        case_queryset.delete()
        audit_queryset.delete()

        self.stdout.write("DiagnosticEvent deleted: {}".format(event_deleted))
        self.stdout.write("DiagnosticCase deleted: {}".format(case_deleted))
        self.stdout.write("DiagnosticOperationAudit deleted: {}".format(audit_deleted))
