# -*- coding: utf-8 -*-

from django.db import migrations, models

import pipeline.contrib.diagnostics.models


class Migration(migrations.Migration):

    dependencies = [("pipeline_diagnostics", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="DiagnosticScanCursor",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, unique=True, verbose_name="扫描器")),
                ("position", models.DateTimeField(blank=True, null=True, verbose_name="时间水位")),
                ("position_id", models.BigIntegerField(default=0, verbose_name="ID 水位")),
                ("extra", pipeline.contrib.diagnostics.models.JSONTextField(default=dict, verbose_name="扫描状态")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"verbose_name": "Pipeline诊断扫描水位", "verbose_name_plural": "Pipeline诊断扫描水位"},
        ),
    ]
