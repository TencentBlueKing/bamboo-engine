# -*- coding: utf-8 -*-
import time

from pipeline.contrib.plugin_execute import api


def test_run_plugin_no_schedule():
    # 测试execute的情况
    task_id = api.run("debug_no_schedule_node", "legacy", {}, {}).data
    state = api.get_state(task_id).data
    assert state["state"] == "READY"
    time.sleep(2)
    state = api.get_state(task_id).data
    assert state["state"] == "FINISHED"


def test_run_plugin_with_schedule():
    # 测试schedule的情况
    task_id = api.run("schedule_node", "legacy", {"count": 1}, {}).data
    state = api.get_state(task_id).data
    assert state["state"] == "READY"
    time.sleep(30)
    state = api.get_state(task_id).data
    assert state["state"] == "FINISHED"
    assert state["outputs"]["count"] == 5


def test_run_plugin_with_callback():
    # 测试callback的情况
    task_id = api.run("hook_callback_node", "legacy", {}, {}).data
    state = api.get_state(task_id).data
    assert state["state"] == "READY"
    time.sleep(5)
    state = api.get_state(task_id).data
    assert state["state"] == "RUNNING"

    api.callback(task_id, {"bit": 0})
    time.sleep(10)

    state = api.get_state(task_id).data
    assert state["state"] == "FAILED"

    api.retry(task_id, inputs={})
    time.sleep(5)
    state = api.get_state(task_id).data
    assert state["state"] == "RUNNING"

    api.callback(task_id, {"bit": 1})
    time.sleep(5)
    state = api.get_state(task_id).data
    assert state["state"] == "RUNNING"


def test_run_plugin_with_callback_success():
    task_id = api.run("debug_callback_node", "legacy", {}, {}).data
    state = api.get_state(task_id).data

    assert state["state"] == "READY"
    time.sleep(5)
    state = api.get_state(task_id).data
    assert state["state"] == "RUNNING"

    api.callback(task_id, {"bit": 1})
    time.sleep(10)

    state = api.get_state(task_id).data
    assert state["state"] == "FINISHED"


def test_run_plugin_with_force_fail():
    task_id = api.run("debug_callback_node", "legacy", {}, {}).data
    state = api.get_state(task_id).data

    assert state["state"] == "READY"
    time.sleep(5)
    state = api.get_state(task_id).data
    assert state["state"] == "RUNNING"

    api.forced_fail(task_id)
    time.sleep(3)

    state = api.get_state(task_id).data
    assert state["state"] == "FAILED"
