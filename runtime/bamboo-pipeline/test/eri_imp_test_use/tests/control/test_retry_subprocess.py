# -*- coding: utf-8 -*-

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine
from pipeline.eri.runtime import BambooDjangoRuntime

from ..utils import *  # noqa


def test_retry_subprocess():
    subproc_start = EmptyStartEvent()
    subproc_act = ServiceActivity(component_code="debug_node")
    subproc_end = EmptyEndEvent()

    subproc_start.extend(subproc_act).extend(subproc_end)

    params = Params({"${raise_var}": Var(type=Var.LAZY, custom_type="raise_variable", value="")})

    start = EmptyStartEvent()
    subproc = SubProcess(start=subproc_start, params=params)
    end = EmptyEndEvent()

    start.extend(subproc).extend(end)

    pipeline = build_tree(start)
    engine = Engine(BambooDjangoRuntime())
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={})

    sleep(2)

    old_state = runtime.get_state(subproc.id)
    assert old_state.name == states.FAILED

    engine.retry_subprocess(subproc.id)

    sleep(2)

    state = runtime.get_state(subproc.id)
    assert state.name == states.FAILED
    assert state.version != old_state.version

    histories = runtime.get_histories(subproc.id)
    assert len(histories) == 1
    assert histories[0].node_id == subproc.id
    assert histories[0].loop == 1
    assert histories[0].retry == 0
    assert histories[0].skip is False
    assert histories[0].started_time is not None
    assert histories[0].archived_time is not None
    assert histories[0].inputs == {}
    assert len(histories[0].outputs) == 1
    assert "ex_data" in histories[0].outputs
    assert histories[0].version == old_state.version
