# -*- coding: utf-8 -*-
import json
import logging

from django.core.serializers.json import DjangoJSONEncoder

from bamboo_engine.builder.builder import generate_pipeline_token

logger = logging.getLogger("bamboo_engine")


class RollbackMixin:
    def set_pipeline_token(self, pipeline_tree: dict):
        """
        设置pipeline token
        """
        try:
            # 引用成功说明pipeline rollback 这个 app 是安装过的
            from pipeline.contrib.rollback.models import RollbackToken
        except Exception as e:
            logger.error(
                "[RollbackMixin][set_pipeline_token] import RollbackToken error, "
                "Please check whether the  rollback app is installed correctly, err={}".format(e)
            )
            return

        root_pipeline_id = pipeline_tree["id"]
        node_map = generate_pipeline_token(pipeline_tree)

        RollbackToken.objects.create(root_pipeline_id=root_pipeline_id, token=json.dumps(node_map))

    def set_node_snapshot(self, root_pipeline_id, node_id, code, version, context_values, inputs, outputs):
        """
        创建一分节点快照
        """
        try:
            # 引用成功说明pipeline rollback 这个 app 是安装过的
            from pipeline.contrib.rollback.models import RollbackNodeSnapshot
        except Exception as e:
            logger.error(
                "[RollbackMixin][set_node_snapshot] import RollbackNodeSnapshot error, "
                "Please check whether the rollback app is installed correctly, err={}".format(e)
            )
            return

        RollbackNodeSnapshot.objects.create(
            root_pipeline_id=root_pipeline_id,
            node_id=node_id,
            code=code,
            version=version,
            context_values=json.dumps(context_values, cls=DjangoJSONEncoder),
            inputs=json.dumps(inputs, cls=DjangoJSONEncoder),
            outputs=json.dumps(outputs, cls=DjangoJSONEncoder),
        )

    def start_rollback(self, root_pipeline_id, node_id):
        """
        新建一个回滚任务
        """
        try:
            # 引用成功说明pipeline rollback 这个 app 是安装过的
            from pipeline.contrib.rollback.handler import RollbackDispatcher
            from pipeline.contrib.rollback.models import RollbackPlan
        except Exception as e:
            logger.error(
                "[RollbackMixin][set_pipeline_token] import RollbackHandler or RollbackPlan error, "
                "Please check whether the rollback app is installed correctly, err={}".format(e)
            )
            return

        try:
            rollback_plan = RollbackPlan.objects.get(
                root_pipeline_id=root_pipeline_id, start_node_id=node_id, is_expired=False
            )
            handler = RollbackDispatcher(root_pipeline_id=root_pipeline_id, mode=rollback_plan.mode)
            handler.rollback(rollback_plan.start_node_id, rollback_plan.target_node_id)
        except Exception as e:
            logger.error("[RollbackMixin][start_rollback] start a rollback task error, err={}".format(e))
            return
