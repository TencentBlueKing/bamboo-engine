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

from functools import wraps

from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from pipeline.contrib.diagnostics.models import DiagnosticCase, DiagnosticOperationAudit


def _superuser_required(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False) or not getattr(user, "is_superuser", False):
            return HttpResponseForbidden("superuser required")
        return func(request, *args, **kwargs)

    return wrapper


@_superuser_required
def case_list(request):
    cases = DiagnosticCase.objects.all().order_by("-last_seen_at", "-id")
    status = request.GET.get("status")
    stuck_type = request.GET.get("stuck_type")
    root_pipeline_id = request.GET.get("root_pipeline_id")
    node_id = request.GET.get("node_id")

    if status:
        cases = cases.filter(status=status)
    if stuck_type:
        cases = cases.filter(stuck_type=stuck_type)
    if root_pipeline_id:
        cases = cases.filter(root_pipeline_id=root_pipeline_id)
    if node_id:
        cases = cases.filter(node_id=node_id)

    paginator = Paginator(cases, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "diagnostics/case_list.html", {"page": page, "filters": request.GET})


@_superuser_required
def case_detail(request, case_id):
    diagnostic_case = get_object_or_404(DiagnosticCase, id=case_id)
    audits = DiagnosticOperationAudit.objects.filter(case=diagnostic_case).order_by("-created_at")[:100]
    return render(request, "diagnostics/case_detail.html", {"case": diagnostic_case, "audits": audits})


@require_POST
@_superuser_required
def update_case_status(request, case_id):
    diagnostic_case = get_object_or_404(DiagnosticCase, id=case_id)
    status = request.POST.get("status")
    if status in [DiagnosticCase.STATUS_OPEN, DiagnosticCase.STATUS_RESOLVED, DiagnosticCase.STATUS_IGNORED]:
        diagnostic_case.status = status
        diagnostic_case.save(update_fields=["status", "updated_at"])
    return redirect("pipeline_diagnostics:case_detail", case_id=diagnostic_case.id)
