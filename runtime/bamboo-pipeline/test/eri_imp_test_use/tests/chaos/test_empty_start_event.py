# -*- coding: utf-8 -*-

from os import pipe
import pytest

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from eri_chaos.runtime import ChoasBambooDjangoRuntime

from ..utils import *  # noqa


@pytest.mark.parametrize(
    "execute_choas_plans",
    [
        pytest.param([{"get_data": {"raise_time": "pre"}}], id="get_data_raise"),
        pytest.param([{"get_context_key_references": {"raise_time": "pre"}}], id="get_context_key_references_raise"),
        pytest.param([{"get_context_values": {"raise_time": "pre"}}], id="get_context_values_raise"),
        pytest.param([{"upsert_plain_context_values": {"raise_time": "pre"}}], id="upsert_plain_context_values_raise"),
        pytest.param([{"set_state": {"raise_time": "pre", "raise_call_time": 2}}], id="pre_set_state_raise"),
        pytest.param([{"set_state": {"raise_time": "post", "raise_call_time": 2}}], id="post_set_state_raise"),
    ],
)
def test(execute_choas_plans):
    start = EmptyStartEvent()
    act = ServiceActivity(component_code="interrupt_test")
    end = EmptyEndEvent()

    start.extend(act).extend(end)

    pipeline_data = Data()
    pipeline_data.pre_render_keys = ["${a}", "${b}", "${c}"]
    pipeline_data.inputs["${a}"] = Var(type=Var.SPLICE, value="${b}_${c}")
    pipeline_data.inputs["${b}"] = Var(type=Var.PLAIN, value="1")
    pipeline_data.inputs["${c}"] = Var(type=Var.PLAIN, value="2")

    pipeline = build_tree(start, data=pipeline_data)

    engine = Engine(
        ChoasBambooDjangoRuntime(stage="start", execute_choas_plans=execute_choas_plans, schedule_choas_plans=[])
    )
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    assert_all_finish([start.id, act.id, end.id, pipeline["id"]])
    context = get_context_dict(pipeline["id"])
    assert context.get("${a}").value == "1_2"
    assert context.get("${b}").value == "1"
    assert context.get("${c}").value == "2"
