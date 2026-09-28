# -*- coding: utf-8 -*-

import django.db.models.deletion
from django.db import migrations, models

import pipeline.contrib.diagnostics.models


class Migration(migrations.Migration):

    dependencies = [("pipeline_diagnostics", "0002_diagnosticscancursor")]

    operations = [
        migrations.CreateModel(
            name="DiagnosticRecovery",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                ("root_pipeline_id", models.CharField(db_index=True, max_length=64, verbose_name="根 Pipeline ID")),
                ("node_id", models.CharField(max_length=64, verbose_name="节点ID")),
                ("stuck_type", models.CharField(db_index=True, max_length=64, verbose_name="卡住类型")),
                ("process_id", models.BigIntegerField(blank=True, null=True, verbose_name="进程ID")),
                ("fingerprint", models.CharField(max_length=255, verbose_name="消息指纹")),
                ("message", pipeline.contrib.diagnostics.models.JSONTextField(default=dict, verbose_name="重放消息")),
                (
                    "trigger",
                    models.CharField(choices=[("manual", "人工"), ("auto", "自动")], max_length=16, verbose_name="触发方式"),
                ),
                (
                    "mode",
                    models.CharField(choices=[("preview", "预演"), ("apply", "执行")], max_length=16, verbose_name="模式"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("previewed", "已预演"),
                            ("blocked", "已阻断"),
                            ("dispatched", "已派发"),
                            ("applied", "已生效"),
                            ("obsolete", "已过期"),
                            ("ineffective", "无效"),
                            ("manual_required", "转人工"),
                        ],
                        max_length=32,
                        verbose_name="状态",
                    ),
                ),
                ("operator", models.CharField(blank=True, default="", max_length=64, verbose_name="操作人")),
                ("detail", pipeline.contrib.diagnostics.models.JSONTextField(default=dict, verbose_name="详情")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("settled_at", models.DateTimeField(blank=True, null=True, verbose_name="复核时间")),
                (
                    "case",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recoveries",
                        to="pipeline_diagnostics.diagnosticcase",
                        verbose_name="诊断案例",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pipeline诊断恢复记录",
                "verbose_name_plural": "Pipeline诊断恢复记录",
                "ordering": ["-id"],
                "index_together": {("case", "fingerprint"), ("status", "settled_at", "created_at")},
            },
        ),
    ]
