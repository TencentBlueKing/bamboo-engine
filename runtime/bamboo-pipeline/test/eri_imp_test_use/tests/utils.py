# -*- coding: utf-8 -*-

from time import sleep  # noqa

from bamboo_engine import states
from bamboo_engine.eri import ContextValueType  # noqa

from pipeline.eri.runtime import BambooDjangoRuntime
from pipeline.eri.models import Schedule as DBSchedule
from pipeline.eri.models import State as DBState

runtime = BambooDjangoRuntime()


def _assert_all_state_equal(node_id_list, name):
    for _ in range(20):
        state_names = runtime.batch_get_state_name(node_id_list)
        if len(state_names) == len(node_id_list) and set(state_names.values()) == {name}:
            break
        sleep(0.5)

    assert len(state_names) == len(node_id_list), "actual: %s" % len(state_names)
    assert set(state_names.values()) == {name}, "actual: %s" % state_names


def assert_all_finish(node_id_list):
    _assert_all_state_equal(node_id_list, states.FINISHED)


def assert_all_failed(node_id_list):
    _assert_all_state_equal(node_id_list, states.FAILED)


def assert_all_running(node_id_list):
    _assert_all_state_equal(node_id_list, states.RUNNING)


def assert_all_revoked(node_id_list):
    _assert_all_state_equal(node_id_list, states.REVOKED)

def assert_all_suspended(node_id_list):
    _assert_all_state_equal(node_id_list, states.SUSPENDED)

def assert_not_executed(node_id_list):
    qs = DBState.objects.filter(node_id__in=node_id_list)
    assert len(qs) == 0


def assert_exec_data_equal(node_data_dict):
    for node_id in node_data_dict.keys():
        data = runtime.get_execution_data(node_id)
        inputs = node_data_dict[node_id]["inputs"]
        outputs = node_data_dict[node_id]["outputs"]
        assert data.inputs == inputs, "actual: %s, expect: %s" % (data.inputs, inputs)
        assert data.outputs == outputs, "actual: %s, expect: %s" % (data.outputs, outputs)


def _assert_schedule_finish(node_id, finished, scheduling, expired, times=None, version=None):
    get_kwargs = {"node_id": node_id}
    if version:
        get_kwargs["version"] = version
    schedule = DBSchedule.objects.get(**get_kwargs)
    assert schedule.finished is finished
    assert schedule.scheduling is scheduling
    assert schedule.expired is expired
    if times is not None:
        assert schedule.schedule_times == times, "actual: %s" % schedule.schedule_times


def assert_schedule_finish(node_id, times=None, version=None):
    _assert_schedule_finish(
        node_id=node_id, finished=True, scheduling=False, expired=False, times=times, version=version
    )


def assert_schedule_not_finish(node_id, times=None, scheduling=False, expired=False, version=None):
    _assert_schedule_finish(
        node_id=node_id, finished=False, scheduling=scheduling, expired=expired, times=times, version=version
    )


def get_context_dict(pipeline_id):
    return {cv.key: cv for cv in runtime.get_context(pipeline_id)}
