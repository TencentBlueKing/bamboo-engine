# -*- coding: utf-8 -*-

from bamboo_engine.validator import api
from pipeline.core.flow import FlowNodeClsFactory

from .end_events import MyTestEndEvent, MyRaiseEndEvent

FlowNodeClsFactory.register_node(MyTestEndEvent.__name__, MyTestEndEvent)
FlowNodeClsFactory.register_node(MyRaiseEndEvent.__name__, MyRaiseEndEvent)
api.add_sink_type(MyTestEndEvent.__name__)
api.add_sink_type(MyRaiseEndEvent.__name__)
