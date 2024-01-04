# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _
from pipeline.contrib.fields import SerializerField
from pipeline.contrib.rollback.constants import TOKEN


class RollbackToken(models.Model):
    """
    回滚配置token信息
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64, db_index=True)
    token = models.TextField(_("token map"), null=False)
    is_deleted = models.BooleanField(_("is deleted"), default=False, help_text=_("is deleted"), db_index=True)


class RollbackSnapshot(models.Model):
    """
    节点执行的快照信息
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64, db_index=True)
    graph = models.TextField(verbose_name="rollback graph", null=False)
    node_access_record = models.TextField(verbose_name="node access record")
    skip_rollback_nodes = models.TextField(verbose_name="skip rollback nodes")
    other_nodes = models.TextField(verbose_name="other nodes")
    start_node_id = models.CharField(verbose_name="start node id", max_length=64, db_index=True)
    target_node_id = models.CharField(verbose_name="target_node_id", max_length=64, db_index=True)
    is_expired = models.BooleanField(verbose_name="is expired", default=False, db_index=True)


class RollbackNodeSnapshot(models.Model):
    """
    节点快照
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64, db_index=True)
    node_id = models.CharField(verbose_name="node_id", max_length=64, db_index=True)
    code = models.CharField(verbose_name="node_code", max_length=64)
    version = models.CharField(verbose_name=_("version"), null=False, max_length=33)
    inputs = SerializerField(verbose_name=_("node inputs"))
    outputs = SerializerField(verbose_name=_("node outputs"))
    context_values = SerializerField(verbose_name=_("pipeline context values"))
    rolled_back = models.BooleanField(_("whether the node rolls back"), default=False)


class RollbackPlan(models.Model):
    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64, db_index=True)
    start_node_id = models.CharField(verbose_name="start node id", max_length=64, db_index=True)
    target_node_id = models.CharField(verbose_name="target_node_id", max_length=64, db_index=True)
    mode = models.CharField(verbose_name="rollback mode", max_length=32, default=TOKEN)
    options = SerializerField(verbose_name="rollback options", default={})
    is_expired = models.BooleanField(verbose_name="is expired", default=False)
