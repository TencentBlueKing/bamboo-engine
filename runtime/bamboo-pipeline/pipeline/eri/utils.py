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
import socket
from typing import Dict

from bamboo_engine.eri import ContextValueType
from celery import current_app
from django.conf import settings

CONTEXT_TYPE_MAP = {
    "plain": ContextValueType.PLAIN,
    "splice": ContextValueType.SPLICE,
    "lazy": ContextValueType.COMPUTE,
}

CONTEXT_VALUE_TYPE_MAP = {
    "plain": ContextValueType.PLAIN.value,
    "splice": ContextValueType.SPLICE.value,
    "lazy": ContextValueType.COMPUTE.value,
}


def caculate_final_references(original_references: Dict[str, set]) -> Dict[str, set]:
    """
    将变量的引用树展开，将树高减少为两层
    convert a:b, b:c,d -> a:b,c,d b:c,d
    """
    final_references = {k: set() for k in original_references.keys()}
    # resolve final references (BFS)
    for key, references in original_references.items():
        queue = []
        queue.extend(references)

        while queue:
            r = queue.pop()

            # processed
            if r in final_references[key]:
                continue

            final_references[key].add(r)
            if r in original_references:
                queue.extend(original_references[r])

    return final_references


def check_worker(connection=None):
    worker_list = []
    tries = 0
    WORKER_PING_TIMES = getattr(settings, "PIPELINE_WORKER_PING_TIMES", 2)
    while tries < WORKER_PING_TIMES:
        kwargs = {"timeout": tries + 1}
        if connection is not None:
            kwargs["connection"] = connection
        try:
            worker_list = current_app.control.ping(**kwargs)
        except socket.error as err:
            if tries >= WORKER_PING_TIMES - 1:
                raise err

        if worker_list:
            break

        tries += 1

    return True, worker_list
