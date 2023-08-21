# -*- coding: utf-8 -*-
from django.db import models


class RollbackToken(models.Model):
    """
    回滚配置token信息
    """

    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    token = models.TextField("token信息", null=False)
    is_deleted = models.BooleanField("是否已经删除", default=False, help_text="表示当前实例是否删除")
