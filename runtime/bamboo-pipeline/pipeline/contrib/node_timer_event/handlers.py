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
from typing import Any, Dict, Tuple, Type

from pipeline.core.data.base import DataObject
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.eri import ExecutionData

logger = logging.getLogger(__name__)


def register_action(action_name: str):
    """注册 Action"""

    def register(cls):
        ActionFactory.add_action(action_name, cls)
        return cls

    return register


class BaseAction:
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


class ActionFactory:
    """
    节点处理器工厂
    """

    _actions: Dict[str, Type["BaseAction"]] = {}

    @classmethod
    def add_action(cls, action_name: str, action_cls: Type["BaseAction"]):
        """
        向工厂中注册 Action

        :param action_cls: Action 类
        :param action_name: Action 名称
        """
        if not issubclass(action_cls, BaseAction):
            raise TypeError("register action err: {} is not subclass of {}".format(action_cls, "BaseAction"))
        cls._actions[action_name] = action_cls

    @classmethod
    def get_action(cls, root_pipeline_id: str, node_id: str, version: str, action_name: str) -> BaseAction:
        """
        获取 Action 实例
        :param root_pipeline_id: 根节点 ID
        :param node_id: 节点 ID
        :param version: 节点版本
        :param action_name: Action 名称
        :return:
        """
        if action_name not in cls._actions:
            raise TypeError("{} not found".format(action_name))
        return cls._actions[action_name](root_pipeline_id, node_id, version)


@register_action("example")
class ExampleAction(BaseAction):
    def do(self, data: DataObject, parent_data: DataObject, *args, **kwargs) -> bool:
        logger.info("[Action] example do: data -> %s, parent_data -> %", data, parent_data)
        return True
