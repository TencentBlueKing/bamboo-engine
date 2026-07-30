# -*- coding: utf-8 -*-
import json

from django.db import models


class JSONTextField(models.TextField):
    def get_prep_value(self, value):
        return json.dumps(value)

    def from_db_value(self, value, expression, connection, *args):
        if value is None:
            return value
        return json.loads(value)

    def to_python(self, value):
        value = super(JSONTextField, self).to_python(value)
        if value is None or isinstance(value, (dict, list)):
            return value
        return json.loads(value)


class EngineEventInbox(models.Model):
    id = models.BigAutoField("ID", primary_key=True)
    event_type = models.CharField("事件类型", max_length=32)
    source_type = models.CharField("来源类型", max_length=32, default="", blank=True)
    source_id = models.CharField("来源记录 ID", max_length=64, default="", blank=True)
    idempotency_key = models.CharField("幂等键", max_length=191, unique=True)
    root_pipeline_id = models.CharField("根流程 ID", max_length=33, default="", blank=True)
    node_id = models.CharField("节点 ID", max_length=33, default="", blank=True)
    version = models.CharField("节点执行版本", max_length=33, default="", blank=True)
    schedule_id = models.BigIntegerField("Schedule ID", null=True, blank=True)
    concurrency_key = models.CharField("并发域", max_length=80, default="", blank=True)
    payload_ref = models.CharField("原始数据引用", max_length=128, default="", blank=True)
    payload_digest = models.CharField("原始数据摘要", max_length=64, default="", blank=True)
    mode = models.CharField("模式", max_length=16, default="SHADOW")
    status = models.CharField("状态", max_length=20, default="PENDING")
    attempts = models.IntegerField("已尝试次数", default=0)
    next_attempt_at = models.DateTimeField("下次可处理时间", null=True, blank=True)
    accepted_at = models.DateTimeField("可靠接收时间", auto_now_add=True)
    converge_deadline_at = models.DateTimeField("收敛截止时间", null=True, blank=True)
    lease_owner = models.CharField("事件租约持有者", max_length=64, default="", blank=True)
    lease_generation = models.IntegerField("事件租约代次", default=0)
    lease_until = models.DateTimeField("事件租约到期", null=True, blank=True)
    last_error_code = models.CharField("最近错误码", max_length=64, default="", blank=True)
    last_error_at = models.DateTimeField("最近错误时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    result_summary = JSONTextField("结果摘要", default=dict, blank=True)

    class Meta:
        app_label = "pipeline_reliable_events"
        verbose_name = "引擎可靠事件"
        verbose_name_plural = "引擎可靠事件"
        ordering = ["-id"]
        index_together = (
            ("status", "next_attempt_at"),
            ("concurrency_key", "status", "next_attempt_at"),
            ("root_pipeline_id", "node_id", "version"),
        )

    def __unicode__(self):
        return "{}:{}({})".format(self.event_type, self.idempotency_key, self.status)


class EngineEventLane(models.Model):
    id = models.BigAutoField("ID", primary_key=True)
    concurrency_key = models.CharField("并发域", max_length=80, unique=True)
    lease_owner = models.CharField("通道租约持有者", max_length=64, default="", blank=True)
    lease_generation = models.IntegerField("通道租约代次", default=0)
    lease_until = models.DateTimeField("通道租约到期", null=True, blank=True)
    last_progress_at = models.DateTimeField("最近进展时间", null=True, blank=True)

    class Meta:
        app_label = "pipeline_reliable_events"
        verbose_name = "引擎事件通道"
        verbose_name_plural = "引擎事件通道"

    def __unicode__(self):
        return self.concurrency_key
