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
# Generated by Django 1.11.2 on 2017-11-15 12:09


from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("component_framework", "0002_delete_componentmodel"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComponentModel",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=255, unique=True, verbose_name="\u7ec4\u4ef6\u7f16\u7801")),
                ("name", models.CharField(max_length=255, verbose_name="\u7ec4\u4ef6\u540d\u79f0")),
                ("status", models.BooleanField(default=True, verbose_name="\u7ec4\u4ef6\u662f\u5426\u53ef\u7528")),
            ],
            options={"ordering": ["-id"], "verbose_name": "\u7ec4\u4ef6", "verbose_name_plural": "\u7ec4\u4ef6"},
        ),
    ]
