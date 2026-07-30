# -*- coding: utf-8 -*-
import abc

import six

_REGISTRY = {}


def register(event_type, handler):
    _REGISTRY[event_type] = handler


def get_handler(event_type):
    return _REGISTRY.get(event_type)


class EventHandler(six.with_metaclass(abc.ABCMeta, object)):
    @abc.abstractmethod
    def is_applicable(self, event):
        """事件是否适用于自动处理（缺任一契约方法的事件只能观察告警）。"""

    @abc.abstractmethod
    def apply(self, event):
        """通过正式引擎入口推动状态机（SHADOW 模式禁止调用）。"""

    @abc.abstractmethod
    def is_applied(self, event):
        """当前运行状态是否已证明预期动作已完成。"""

    @abc.abstractmethod
    def is_obsolete(self, event):
        """事件是否已对应旧版本/已结束节点，不应再执行。"""
