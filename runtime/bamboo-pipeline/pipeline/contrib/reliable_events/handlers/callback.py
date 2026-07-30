# -*- coding: utf-8 -*-
from bamboo_engine.eri import ScheduleType

from pipeline.contrib.reliable_events.constants import EventType
from pipeline.contrib.reliable_events.handlers.base import EventHandler, register
from pipeline.eri.models import Schedule, State
from pipeline.eri.runtime import BambooDjangoRuntime


class NoScheduleError(Exception):
    """ACTIVE 重放时找不到对应 Schedule。"""


class NotEligibleError(Exception):
    """事件对应的 schedule 非单-CALLBACK 类型,ACTIVE 不应重放。"""


class CallbackHandler(EventHandler):
    def is_applicable(self, event):
        return True

    def apply(self, event):
        # 幂等重投:复用生产 Celery→Engine.schedule 路径重放已存 CallbackData,不新建回调数据、不改核心。
        schedule = Schedule.objects.filter(node_id=event.node_id, version=event.version).first()
        if schedule is None:
            raise NoScheduleError("no schedule for node={} version={}".format(event.node_id, event.version))
        if schedule.type != ScheduleType.CALLBACK.value:
            raise NotEligibleError(
                "schedule type {} is not single CALLBACK for node={}".format(schedule.type, event.node_id)
            )
        BambooDjangoRuntime().schedule(
            process_id=schedule.process_id,
            node_id=event.node_id,
            schedule_id=str(schedule.id),
            callback_data_id=int(event.source_id),
        )

    def is_obsolete(self, event):
        state = State.objects.filter(node_id=event.node_id).first()
        if state is None:
            return True
        return state.version != event.version

    def is_applied(self, event):
        schedule = Schedule.objects.filter(node_id=event.node_id, version=event.version).first()
        if schedule is None:
            return False
        return bool(schedule.finished)


register(EventType.NODE_CALLBACK, CallbackHandler())
