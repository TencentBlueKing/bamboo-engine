# -*- coding: utf-8 -*-
from bamboo_engine.builder.builder import generate_pipeline_token


class RollbackMixin:
    def set_pipeline_token(self, pipeline_tree: dict):
        """
        设置pipeline token
        """
        try:
            # 引用成功说明pipeline rollback 这个 app 是安装过的
            from pipeline.contrib.rollback.models import RollbackToken
        except Exception:
            return

        root_pipeline_id = pipeline_tree["id"]
        node_map = generate_pipeline_token(pipeline_tree)

        RollbackToken.objects.create(root_pipeline_id=root_pipeline_id, token=node_map)
