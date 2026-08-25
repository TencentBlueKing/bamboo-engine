# -*- coding: utf-8 -*-

from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.builder import *  # noqa
from bamboo_engine.engine import Engine

from ..utils import *  # noqa


def test_subcanvas_share_main_canvas_context():
    """
    验证子画布内部节点可以直接引用主画布（父流程）上下文变量，
    而无需像子流程那样通过 params 注入入参。
    """
    # 主画布上下文变量
    main_data = Data()
    main_data.inputs["${name}"] = Var(type=Var.PLAIN, value="bamboo")
    main_data.inputs["${greeting}"] = Var(type=Var.SPLICE, value="hello ${name}")

    # 子画布内部：一个活动直接引用主画布的 ${greeting}
    start_sub = EmptyStartEvent()
    act_sub = ServiceActivity(component_code="debug_node")
    act_sub.component.inputs.input_a = Var(type=Var.SPLICE, value="${greeting}")
    end_sub = EmptyEndEvent()
    start_sub.extend(act_sub).extend(end_sub)

    # 主画布：start -> subcanvas -> end
    start = EmptyStartEvent()
    sub_canvas = SubCanvas(start=start_sub)
    end = EmptyEndEvent()
    start.extend(sub_canvas).extend(end)

    pipeline = build_tree(start, data=main_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([pipeline["id"]])

    state = runtime.get_state(sub_canvas.id)
    assert state.name == states.FINISHED

    assert_exec_data_equal(
        {
            act_sub.id: {
                "inputs": {"_loop": 1, "_inner_loop": 1, "input_a": "hello bamboo"},
                "outputs": {"_loop": 1, "_inner_loop": 1, "input_a": "hello bamboo", "_result": True},
            },
        }
    )


def test_subcanvas_loop_driven_by_inner_loop():
    """
    验证子画布可以像子流程一样被父流程网关用其 _loop 计数器驱动循环。

    循环机制：父流程网关 ${s_i} < 4 时回到子画布，子画布的 _loop 自动递增并被
    父流程 ${s_i}（经 NodeOutput 取自子画布 _loop）读取，达到 4 时退出到 end。
    """
    # 子画布内部：起止事件即可，_loop 由引擎自动维护
    start_sub = EmptyStartEvent()
    act_sub = ServiceActivity(component_code="debug_node")
    end_sub = EmptyEndEvent()
    start_sub.extend(act_sub).extend(end_sub)

    # 主画布：start -> act_1 -> subcanvas -> eg ->(回边/退出)
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="debug_node")
    sub_canvas = SubCanvas(start=start_sub)
    eg = ExclusiveGateway(conditions={0: "${s_i} < 4", 1: "${s_i} >= 4"})
    end = EmptyEndEvent()

    start.extend(act_1).extend(sub_canvas).extend(eg).connect(sub_canvas, end)

    # 父流程数据：${s_i} 取自子画布的 _loop 输出
    main_data = Data()
    main_data.inputs["${s_i}"] = NodeOutput(type=Var.SPLICE, source_act=sub_canvas.id, source_key="_loop", value="")

    pipeline = build_tree(start, data=main_data)
    runtime = BambooDjangoRuntime()
    engine = Engine(runtime)
    engine.run_pipeline(pipeline=pipeline, root_pipeline_data={}, cycle_tolerate=True)

    assert_all_finish([pipeline["id"]])

    # 子画布被循环执行 4 次
    state = runtime.get_state(sub_canvas.id)
    assert state.name == states.FINISHED
    assert state.loop == 4

    # 子画布内 start 事件也应随循环执行 4 次
    state = runtime.get_state(start_sub.id)
    assert state.name == states.FINISHED
    assert state.loop == 4
