# Generated for pipeline reliable events initial models.
from django.db import migrations, models

import pipeline.contrib.reliable_events.models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EngineEventInbox",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=32, verbose_name="事件类型")),
                ("source_type", models.CharField(blank=True, default="", max_length=32, verbose_name="来源类型")),
                ("source_id", models.CharField(blank=True, default="", max_length=64, verbose_name="来源记录 ID")),
                ("idempotency_key", models.CharField(max_length=191, unique=True, verbose_name="幂等键")),
                ("root_pipeline_id", models.CharField(blank=True, default="", max_length=33, verbose_name="根流程 ID")),
                ("node_id", models.CharField(blank=True, default="", max_length=33, verbose_name="节点 ID")),
                ("version", models.CharField(blank=True, default="", max_length=33, verbose_name="节点执行版本")),
                ("schedule_id", models.BigIntegerField(blank=True, null=True, verbose_name="Schedule ID")),
                ("concurrency_key", models.CharField(blank=True, default="", max_length=80, verbose_name="并发域")),
                ("payload_ref", models.CharField(blank=True, default="", max_length=128, verbose_name="原始数据引用")),
                ("payload_digest", models.CharField(blank=True, default="", max_length=64, verbose_name="原始数据摘要")),
                ("mode", models.CharField(default="SHADOW", max_length=16, verbose_name="模式")),
                ("status", models.CharField(default="PENDING", max_length=20, verbose_name="状态")),
                ("attempts", models.IntegerField(default=0, verbose_name="已尝试次数")),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True, verbose_name="下次可处理时间")),
                ("accepted_at", models.DateTimeField(auto_now_add=True, verbose_name="可靠接收时间")),
                ("converge_deadline_at", models.DateTimeField(blank=True, null=True, verbose_name="收敛截止时间")),
                ("lease_owner", models.CharField(blank=True, default="", max_length=64, verbose_name="事件租约持有者")),
                ("lease_generation", models.IntegerField(default=0, verbose_name="事件租约代次")),
                ("lease_until", models.DateTimeField(blank=True, null=True, verbose_name="事件租约到期")),
                ("last_error_code", models.CharField(blank=True, default="", max_length=64, verbose_name="最近错误码")),
                ("last_error_at", models.DateTimeField(blank=True, null=True, verbose_name="最近错误时间")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="完成时间")),
                ("result_summary", pipeline.contrib.reliable_events.models.JSONTextField(blank=True, default=dict, verbose_name="结果摘要")),
            ],
            options={
                "verbose_name": "引擎可靠事件",
                "verbose_name_plural": "引擎可靠事件",
                "ordering": ["-id"],
                "index_together": {
                    ("status", "next_attempt_at"),
                    ("concurrency_key", "status", "next_attempt_at"),
                    ("root_pipeline_id", "node_id", "version"),
                },
            },
        ),
        migrations.CreateModel(
            name="EngineEventLane",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                ("concurrency_key", models.CharField(max_length=80, unique=True, verbose_name="并发域")),
                ("lease_owner", models.CharField(blank=True, default="", max_length=64, verbose_name="通道租约持有者")),
                ("lease_generation", models.IntegerField(default=0, verbose_name="通道租约代次")),
                ("lease_until", models.DateTimeField(blank=True, null=True, verbose_name="通道租约到期")),
                ("last_progress_at", models.DateTimeField(blank=True, null=True, verbose_name="最近进展时间")),
            ],
            options={
                "verbose_name": "引擎事件通道",
                "verbose_name_plural": "引擎事件通道",
            },
        ),
    ]
