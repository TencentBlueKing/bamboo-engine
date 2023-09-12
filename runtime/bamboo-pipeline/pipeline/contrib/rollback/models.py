# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext_lazy as _


class RollbackToken(models.Model):
    """
    回滚配置token信息
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    token = models.TextField(_("token map"), null=False)
    is_deleted = models.BooleanField(_("is deleted"), default=False, help_text=_("is deleted"))


class RollbackSnapshot(models.Model):
    """
    节点执行的快照信息
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    graph = models.TextField(verbose_name="rollback graph", null=False)
    node_access_record = models.TextField(verbose_name="node access record")
    skip_rollback_nodes = models.TextField(verbose_name="skip rollback nodes")
    start_node_id = models.CharField(verbose_name="start node id", max_length=64)
    target_node_id = models.CharField(verbose_name="target_node_id", max_length=64)
    is_expired = models.BooleanField(verbose_name="is expired", default=False)


class RollbackNodeSnapshot(models.Model):
    """
    节点快照
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    node_id = models.CharField(verbose_name="node_id", max_length=64)
    code = models.CharField(verbose_name="node_code", max_length=64)
    version = models.CharField(verbose_name=_("version"), null=False, max_length=33)
    inputs = models.TextField(verbose_name=_("node inputs"))
    outputs = models.TextField(verbose_name=_("node outputs"))
    context_values = models.TextField(verbose_name=_("pipeline context values"))
    rolled_back = models.BooleanField(_("whether the node rolls back"), default=False)


class RollbackPlan(models.Model):
    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    start_node_id = models.CharField(verbose_name="start node id", max_length=64)
    target_node_id = models.CharField(verbose_name="target_node_id", max_length=64)
    is_expired = models.BooleanField(verbose_name="is expired", default=False)