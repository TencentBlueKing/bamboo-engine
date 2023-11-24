# Generated by Django 3.2.18 on 2023-10-20 12:34

import pipeline.contrib.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("rollback", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rollbacknodesnapshot",
            name="context_values",
            field=pipeline.contrib.fields.SerializerField(verbose_name="pipeline context values"),
        ),
        migrations.AlterField(
            model_name="rollbacknodesnapshot",
            name="inputs",
            field=pipeline.contrib.fields.SerializerField(verbose_name="node inputs"),
        ),
        migrations.AlterField(
            model_name="rollbacknodesnapshot",
            name="outputs",
            field=pipeline.contrib.fields.SerializerField(verbose_name="node outputs"),
        ),
    ]
