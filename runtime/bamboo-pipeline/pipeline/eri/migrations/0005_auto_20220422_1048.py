# Generated by Django 2.2.28 on 2022-04-22 02:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eri', '0004_state_inner_loop_'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contextvalue',
            name='code',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='计算型变量类型唯一标志'),
        ),
        migrations.AlterField(
            model_name='logentry',
            name='message',
            field=models.TextField(blank=True, null=True, verbose_name='日志内容'),
        ),
        migrations.AlterField(
            model_name='logentry',
            name='version',
            field=models.CharField(blank=True, default='', max_length=33, verbose_name='状态版本'),
        ),
        migrations.AlterField(
            model_name='process',
            name='destination_id',
            field=models.CharField(blank=True, default='', max_length=33, verbose_name='执行终点 ID'),
        ),
        migrations.AlterField(
            model_name='process',
            name='queue',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='所属队列'),
        ),
        migrations.AlterField(
            model_name='process',
            name='suspended_by',
            field=models.CharField(blank=True, db_index=True, default='', max_length=33, verbose_name='导致进程暂停的节点 ID'),
        ),
        migrations.AlterField(
            model_name='state',
            name='archived_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='归档时间'),
        ),
        migrations.AlterField(
            model_name='state',
            name='parent_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=33, verbose_name='父节点 ID'),
        ),
        migrations.AlterField(
            model_name='state',
            name='root_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=33, verbose_name='根节点 ID'),
        ),
        migrations.AlterField(
            model_name='state',
            name='started_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='开始时间'),
        ),
    ]
