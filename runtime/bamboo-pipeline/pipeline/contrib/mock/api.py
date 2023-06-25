# -*- coding: utf-8 -*-
import json
import re

from django.db import transaction

from pipeline.eri.models import State
from pipeline.eri.models import ContextValue
from pipeline.eri.models import ExecutionData as DBExecutionData
from bamboo_engine import states

from pipeline.contrib.exceptions import UpdatePipelineContextException

formatted_key_pattern = re.compile(r"^\${(.*?)}$")


def update_pipeline_context(pipeline_id, node_id, context_values):
    """
    批量修改任务某个节点的输出
    :param pipeline_id: pipeline的id
    :param node_id: 节点id
    :param context_values: {
        "${code}": 200
    }
    :return:
    """

    pipeline_state = State.objects.filter(node_id=pipeline_id).first()
    if not pipeline_state:
        raise UpdatePipelineContextException(
            "update context values failed: pipeline state not exist, pipeline_id={}".format(pipeline_id))

    if pipeline_state.name != states.RUNNING:
        raise UpdatePipelineContextException(
            "update context values failed: the task of non-running state is not allowed to roll back, pipeline_id={}".format(
                pipeline_id))

    node_state = State.objects.filter(node_id=node_id).first()
    if not node_state:
        raise UpdatePipelineContextException(
            "update context values failed: node state not exist, pipeline_id={}".format(pipeline_id))

    if node_state.name != states.FAILED:
        raise UpdatePipelineContextException(
            "update context values failed: the task of non-running state is not allowed to update, node_id={}".format(
                node_id))

    if "${_system}" in context_values.keys():
        raise UpdatePipelineContextException("${_system} is built-in variable that is not allowed to be updated")

    # 获取流程内满足上下文的key
    context_value_queryset = ContextValue.objects.filter(pipeline_id=pipeline_id, key__in=context_values.keys())
    context_value_list = []

    for context_value in context_value_queryset:
        if context_value.key in context_values.keys():
            context_value.value = context_values.get(context_value.key)
            context_value_list.append(context_value)
    with transaction.atomic():
        try:
            ContextValue.objects.bulk_update(context_value_list, fields=["value"])
        except Exception as e:
            raise UpdatePipelineContextException("update context value failed, please check it, error={}".format(e))

        outputs = {}
        try:
            for key, value in context_values.items():
                if formatted_key_pattern.match(key):
                    key = key[2:-1]
                outputs[key] = value
            execution_data = DBExecutionData.objects.get(node_id=node_id)
            detail = json.loads(execution_data.outputs)
            detail.update(outputs)
            execution_data.outputs = json.dumps(detail)
            execution_data.save()

        except Exception as e:
            raise UpdatePipelineContextException(
                "update node outputs value failed, please check it,outputs={}, error={}".format(outputs, e))
