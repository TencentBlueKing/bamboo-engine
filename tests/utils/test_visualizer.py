import pytest

from bamboo_engine.builder import (
    ConditionalParallelGateway,
    ConvergeGateway,
    Data,
    DataInput,
    EmptyEndEvent,
    EmptyStartEvent,
    ExclusiveGateway,
    NodeOutput,
    Params,
    ServiceActivity,
    SubProcess,
    Var,
    build_tree,
)
from bamboo_engine.utils.visualizer import BambooVisualizer


class TestBambooVisualizer:
    @pytest.fixture
    def sub_pipeline_start(self):
        """子流程"""

        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1", id="sub_act_1")
        cpg = ConditionalParallelGateway(conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0"}, name="cpg")
        act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
        act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
        cg = ConvergeGateway(name="cg")
        end = EmptyEndEvent()

        start.extend(act_1).extend(cpg).connect(act_2, act_3).to(cpg).converge(cg).extend(end)

        act_1.component.inputs.input_a = Var(type=Var.LAZY, value="${input_a}", custom_type="example")

        return start

    @pytest.fixture
    def pipeline_tree(self, sub_pipeline_start):
        """主流程"""

        sub_pipeline_data = Data()
        sub_pipeline_data.inputs["${input_a}"] = DataInput(type=Var.PLAIN, value="default_value")
        sub_pipeline_data.inputs["${act_1_output}"] = NodeOutput(
            type=Var.SPLICE, source_act="sub_act_1", source_key="input_a"
        )

        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="debug_node", name="act_1")
        act_1.component.inputs.param_1 = Var(type=Var.PLAIN, value="output_value_1")
        gateway = ExclusiveGateway(
            conditions={0: "${act_1_output} is None", 1: "${act_1_output} is not None"}, name="eg"
        )
        act_2 = ServiceActivity(component_code="debug_node", name="act_2")
        act_2.component.inputs.param_2 = Var(type=Var.SPLICE, value="${act_1_output}")
        end = EmptyEndEvent()

        params = Params({"${input_a}": Var(type=Var.SPLICE, value="${lazy_value}")})
        subprocess = SubProcess(start=sub_pipeline_start, name="sub", data=sub_pipeline_data, params=params)

        pipeline_data = Data()
        pipeline_data.inputs["${value}"] = Var(type=Var.PLAIN, value="1")
        pipeline_data.inputs["${lazy_value}"] = Var(type=Var.LAZY, value="${value}", custom_type="to_int")
        pipeline_data.inputs["${act_1_output}"] = NodeOutput(source_act=act_1.id, source_key="param_1", type=Var.SPLICE)

        start.extend(act_1).extend(subprocess).extend(gateway).connect(end, act_2).to(act_2).extend(end)
        pipeline_tree = build_tree(start, data=pipeline_data)

        return pipeline_tree

    def test_render(self, pipeline_tree):
        """测试渲染"""

        visualizer = BambooVisualizer(pipeline_tree)
        visualizer.render()

    def test_render_json(self, pipeline_tree):
        """测试渲染 JSON"""

        visualizer = BambooVisualizer(pipeline_tree)
        visualizer.render_json()
