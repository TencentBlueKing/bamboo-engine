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
import logging
from abc import abstractmethod
from typing import Any, Dict, Tuple

from pipeline.core.data.base import DataObject
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine import api as bamboo_engine_api
from bamboo_engine.eri import ExecutionData

logger = logging.getLogger(__name__)


class ActionManager:
    __hub = {}

    @classmethod
    def register_invocation_cls(cls, invocation_cls):
        action_name = invocation_cls.Meta.action_name
        existed_invocation_cls = cls.__hub.get(action_name)
        if existed_invocation_cls:
            raise RuntimeError(
                "func register error, {}'s action_name {} conflict with {}".format(
                    existed_invocation_cls, action_name, invocation_cls
                )
            )

        cls.__hub[action_name] = invocation_cls

    @classmethod
    def clear(cls):
        cls.__hub = {}

    @classmethod
    def get_action(cls, root_pipeline_id: str, node_id: str, version: str, action_name: str) -> "BaseAction":
        """
        获取 Action 实例
        :param root_pipeline_id: 根节点 ID
        :param node_id: 节点 ID
        :param version: 节点版本
        :param action_name: Action 名称
        :return:
        """
        if action_name not in cls.__hub:
            raise ValueError("{} not found".format(action_name))
        return cls.__hub[action_name](root_pipeline_id, node_id, version)


class ActionMeta(type):
    """
    Metaclass for FEEL function invocation
    """

    def __new__(cls, name, bases, dct):
        # ensure initialization is only performed for subclasses of Plugin
        parents = [b for b in bases if isinstance(b, ActionMeta)]
        if not parents:
            return super().__new__(cls, name, bases, dct)

        new_cls = super().__new__(cls, name, bases, dct)

        # meta validation
        meta_obj = getattr(new_cls, "Meta", None)
        if not meta_obj:
            raise AttributeError("Meta class is required")

        action_name = getattr(meta_obj, "action_name", None)
        if not action_name:
            raise AttributeError("action_name is required in Meta")

        # register func
        ActionManager.register_invocation_cls(new_cls)

        return new_cls


class BaseAction(metaclass=ActionMeta):
    def __init__(self, root_pipeline_id: str, node_id: str, version: str):
        self.root_pipeline_id = root_pipeline_id
        self.node_id = node_id
        self.version = version

    @classmethod
    def get_execution_data(cls, root_pipeline_id: str, node_id: str) -> Tuple[DataObject, DataObject]:
        runtime: BambooDjangoRuntime = BambooDjangoRuntime()
        data: ExecutionData = runtime.get_execution_data(node_id)
        root_pipeline_inputs: Dict[str, Any] = {
            key: di.value for key, di in runtime.get_data_inputs(root_pipeline_id).items()
        }
        root_pipeline_data: ExecutionData = ExecutionData(inputs=root_pipeline_inputs, outputs={})

        data_obj: DataObject = DataObject(inputs=data.inputs, outputs=data.outputs)
        parent_data_obj: DataObject = DataObject(inputs=root_pipeline_data.inputs, outputs=root_pipeline_data.outputs)
        return data_obj, parent_data_obj

    def notify(self, *args, **kwargs) -> bool:
        data, parent_data = self.get_execution_data(self.root_pipeline_id, self.node_id)
        return self.do(data, parent_data, *args, **kwargs)

    @abstractmethod
    def do(self, data: DataObject, parent_data: DataObject, *args, **kwargs) -> bool:
        raise NotImplementedError


class ExampleAction(BaseAction):
    def do(self, data: DataObject, parent_data: DataObject, *args, **kwargs) -> bool:
        logger.info("[Action] example do: data -> %s, parent_data -> %s", data, parent_data)
        return True

    class Meta:
        action_name = "example"


class ForcedFailAction(BaseAction):

    TIMEOUT_NODE_OPERATOR = "bamboo_engine"

    def do(self, data: DataObject, parent_data: DataObject, *args, **kwargs) -> bool:
        logger.info("[Action(bamboo_engine_forced_fail)] do: data -> %s, parent_data -> %s", data, parent_data)
        result = bamboo_engine_api.forced_fail_activity(
            runtime=BambooDjangoRuntime(),
            node_id=self.node_id,
            ex_data="forced fail by {}".format(self.TIMEOUT_NODE_OPERATOR),
            send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
        )
        return result.result

    class Meta:
        action_name = "bamboo_engine_forced_fail"


class ForcedFailAndSkipAction(BaseAction):

    TIMEOUT_NODE_OPERATOR = "bamboo_engine"

    def do(self, data: DataObject, parent_data: DataObject, *args, **kwargs) -> bool:
        logger.info("[Action(bamboo_engine_forced_fail_and_skip)] do: data -> %s, parent_data -> %s", data, parent_data)
        result = bamboo_engine_api.forced_fail_activity(
            runtime=BambooDjangoRuntime(),
            node_id=self.node_id,
            ex_data="forced fail by {}".format(self.TIMEOUT_NODE_OPERATOR),
            send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
        )
        if result.result:
            result = bamboo_engine_api.skip_node(
                runtime=BambooDjangoRuntime(),
                node_id=self.node_id,
                ex_data="forced skip by {}".format(self.TIMEOUT_NODE_OPERATOR),
                send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
            )
        return result.result

    class Meta:
        action_name = "bamboo_engine_forced_fail_and_skip"
