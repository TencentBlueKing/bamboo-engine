# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bamboo_engine.eri.models import ProcessInfo
from os import pipe
import pytest
from mock import MagicMock, call, patch

from bamboo_engine.api import preview_node_inputs
from bamboo_engine.eri import SuspendedProcessInfo, NodeType, Variable
from bamboo_engine import states, exceptions
from bamboo_engine.engine import Engine


def test_run_pipeline():
    process_id = 1
    start_event_id = "token"
    pipeline_id = "pipeline_id"
    options = {"priority": 100, "queue": "q"}

    runtime = MagicMock()
    runtime.prepare_run_pipeline = MagicMock(return_value=process_id)
    runtime.execute = MagicMock()
    validator = MagicMock()

    pipeline = {"start_event": {"id": start_event_id}, "id": pipeline_id}
    root_pipeline_data = {"k": "v"}
    root_pipeline_context = {"k1": "v1"}
    subprocess_context = {"k2": "v2"}

    engine = Engine(runtime=runtime)

    with patch("bamboo_engine.engine.validator", validator):
        engine.run_pipeline(
            pipeline=pipeline,
            root_pipeline_data=root_pipeline_data,
            root_pipeline_context=root_pipeline_context,
            subprocess_context=subprocess_context,
            **options
        )

    validator.validate_and_process_pipeline.assert_called_once_with(pipeline, False)
    runtime.pre_prepare_run_pipeline.assert_called_once_with(
        pipeline, root_pipeline_data, root_pipeline_context, subprocess_context, **options
    )
    runtime.prepare_run_pipeline.assert_called_once_with(
        pipeline, root_pipeline_data, root_pipeline_context, subprocess_context, **options
    )
    runtime.post_prepare_run_pipeline.assert_called_once_with(
        pipeline, root_pipeline_data, root_pipeline_context, subprocess_context, **options
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id, node_id=start_event_id, root_pipeline_id=pipeline_id, parent_pipeline_id=pipeline_id
    )


def test_pause_pipeline():
    pipeline_id = "pid"

    runtime = MagicMock()
    runtime.has_state = MagicMock(return_value=True)

    engine = Engine(runtime=runtime)
    engine.pause_pipeline(pipeline_id)

    runtime.has_state.assert_called_once_with(pipeline_id)
    runtime.pre_pause_pipeline.assert_called_once_with(pipeline_id)
    runtime.set_state.assert_called_once_with(node_id=pipeline_id, to_state=states.SUSPENDED)
    runtime.post_pause_pipeline.assert_called_once_with(pipeline_id)


def test_pause_pipeline__pipeline_not_exist():
    pipeline_id = "pid"

    runtime = MagicMock()
    runtime.has_state = MagicMock(return_value=False)
    runtime.pre_pause_pipeline = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.NotFoundError):
        engine.pause_pipeline(pipeline_id)


def test_revoke_pipeline():
    pipeline_id = "pid"

    runtime = MagicMock()
    runtime.has_state = MagicMock(return_value=True)

    engine = Engine(runtime=runtime)
    engine.revoke_pipeline(pipeline_id)

    runtime.has_state.assert_called_once_with(pipeline_id)
    runtime.pre_revoke_pipeline.assert_called_once_with(pipeline_id)
    runtime.set_state.assert_called_once_with(node_id=pipeline_id, to_state=states.REVOKED)
    runtime.post_revoke_pipeline.assert_called_once_with(pipeline_id)


def test_revoke_pipeline__pipeline_not_exist():
    pipeline_id = "pid"

    runtime = MagicMock()
    runtime.has_state = MagicMock(return_value=False)
    runtime.pre_revoke_pipeline = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.NotFoundError):
        engine.revoke_pipeline(pipeline_id)


def test_resume_pipeline():
    pipeline_id = "pid"
    suspended_process_info = [
        SuspendedProcessInfo(process_id=1, current_node=2, root_pipeline_id=pipeline_id, pipeline_stack=[pipeline_id]),
        SuspendedProcessInfo(process_id=3, current_node=4, root_pipeline_id=pipeline_id, pipeline_stack=[pipeline_id]),
    ]
    state = MagicMock()
    state.name = "SUSPENDED"

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_suspended_process_info = MagicMock(return_value=suspended_process_info)

    engine = Engine(runtime=runtime)
    engine.resume_pipeline(pipeline_id)

    runtime.get_state.assert_called_once_with(pipeline_id)
    runtime.get_suspended_process_info.assert_called_once_with(pipeline_id)
    runtime.pre_resume_pipeline.assert_called_once_with(pipeline_id)
    runtime.set_state.assert_called_once_with(node_id=pipeline_id, to_state=states.RUNNING)
    runtime.batch_resume.assert_called_once_with(
        process_id_list=[
            suspended_process_info[0].process_id,
            suspended_process_info[1].process_id,
        ]
    )
    runtime.execute.assert_has_calls(
        [
            call(
                process_id=suspended_process_info[0].process_id,
                node_id=suspended_process_info[0].current_node,
                root_pipeline_id=pipeline_id,
                parent_pipeline_id=pipeline_id,
            ),
            call(
                process_id=suspended_process_info[1].process_id,
                node_id=suspended_process_info[1].current_node,
                root_pipeline_id=pipeline_id,
                parent_pipeline_id=pipeline_id,
            ),
        ]
    )
    runtime.post_resume_pipeline.assert_called_once_with(pipeline_id)


def test_resume_pipeline__state_not_match():
    pipeline_id = "pid"
    suspended_process_info = []
    state = MagicMock()
    state.name = "RUNNING"

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.resume_pipeline(pipeline_id)

    runtime.get_state.assert_called_once_with(pipeline_id)
    runtime.set_state.assert_not_called()


def test_resume_pipeline__can_not_find_suspended_process():
    pipeline_id = "pid"
    suspended_process_info = []
    state = MagicMock()
    state.name = "SUSPENDED"

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_suspended_process_info = MagicMock(return_value=suspended_process_info)

    engine = Engine(runtime=runtime)
    engine.resume_pipeline(pipeline_id)

    runtime.get_state.assert_called_once_with(pipeline_id)
    runtime.get_suspended_process_info.assert_called_once_with(pipeline_id)
    runtime.pre_resume_pipeline.assert_called_once_with(pipeline_id)
    runtime.set_state.assert_called_once_with(node_id=pipeline_id, to_state=states.RUNNING)
    runtime.batch_resume.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.post_resume_pipeline.assert_called_once_with(pipeline_id)


def test_pause_node_appoint():
    node_id = "nid"
    node_type = NodeType.ServiceActivity

    node = MagicMock()
    node.type = node_type

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)

    engine = Engine(runtime=runtime)
    engine.pause_node_appoint(node_id)

    runtime.pre_pause_node.assert_called_once_with(node_id)
    runtime.set_state.assert_called_once_with(node_id=node_id, to_state=states.SUSPENDED)
    runtime.post_pause_node.assert_called_once_with(node_id)


def test_pause_node_appoint__node_type_is_subprocess():
    node_id = "nid"
    node_type = NodeType.SubProcess

    node = MagicMock()
    node.type = node_type

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.pre_pause_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.pause_node_appoint(node_id)


def test_resume_node_appoint():
    node_id = "nid"
    node_type = NodeType.ServiceActivity
    pipeline_id = "pid"

    node = MagicMock()
    node.type = node_type
    suspended_process_info_list = [
        SuspendedProcessInfo("1", "2", pipeline_id, [pipeline_id]),
    ]

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_suspended_process_info = MagicMock(return_value=suspended_process_info_list)

    engine = Engine(runtime=runtime)
    engine.resume_node_appoint(node_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.pre_resume_node.assert_called_once_with(node_id)
    runtime.set_state.assert_called_once_with(node_id=node_id, to_state=states.READY)
    runtime.get_suspended_process_info.assert_called_once_with(node_id)
    runtime.resume.assert_called_once_with(process_id=suspended_process_info_list[0].process_id)
    runtime.execute.assert_called_once_with(
        process_id=suspended_process_info_list[0].process_id,
        node_id=suspended_process_info_list[0].current_node,
        root_pipeline_id=pipeline_id,
        parent_pipeline_id=pipeline_id,
    )
    runtime.post_resume_node.assert_called_once_with(node_id)


def test_resume_node_appoint__node_type_is_subprocess():
    node_id = "nid"
    node_type = NodeType.SubProcess

    node = MagicMock()
    node.type = node_type

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.pre_resume_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.resume_node_appoint(node_id)


def test_resume_node_appoint__without_suspended_process():
    node_id = "nid"
    node_type = NodeType.ServiceActivity

    node = MagicMock()
    node.type = node_type
    suspended_process_info_list = []

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_suspended_process_info = MagicMock(return_value=suspended_process_info_list)
    runtime.resume = MagicMock(side_effect=Exception)
    runtime.execute = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    engine.resume_node_appoint(node_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.pre_resume_node.assert_called_once_with(node_id)
    runtime.set_state.assert_called_once_with(node_id=node_id, to_state=states.READY)
    runtime.get_suspended_process_info.assert_called_once_with(node_id)
    runtime.resume.assert_not_called()
    runtime.execute.assert_not_called()
    runtime.post_resume_node.assert_called_once_with(node_id)


def test_retry_node():
    node_id = "nid"
    process_id = "pid"
    pipeline_id = "pipeline_id"
    data = {}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED
    state.started_time = "started_time"
    state.archived_time = "archived_time"
    state.loop = 1
    state.skip = True
    state.retry = 0
    state.version = "version"

    execution_data = MagicMock()
    execution_data.inputs = "inputs"
    execution_data.outputs = "outputs"

    process_info = ProcessInfo(
        process_id=process_id,
        destination_id="did",
        parent_id=2,
        root_pipeline_id=pipeline_id,
        pipeline_stack=[pipeline_id],
    )

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_execution_data = MagicMock(return_value=execution_data)

    engine = Engine(runtime=runtime)
    engine.retry_node(node_id, data)

    runtime.pre_retry_node.assert_called_once_with(node_id, data)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.set_data_inputs.assert_called_once_with(node_id, data)
    runtime.add_history.assert_called_once_with(
        node_id=node_id,
        started_time=state.started_time,
        archived_time=state.archived_time,
        loop=state.loop,
        skip=state.skip,
        retry=state.retry,
        version=state.version,
        inputs=execution_data.inputs,
        outputs=execution_data.outputs,
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.READY,
        is_retry=True,
        refresh_version=True,
        clear_started_time=True,
        clear_archived_time=True,
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id,
        node_id=node_id,
        root_pipeline_id=process_info.root_pipeline_id,
        parent_pipeline_id=process_info.top_pipeline_id,
    )
    runtime.post_retry_node.assert_called_once_with(node_id, data)


def test_retry_node__state_is_not_failed():
    node_id = "nid"
    data = {}

    state = MagicMock()
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.pre_retry_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.retry_node(node_id, data)


def test_retry_node__can_retry_is_false():
    node_id = "nid"
    process_id = "pid"
    data = {}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED

    node = MagicMock()
    node.can_retry = False

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_node = MagicMock(return_value=node)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.retry_node(node_id, data)


def test_retry_node__can_not_find_sleep_process():
    node_id = "nid"
    data = {}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=None)
    runtime.pre_retry_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.retry_node(node_id, data)


def test_retry_node__with_none_data():
    node_id = "nid"
    process_id = "pid"

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED
    state.started_time = "started_time"
    state.archived_time = "archived_time"
    state.loop = 1
    state.skip = True
    state.retry = 0
    state.version = "version"

    process_info = ProcessInfo(
        process_id=process_id, destination_id="did", parent_id=2, root_pipeline_id="p", pipeline_stack=["p"]
    )

    execution_data = MagicMock()
    execution_data.inputs = "inputs"
    execution_data.outputs = "outputs"

    runtime = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_execution_data = MagicMock(return_value=execution_data)

    engine = Engine(runtime=runtime)
    engine.retry_node(node_id)

    runtime.pre_retry_node.assert_called_once_with(node_id, None)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.set_data_inputs.assert_not_called()
    runtime.add_history.assert_called_once_with(
        node_id=node_id,
        started_time=state.started_time,
        archived_time=state.archived_time,
        loop=state.loop,
        skip=state.skip,
        retry=state.retry,
        version=state.version,
        inputs=execution_data.inputs,
        outputs=execution_data.outputs,
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.READY,
        is_retry=True,
        refresh_version=True,
        clear_started_time=True,
        clear_archived_time=True,
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id, node_id=node_id, root_pipeline_id="p", parent_pipeline_id="p"
    )
    runtime.post_retry_node.assert_called_once_with(node_id, None)


def test_skip_node():
    node_id = "nid"
    process_id = "pid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity
    node.can_skip = True
    node.target_nodes = ["target_node"]

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED
    state.started_time = "started_time"
    state.archived_time = "archived_time"
    state.loop = 1
    state.skip = True
    state.retry = 0
    state.version = "version"

    process_info = ProcessInfo(
        process_id=process_id, destination_id="did", parent_id=2, root_pipeline_id="p", pipeline_stack=["p", "nid"]
    )

    execution_data = MagicMock()
    execution_data.inputs = "inputs"
    execution_data.outputs = "outputs"

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_execution_data = MagicMock(return_value=execution_data)

    engine = Engine(runtime=runtime)
    engine.skip_node(node_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.pre_skip_node.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id(node_id)
    runtime.add_history.assert_called_once_with(
        node_id=node_id,
        started_time=state.started_time,
        archived_time=state.archived_time,
        loop=state.loop,
        skip=state.skip,
        retry=state.retry,
        version=state.version,
        inputs=execution_data.inputs,
        outputs=execution_data.outputs,
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.FINISHED,
        is_skip=True,
        refresh_version=True,
        set_archive_time=True,
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id, node_id=node.target_nodes[0], root_pipeline_id="p", parent_pipeline_id="nid"
    )
    runtime.post_skip_node.assert_called_once_with(node_id)


def test_skip_node__node_can_not_skip():
    node_id = "nid"
    process_id = "pid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity
    node.can_skip = False

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.pre_skip_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_node(node_id)


def test_skip_node__node_type_not_fit():
    node_id = "nid"
    process_id = "pid"

    node = MagicMock()
    node.type = NodeType.SubProcess
    node.can_skip = True

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.pre_skip_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_node(node_id)


def test_skip_node__state_is_not_failed():
    node_id = "nid"
    process_id = "pid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity
    node.can_skip = True
    node.target_nodes = ["target_node"]

    state = MagicMock()
    state.node_id = node_id
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.pre_skip_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_node(node_id)

    runtime.get_state.assert_called_once_with(node_id)


def test_skip_node__can_not_find_sleep_process():
    node_id = "nid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity
    node.can_skip = True
    node.target_nodes = ["target_node"]

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=None)
    runtime.pre_retry_node = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_node(node_id)

    runtime.get_state.assert_called_once_with(node_id)


def test_skip_exclusive_gateway():
    node_id = "nid"
    process_id = "pid"
    flow_id = "flow_1"

    node = MagicMock()
    node.id = node_id
    node.type = NodeType.ExclusiveGateway
    node.targets = {flow_id: "target_1"}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED
    state.started_time = "started_time"
    state.archived_time = "archived_time"
    state.loop = 1
    state.skip = True
    state.retry = 0
    state.version = "version"

    process_info = ProcessInfo(
        process_id=process_id, destination_id="did", parent_id=2, root_pipeline_id="p", pipeline_stack=["p"]
    )

    execution_data = MagicMock()
    execution_data.inputs = "inputs"
    execution_data.outputs = "outputs"

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.pre_skip_exclusive_gateway = MagicMock()
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_execution_data = MagicMock(return_value=execution_data)

    engine = Engine(runtime=runtime)
    engine.skip_exclusive_gateway(node_id, flow_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.pre_skip_exclusive_gateway.assert_called_once_with(node_id, flow_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.add_history.assert_called_once_with(
        node_id=node_id,
        started_time=state.started_time,
        archived_time=state.archived_time,
        loop=state.loop,
        skip=state.skip,
        retry=state.retry,
        version=state.version,
        inputs=execution_data.inputs,
        outputs=execution_data.outputs,
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.FINISHED,
        is_skip=True,
        refresh_version=True,
        set_archive_time=True,
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id, node_id=node.targets[flow_id], root_pipeline_id="p", parent_pipeline_id="p"
    )
    runtime.post_skip_exclusive_gateway.assert_called_once_with(node_id, flow_id)


def test_skip_exclusive_gateway__node_type_not_fit():
    node_id = "nid"
    flow_id = "flow_1"

    node = MagicMock()
    node.type = NodeType.ParallelGateway

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_exclusive_gateway(node_id, flow_id)


def test_skip_exclusive_gateway__node_is_not_failed():
    node_id = "nid"
    process_id = "pid"
    flow_id = "flow_1"

    node = MagicMock()
    node.type = NodeType.ExclusiveGateway
    node.can_skip = True
    node.targets = {flow_id: "target1"}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.pre_skip_exclusive_gateway = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_exclusive_gateway(node_id, flow_id)

    runtime.get_state.assert_called_once_with(node_id)


def test_skip_exclusive_gateway__can_not_find_sleep_proces():
    node_id = "nid"
    flow_id = "flow_1"

    node = MagicMock()
    node.type = NodeType.ExclusiveGateway
    node.targets = {flow_id: "target1"}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=None)
    runtime.pre_skip_exclusive_gateway = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_exclusive_gateway(node_id, flow_id)

    runtime.get_state.assert_called_once_with(node_id)


def test_skip_conditional_parallel_gateway():
    node_id = "nid"
    process_id = "pid"
    root_pipeline_id = "r_pid"
    top_pipeline_id = "t_pid"
    pipeline_stack = "p_stack"
    flow_ids = ["flow_1", "flow_2"]
    converge_gateway_id = "converge_gateway_id"
    child_1_id = "target_1"
    child_2_id = "target_2"
    child_1_process_id = "child_1_pid"
    child_2_process_id = "child_2_pid"

    node = MagicMock()
    node.id = node_id
    node.type = NodeType.ConditionalParallelGateway
    node.targets = {"flow_1": child_1_id, "flow_2": child_2_id}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.FAILED
    state.started_time = "started_time"
    state.archived_time = "archived_time"
    state.loop = 1
    state.skip = True
    state.retry = 0
    state.version = "version"

    execution_data = MagicMock()
    execution_data.inputs = "inputs"
    execution_data.outputs = "outputs"

    process_info = MagicMock()
    process_info.process_id = process_id
    process_info.root_pipeline_id = root_pipeline_id
    process_info.pipeline_stack = pipeline_stack
    process_info.top_pipeline_id = top_pipeline_id

    dispatch_process_1 = MagicMock()
    dispatch_process_1.process_id = child_1_process_id
    dispatch_process_1.node_id = child_1_id
    dispatch_process_2 = MagicMock()
    dispatch_process_2.process_id = child_2_process_id
    dispatch_process_2.node_id = child_2_id

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_process_info = MagicMock(return_value=process_info)
    runtime.pre_skip_conditional_parallel_gateway = MagicMock()
    runtime.sleep = MagicMock()
    runtime.fork = MagicMock(return_value=[dispatch_process_1, dispatch_process_2])
    runtime.join = MagicMock()

    runtime.get_execution_data = MagicMock(return_value=execution_data)

    engine = Engine(runtime=runtime)
    engine.skip_conditional_parallel_gateway(node_id, flow_ids, converge_gateway_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.pre_skip_conditional_parallel_gateway.assert_called_once_with(node_id, flow_ids, converge_gateway_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.add_history.assert_called_once_with(
        node_id=node_id,
        started_time=state.started_time,
        archived_time=state.archived_time,
        loop=state.loop,
        skip=state.skip,
        retry=state.retry,
        version=state.version,
        inputs=execution_data.inputs,
        outputs=execution_data.outputs,
    )
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.FINISHED,
        is_skip=True,
        refresh_version=True,
        set_archive_time=True,
    )
    runtime.sleep.assert_called_once_with(process_id)
    runtime.join.assert_called_once_with(process_id, [dispatch_process_1.process_id, dispatch_process_2.process_id])
    runtime.execute.assert_has_calls(
        [
            call(
                process_id=dispatch_process_1.process_id,
                node_id=dispatch_process_1.node_id,
                root_pipeline_id=root_pipeline_id,
                parent_pipeline_id=top_pipeline_id,
            ),
            call(
                process_id=dispatch_process_2.process_id,
                node_id=dispatch_process_2.node_id,
                root_pipeline_id=root_pipeline_id,
                parent_pipeline_id=top_pipeline_id,
            ),
        ]
    )
    runtime.post_skip_conditional_parallel_gateway.assert_called_once_with(node_id, flow_ids, converge_gateway_id)


def test_skip_conditional_parallel_gateway__node_type_not_fit():
    node_id = "nid"
    flow_ids = ["flow_1", "flow_2"]
    converge_gateway_id = "converge_gateway_id"

    node = MagicMock()
    node.type = NodeType.ParallelGateway

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_conditional_parallel_gateway(node_id, flow_ids, converge_gateway_id)


def test_skip_conditional_parallel_gateway__node_is_not_failed():
    node_id = "nid"
    flow_ids = ["flow_1", "flow_2"]
    converge_gateway_id = "converge_gateway_id"

    node = MagicMock()
    node.type = NodeType.ConditionalParallelGateway
    node.can_skip = True
    node.targets = {"flow_1": "target_1", "flow_2": "target_2"}

    state = MagicMock()
    state.node_id = node_id
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)

    with pytest.raises(exceptions.InvalidOperationError):
        engine.skip_conditional_parallel_gateway(node_id, flow_ids, converge_gateway_id)

    runtime.get_state.assert_called_once_with(node_id)


def test_forced_fail_activity():
    node_id = "nid"
    ex_data = "ex_msg"
    process_id = "pid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity

    state = MagicMock()
    state.name = states.RUNNING
    state.version = "old_version"

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_process_id_with_current_node_id = MagicMock(return_value=process_id)
    runtime.get_execution_data_outputs = MagicMock(return_value={})
    runtime.set_state = MagicMock(return_value="new_version")

    engine = Engine(runtime=runtime)
    engine.forced_fail_activity(node_id, ex_data)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_process_id_with_current_node_id.assert_called_once_with(node_id)
    runtime.pre_forced_fail_activity.assert_called_once_with(node_id, ex_data)
    runtime.get_execution_data_outputs.assert_called_once_with(node_id)
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.FAILED,
        refresh_version=True,
        set_archive_time=True,
        send_post_set_state_signal=True,
    )
    runtime.set_execution_data_outputs.assert_called_once_with(node_id, {"ex_data": ex_data, "_forced_failed": True})
    runtime.kill.assert_called_once_with(process_id)
    runtime.post_forced_fail_activity.assert_called_once_with(node_id, ex_data, "old_version", "new_version")


def test_forced_fail_activity_not_send_post_set_state_signal():
    node_id = "nid"
    ex_data = "ex_msg"
    process_id = "pid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity

    state = MagicMock()
    state.name = states.RUNNING
    state.version = "old_version"

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_process_id_with_current_node_id = MagicMock(return_value=process_id)
    runtime.get_execution_data_outputs = MagicMock(return_value={})
    runtime.set_state = MagicMock(return_value="new_version")

    engine = Engine(runtime=runtime)
    engine.forced_fail_activity(node_id, ex_data, send_post_set_state_signal=False)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_process_id_with_current_node_id.assert_called_once_with(node_id)
    runtime.pre_forced_fail_activity.assert_called_once_with(node_id, ex_data)
    runtime.get_execution_data_outputs.assert_called_once_with(node_id)
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.FAILED,
        refresh_version=True,
        set_archive_time=True,
        send_post_set_state_signal=False,
    )
    runtime.set_execution_data_outputs.assert_called_once_with(node_id, {"ex_data": ex_data, "_forced_failed": True})
    runtime.kill.assert_called_once_with(process_id)
    runtime.post_forced_fail_activity.assert_called_once_with(node_id, ex_data, "old_version", "new_version")


def test_forced_fail_activity__node_type_not_fit():
    node_id = "nid"
    ex_data = "ex_msg"

    node = MagicMock()
    node.type = NodeType.SubProcess

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.forced_fail_activity(node_id, ex_data)


def test_forced_fail_activity__node_is_not_running():
    node_id = "nid"
    ex_data = "ex_msg"

    node = MagicMock()
    node.type = NodeType.ServiceActivity

    state = MagicMock()
    state.name = states.FINISHED

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_process_id_with_current_node_id = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.forced_fail_activity(node_id, ex_data)

    runtime.get_state.assert_called_once_with(node_id)


def test_forced_fail_activity__can_not_find_process_id():
    node_id = "nid"
    ex_data = "ex_msg"

    node = MagicMock()
    node.type = NodeType.ServiceActivity

    state = MagicMock()
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_process_id_with_current_node_id = MagicMock(return_value=None)
    runtime.pre_forced_fail_activity = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.forced_fail_activity(node_id, ex_data)

    runtime.get_state.get_process_id_with_current_node_id(node_id)


def test_callback():
    node_id = "nid"
    version = "v1"
    process_id = "pid"
    data = {"data": 1}
    data_id = 1

    state = MagicMock()
    state.version = version

    schedule = MagicMock()
    schedule.finished = False
    schedule.expired = False

    process_info = ProcessInfo(
        process_id=process_id, destination_id="did", parent_id=2, root_pipeline_id="p", pipeline_stack=["p"]
    )

    runtime = MagicMock()
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_schedule_with_node_and_version = MagicMock(return_value=schedule)
    runtime.set_callback_data = MagicMock(return_value=data_id)

    engine = Engine(runtime=runtime)
    engine.callback(node_id, version, data)

    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_schedule_with_node_and_version(node_id, version)
    runtime.pre_callback.assert_called_once_with(node_id, version, data)
    runtime.set_callback_data.assert_called_once_with(node_id, version, data)
    runtime.schedule.assert_called_once_with(process_id, node_id, schedule.id, data_id)
    runtime.post_callback.assert_called_once_with(node_id, version, data)


def test_callback__can_not_find_process_id():
    node_id = "nid"
    version = "v1"
    data = {"data": 1}

    runtime = MagicMock()
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=None)
    runtime.get_state = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.callback(node_id, version, data)


def test_callback__version_not_match():
    node_id = "nid"
    version = "v1"
    process_id = "pid"
    data = {"data": 1}

    state = MagicMock()
    state.version = "v2"

    schedule = MagicMock()
    schedule_id = 2

    runtime = MagicMock()
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_id)
    runtime.get_schedule_with_node_and_version = MagicMock(return_value=schedule)
    runtime.get_state = MagicMock(return_value=state)
    runtime.pre_callback = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.callback(node_id, version, data)

    runtime.expire_schedule.assert_called_once_with(schedule.id)


def test_callback__schedule_finished():
    node_id = "nid"
    version = "v1"
    process_id = "pid"
    data = {"data": 1}

    state = MagicMock()
    state.version = version

    schedule = MagicMock()
    schedule_id = 2
    schedule.finished = True
    schedule.expired = False

    runtime = MagicMock()
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_id)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_schedule_with_node_and_version = MagicMock(return_value=schedule)
    runtime.pre_callback = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.callback(node_id, version, data)

    runtime.get_schedule_with_node_and_version.assert_called_once_with(node_id, version)
    runtime.expire_schedule.assert_not_called()


def test_callback__schedule_expired():
    node_id = "nid"
    version = "v1"
    process_id = "pid"
    data = {"data": 1}

    state = MagicMock()
    state.version = version

    schedule = MagicMock()
    schedule_id = 2
    schedule.finished = False
    schedule.expired = True

    runtime = MagicMock()
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_id)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_schedule_with_node_and_version = MagicMock(return_value=schedule)
    runtime.pre_callback = MagicMock(side_effect=Exception)

    engine = Engine(runtime=runtime)
    with pytest.raises(exceptions.InvalidOperationError):
        engine.callback(node_id, version, data)

    runtime.get_schedule_with_node_and_version.assert_called_once_with(node_id, version)
    runtime.expire_schedule.assert_not_called()


def test_preview_node_inputs__plain_variable():
    node_id = "nid"
    pipeline = {"data": {}, "activities": {"nid": {"component": {"inputs": {"input": {"value": "test"}}}}}}
    runtime = MagicMock()

    api_result = preview_node_inputs(runtime, pipeline, node_id)
    assert api_result.result is True
    assert api_result.data == {"input": "test"}


class MockCV(Variable):
    def __init__(self, value):
        self.value = value

    def get(self):
        return "compute_result of {}".format(self.value)


def test_preview_node_inputs__ref_variable():
    node_id = "nid"
    pipeline = {
        "data": {
            "inputs": {
                "${test}": {"custom_type": "custom_type", "value": "test", "is_param": False, "type": "lazy"},
                "${input}": {"type": "splice", "is_param": False, "value": "${test} in input"},
            }
        },
        "activities": {
            "nid": {
                "component": {
                    "inputs": {
                        "input": {
                            "type": "splice",
                            "is_param": False,
                            "value": "${input}",
                        }
                    }
                }
            }
        },
    }

    compute_var = MockCV(pipeline["data"]["inputs"]["${test}"]["value"])
    runtime = MagicMock()
    runtime.get_compute_variable = MagicMock(return_value=compute_var)

    api_result = preview_node_inputs(runtime, pipeline, node_id)
    assert api_result.result is True
    assert api_result.data == {"input": "compute_result of test in input"}


def test_preview_node_inputs__with_subprocess():
    node_id = "nid"
    subprocess_id = "sid"
    subprocess_pipeline = {
        "data": {"inputs": {"${input}": {"value": "${test}", "type": "splice", "is_param": True}}},
        "activities": {
            "nid": {"component": {"inputs": {"input": {"value": "${input}", "type": "splice", "is_param": False}}}}
        },
    }
    pipeline = {
        "data": {
            "inputs": {
                "${test}": {
                    "value": "test_value",
                    "type": "plain",
                    "is_param": False,
                },
                "${input}": {"value": "parent_input", "type": "plain", "is_param": False},
            }
        },
        "activities": {
            "sid": {"pipeline": subprocess_pipeline, "params": {"${input}": {"type": "splice", "value": "${test}"}}}
        },
    }
    runtime = MagicMock()

    api_result = preview_node_inputs(runtime, pipeline, node_id, subprocess_stack=[subprocess_id])
    assert api_result.result is True
    assert api_result.data == {"input": "test_value"}


def test_retry_subprocess__type_not_match():
    node_id = "nid"

    node = MagicMock()
    node.type = NodeType.ServiceActivity

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)

    engine = Engine(runtime)

    try:
        engine.retry_subprocess(node_id)
    except exceptions.InvalidOperationError:
        pass
    else:
        assert False, "InvalidOperationError not raise"

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state.assert_not_called()


def test_retry_subprocess__state_is_not_fail():
    node_id = "nid"

    node = MagicMock()
    node.type = NodeType.SubProcess

    state = MagicMock()
    state.name = states.RUNNING

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)

    engine = Engine(runtime)

    try:
        engine.retry_subprocess(node_id)
    except exceptions.InvalidOperationError:
        pass
    else:
        assert False, "InvalidOperationError not raise"

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.pre_retry_subprocess.assert_not_called()


def test_retry_subprocess__success_and_need_reset_pipeline_stack():
    node_id = "nid"
    process_id = "process_id"

    node = MagicMock()
    node.type = NodeType.SubProcess

    state = MagicMock()
    state.name = states.FAILED
    state.node_id = node_id

    process_info = ProcessInfo(
        process_id=process_id, destination_id="did", parent_id=2, root_pipeline_id="p", pipeline_stack=["p", "nid"]
    )

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)
    runtime.get_process_info = MagicMock(return_value=process_info)

    engine = Engine(runtime)
    engine._add_history = MagicMock()

    engine.retry_subprocess(node_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.pre_retry_subprocess.assert_called_once_with(node_id)
    runtime.set_pipeline_stack.assert_called_once_with(process_id, process_info.pipeline_stack[:-1])
    engine._add_history.assert_called_once_with(node_id, state)
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.READY,
        is_retry=True,
        refresh_version=True,
        clear_started_time=True,
        clear_archived_time=True,
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id, node_id=node_id, root_pipeline_id="p", parent_pipeline_id="nid"
    )
    runtime.post_retry_subprocess.assert_called_once_with(node_id)


def test_retry_subprocess__success():
    node_id = "nid"
    process_id = "process_id"

    node = MagicMock()
    node.type = NodeType.SubProcess

    state = MagicMock()
    state.name = states.FAILED
    state.node_id = node_id

    process_info = ProcessInfo(
        process_id=process_id, destination_id="did", parent_id=2, root_pipeline_id="p", pipeline_stack=["p"]
    )

    runtime = MagicMock()
    runtime.get_node = MagicMock(return_value=node)
    runtime.get_state = MagicMock(return_value=state)
    runtime.get_sleep_process_info_with_current_node_id = MagicMock(return_value=process_info)

    engine = Engine(runtime)
    engine._add_history = MagicMock()

    engine.retry_subprocess(node_id)

    runtime.get_node.assert_called_once_with(node_id)
    runtime.get_state.assert_called_once_with(node_id)
    runtime.get_sleep_process_info_with_current_node_id.assert_called_once_with(node_id)
    runtime.pre_retry_subprocess.assert_called_once_with(node_id)
    runtime.set_pipeline_stack.assert_not_called()
    engine._add_history.assert_called_once_with(node_id, state)
    runtime.set_state.assert_called_once_with(
        node_id=node_id,
        to_state=states.READY,
        is_retry=True,
        refresh_version=True,
        clear_started_time=True,
        clear_archived_time=True,
    )
    runtime.execute.assert_called_once_with(
        process_id=process_id, node_id=node_id, root_pipeline_id="p", parent_pipeline_id="p"
    )
    runtime.post_retry_subprocess.assert_called_once_with(node_id)
