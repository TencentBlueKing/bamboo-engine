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
import time

from bamboo_engine import Engine

from bamboo_engine.builder import *  # noqa
from pipeline.engine import states
from pipeline.eri.models import Process, State
from pipeline.eri.runtime import BambooDjangoRuntime

from pipeline.contrib.rollback import api


def test_rollback_sample_pipeline():
    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="callback_node")
    act_1 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()
    start.extend(act_0).extend(act_1).extend(end)
    pipeline = build_tree(start)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})
    time.sleep(3)

    state = runtime.get_state(act_0.id)
    engine.callback(act_0.id, state.version, {"bit": 1})
    pipeline_id = pipeline["id"]
    time.sleep(3)
    assert State.objects.filter(node_id=act_0.id, name=states.FINISHED).exists()
    api.rollback(root_pipeline_id=pipeline_id, node_id=act_0.id)
    time.sleep(3)
    process = Process.objects.get(root_pipeline_id=pipeline_id, parent_id=-1)
    # 此时最新进程被指向了最新的node_id
    assert process.current_node_id == act_0.id
    # 此时第一个节点重回RUNNING状态
    assert State.objects.filter(node_id=act_0.id, name=states.RUNNING).exists()


def test_rollback_pipeline_with_exclusive_gateway():
    """
                    -> act_0
    开始 -> 分支网关             -> 汇聚网关 -> act_2 -> 结束
                   -> act_1

    当执行到 act_2 时，此时回退到act_0 应当能够再次回到 act_2
    """

    runtime = BambooDjangoRuntime()

    start = EmptyStartEvent()
    eg = ExclusiveGateway(
        conditions={0: "True == True", 1: "True == False"}
    )
    act_0 = ServiceActivity(component_code="callback_node")
    act_1 = ServiceActivity(component_code="callback_node")
    act_2 = ServiceActivity(component_code="callback_node")

    cg = ConvergeGateway()
    end = EmptyEndEvent()

    start.extend(eg).connect(act_0, act_1).converge(cg).extend(act_2).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})
    time.sleep(3)

    state = runtime.get_state(act_0.id)
    engine.callback(act_0.id, state.version, {"bit": 1})

    time.sleep(3)
    pipeline_id = pipeline["id"]

    process = Process.objects.get(root_pipeline_id=pipeline_id, parent_id=-1)

    # 此时执行到了act_2
    assert process.current_node_id == act_2.id

    api.rollback(pipeline_id, act_0.id)
    time.sleep(3)

    process.refresh_from_db()
    # 此时最新进程被指向了最新的node_id
    assert process.current_node_id == act_0.id
    # 此时第一个节点重回RUNNING状态
    assert State.objects.filter(node_id=act_0.id, name=states.RUNNING).exists()


def test_rollback_pipeline_with_conditional_parallel():
    """
                    -> act_1
    开始 -> act_0 并行网关             -> 汇聚网关 -> act_3 -> 结束
                   -> act_2

    当执行到 act_2 时，此时回退到act_0 应当能够再次回到 act_2
    """

    runtime = BambooDjangoRuntime()

    start = EmptyStartEvent()
    act_0 = ServiceActivity(component_code="debug_node")
    pg = ParallelGateway()

    act_1 = ServiceActivity(component_code="debug_node")
    act_2 = ServiceActivity(component_code="debug_node")
    cg = ConvergeGateway()
    act_3 = ServiceActivity(component_code="callback_node")
    end = EmptyEndEvent()

    start.extend(act_0).extend(pg).connect(act_1, act_2).converge(cg).extend(act_3).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    time.sleep(3)
    pipeline_id = pipeline["id"]

    process = Process.objects.get(root_pipeline_id=pipeline_id, parent_id=-1)
    # 此时执行到了act_2
    assert process.current_node_id == act_3.id

    # 此时回到开始节点
    api.rollback(pipeline_id, act_0.id)
    time.sleep(3)

    process.refresh_from_db()
    # 此时第二次执行到act_2
    assert process.current_node_id == act_3.id
    # 此时第一个节点重回RUNNING状态
    assert State.objects.filter(node_id=act_3.id, name=states.RUNNING).exists()
    # callback act_2 此时流程结束
    state = runtime.get_state(act_3.id)
    engine.callback(act_3.id, state.version, {"bit": 1})
    time.sleep(3)

    assert State.objects.filter(node_id=pipeline_id, name=states.FINISHED).exists()
