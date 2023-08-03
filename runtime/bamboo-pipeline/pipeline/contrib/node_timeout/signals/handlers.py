# -*- coding: utf-8 -*-
import datetime
import logging

from django.dispatch import receiver

from bamboo_engine import states as bamboo_engine_states
from pipeline.contrib.node_timeout.models import TimeoutNodeConfig
from pipeline.contrib.node_timeout.settings import node_timeout_settings
from pipeline.eri.signals import post_set_state


logger = logging.getLogger(__name__)


def _node_timeout_info_update(redis_inst, to_state, node_id, version):
    key = f"{node_id}_{version}"
    if to_state == bamboo_engine_states.RUNNING:
        now = datetime.datetime.now()
        timeout_qs = TimeoutNodeConfig.objects.filter(node_id=node_id).only("timeout")
        if not timeout_qs:
            return
        timeout_time = (now + datetime.timedelta(seconds=timeout_qs[0].timeout)).timestamp()
        redis_inst.zadd(node_timeout_settings.executing_pool, mapping={key: timeout_time}, nx=True)
    elif to_state in [bamboo_engine_states.FAILED, bamboo_engine_states.FINISHED, bamboo_engine_states.SUSPENDED]:
        redis_inst.zrem(node_timeout_settings.executing_pool, key)


@receiver(post_set_state)
def bamboo_engine_eri_node_state_handler(sender, node_id, to_state, version, root_id, parent_id, loop, **kwargs):
    try:
        _node_timeout_info_update(node_timeout_settings.redis_inst, to_state, node_id, version)
    except Exception:
        logger.exception("node_timeout_info_update error")