from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("eri", "0005_auto_20220422_1048")]
    operations = [
        migrations.CreateModel(
            name="SyncAdvanceCheckpoint",
            fields=[
                (
                    "process",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="eri.process",
                    ),
                ),
                ("from_node", models.CharField(max_length=33)),
                ("from_version", models.CharField(max_length=33)),
                ("to_node", models.CharField(max_length=33)),
                ("phase", models.CharField(max_length=16)),
                ("prepared_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]
