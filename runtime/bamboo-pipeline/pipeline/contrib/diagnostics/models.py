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

import ujson as json
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class JSONTextField(models.TextField):
    def get_prep_value(self, value):
        return json.dumps(value)

    def to_python(self, value):
        value = super(JSONTextField, self).to_python(value)
        if value is None or isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    def from_db_value(self, value, expression, connection, context=None):
        return self.to_python(value)


class DiagnosticEvent(models.Model):
    id = models.BigAutoField(_("ID"), primary_key=True)
    event_type = models.CharField(_("事件类型"), max_length=64, db_index=True)
    root_pipeline_id = models.CharField(_("根 Pipeline ID"), max_length=64, db_index=True)
    node_id = models.CharField(_("节点ID"), max_length=64, blank=True, default="", db_index=True)
    process_id = models.BigIntegerField(_("进程ID"), null=True, blank=True, db_index=True)
    version = models.CharField(_("节点版本"), max_length=64, blank=True, default="")
    schedule_id = models.BigIntegerField(_("调度ID"), null=True, blank=True, db_index=True)
    callback_data_id = models.BigIntegerField(_("回调数据ID"), null=True, blank=True, db_index=True)
    result = models.CharField(_("事件结果"), max_length=32, blank=True, default="", db_index=True)
    reason = models.TextField(_("诊断原因"), blank=True, default="")
    duration = models.FloatField(_("持续时间"), null=True, blank=True)
    engine_version = models.CharField(_("引擎版本"), max_length=64, blank=True, default="")
    payload = JSONTextField(_("诊断载荷"), default=dict)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True, db_index=True)

    class Meta:
        app_label = "pipeline_diagnostics"
        verbose_name = _("Pipeline诊断事件")
        verbose_name_plural = _("Pipeline诊断事件")
        ordering = ["-id"]
        index_together = (("root_pipeline_id", "node_id"), ("event_type", "result"))

    def __unicode__(self):
        return "{}_{}_{}".format(self.root_pipeline_id, self.node_id, self.result)


class DiagnosticCase(models.Model):
    id = models.BigAutoField(_("ID"), primary_key=True)

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_IGNORED = "ignored"

    STATUS_CHOICES = (
        (STATUS_OPEN, _("待治理")),
        (STATUS_RESOLVED, _("已解决")),
        (STATUS_IGNORED, _("已忽略")),
    )

    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_CRITICAL = "critical"

    SEVERITY_CHOICES = (
        (SEVERITY_INFO, _("提示")),
        (SEVERITY_WARNING, _("告警")),
        (SEVERITY_CRITICAL, _("严重")),
    )

    root_pipeline_id = models.CharField(_("根 Pipeline ID"), max_length=64, db_index=True)
    node_id = models.CharField(_("节点ID"), max_length=64, db_index=True)
    stuck_type = models.CharField(_("卡住类型"), max_length=64, db_index=True)
    severity = models.CharField(
        _("严重级别"), max_length=32, choices=SEVERITY_CHOICES, default=SEVERITY_INFO, db_index=True
    )
    confidence = models.FloatField(_("置信度"), default=0.0)
    status = models.CharField(
        _("治理状态"), max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True
    )
    first_seen_at = models.DateTimeField(_("首次发现时间"), default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(_("最近发现时间"), default=timezone.now, db_index=True)
    hit_count = models.IntegerField(_("命中次数"), default=1)
    evidence = JSONTextField(_("证据"), default=dict)
    related_objects = JSONTextField(_("关联对象"), default=dict)
    recommended_actions = JSONTextField(_("推荐操作"), default=list)
    forbidden_actions = JSONTextField(_("禁止操作"), default=list)
    message = models.TextField(_("诊断信息"), blank=True, default="")
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        app_label = "pipeline_diagnostics"
        verbose_name = _("Pipeline诊断案例")
        verbose_name_plural = _("Pipeline诊断案例")
        ordering = ["-id"]
        index_together = (("root_pipeline_id", "node_id", "stuck_type", "status"), ("status", "severity"))
        unique_together = (("root_pipeline_id", "node_id", "stuck_type", "status"),)

    def __unicode__(self):
        return "{}_{}_{}_{}".format(self.root_pipeline_id, self.node_id, self.stuck_type, self.status)


class DiagnosticOperationAudit(models.Model):
    id = models.BigAutoField(_("ID"), primary_key=True)

    OPERATION_TYPE_REPLAY_CALLBACK_DATA = "replay_callback_data"
    OPERATION_TYPE_RESEND_SCHEDULE = "resend_schedule"
    OPERATION_TYPE_EXPIRE_STALE_SCHEDULE = "expire_stale_schedule"
    OPERATION_TYPE_INSPECT_ACK_CONVERGE = "inspect_ack_converge"
    OPERATION_TYPE_INSPECT_NODE_RUNTIME_READINESS = "inspect_node_runtime_readiness"
    OPERATION_TYPE_IGNORE = "ignore"

    MODE_DRY_RUN = "dry_run"
    MODE_APPLY = "apply"

    MODE_CHOICES = (
        (MODE_DRY_RUN, _("预检查")),
        (MODE_APPLY, _("执行")),
    )

    RISK_LEVEL_LOW = "low"
    RISK_LEVEL_MEDIUM = "medium"
    RISK_LEVEL_HIGH = "high"

    RISK_LEVEL_CHOICES = (
        (RISK_LEVEL_LOW, _("低")),
        (RISK_LEVEL_MEDIUM, _("中")),
        (RISK_LEVEL_HIGH, _("高")),
    )

    case = models.ForeignKey(
        DiagnosticCase,
        verbose_name=_("诊断案例"),
        related_name="operation_audits",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    operation_type = models.CharField(_("操作类型"), max_length=64, db_index=True)
    target_object = JSONTextField(_("操作对象"), default=dict)
    operator = models.CharField(_("操作人"), max_length=64)
    mode = models.CharField(_("操作模式"), max_length=32, choices=MODE_CHOICES, default=MODE_DRY_RUN, db_index=True)
    precheck_result = JSONTextField(_("预检查结果"), default=dict)
    result = JSONTextField(_("操作结果"), default=dict)
    risk_level = models.CharField(
        _("风险级别"), max_length=32, choices=RISK_LEVEL_CHOICES, default=RISK_LEVEL_LOW, db_index=True
    )
    payload = JSONTextField(_("操作载荷"), default=dict)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True, db_index=True)

    class Meta:
        app_label = "pipeline_diagnostics"
        verbose_name = _("Pipeline诊断操作审计")
        verbose_name_plural = _("Pipeline诊断操作审计")
        ordering = ["-id"]
        index_together = (("operator", "operation_type"), ("mode", "created_at"))

    def __unicode__(self):
        return "{}_{}_{}".format(self.case_id or "", self.operation_type, self.mode)
