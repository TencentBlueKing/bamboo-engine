# -*- coding: utf-8 -*-

from django.test import TestCase
from pipeline.parser.utils import recursive_replace_id, replace_all_id

from bamboo_engine.builder import (
    ConvergeGateway,
    Data,
    EmptyEndEvent,
    EmptyStartEvent,
    ExclusiveGateway,
    ParallelGateway,
    ServiceActivity,
    SubProcess,
    Var,
    build_tree,
    builder,
)


class ReplaceTests(TestCase):
    def test_replace_all_id(self):
        start = EmptyStartEvent()
        act = ServiceActivity(component_code="example_component")
        end = EmptyEndEvent()
        start.extend(act).extend(end)
        pipeline = builder.build_tree(start)
        node_map = replace_all_id(pipeline)
        self.assertIsInstance(node_map, dict)
        self.assertIn(pipeline["start_event"]["id"], node_map["start_event"][start.id])
        self.assertIn(pipeline["end_event"]["id"], node_map["end_event"][end.id])
        self.assertEqual(list(pipeline["activities"].keys())[0], node_map["activities"][act.id])

    def test_replace_all_id_gateway(self):
        start = EmptyStartEvent()
        pg = ParallelGateway()
        act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
        act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
        act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
        cg = ConvergeGateway()
        end = EmptyEndEvent()

        start.extend(pg).connect(act_1, act_2, act_3).to(pg).converge(cg).extend(end)
        pipeline = build_tree(start)
        node_map = replace_all_id(pipeline)

        self.assertIn(pg.id, node_map["gateways"].keys())
        self.assertIn(cg.id, node_map["gateways"].keys())

        self.assertIn(node_map["gateways"][pg.id], pipeline["gateways"].keys())
        self.assertIn(node_map["gateways"][cg.id], pipeline["gateways"].keys())

    def test_recursive_replace_id(self):
        start = EmptyStartEvent()
        pg = ParallelGateway()
        act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
        act_2 = ServiceActivity(component_code="pipe_example_component", name="act_2")
        act_3 = ServiceActivity(component_code="pipe_example_component", name="act_3")
        cg = ConvergeGateway()
        end = EmptyEndEvent()
        start.extend(pg).connect(act_1, act_2, act_3).to(pg).converge(cg).extend(end)
        pipeline = build_tree(start)
        node_map = recursive_replace_id(pipeline)
        self.assertIn(pg.id, node_map[pipeline["id"]]["gateways"].keys())
        self.assertIn(cg.id, node_map[pipeline["id"]]["gateways"].keys())
        self.assertIn(node_map[pipeline["id"]]["gateways"][pg.id], pipeline["gateways"].keys())
        self.assertIn(node_map[pipeline["id"]]["gateways"][cg.id], pipeline["gateways"].keys())
        self.assertIn(act_1.id, node_map[pipeline["id"]]["activities"].keys())

    def test_recursive_replace_id_with_subprocess(self):
        def sub_process(data):
            subproc_start = EmptyStartEvent()
            subproc_act = ServiceActivity(component_code="pipe_example_component", name="sub_act")
            subproc_end = EmptyEndEvent()

            subproc_start.extend(subproc_act).extend(subproc_end)

            subproc_act.component.inputs.sub_input = Var(type=Var.SPLICE, value="${sub_input}")

            return SubProcess(start=subproc_start, data=data)

        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="pipe_example_component", name="act_1")
        eg = ExclusiveGateway(conditions={0: "${act_1_output} < 0", 1: "${act_1_output} >= 0"}, name="act_2 or act_3")

        sub_pipeline_data_1 = Data(inputs={"${sub_input}": Var(type=Var.PLAIN, value=1)})
        subproc_1 = sub_process(sub_pipeline_data_1)

        sub_pipeline_data_2 = Data(inputs={"${sub_input}": Var(type=Var.PLAIN, value=2)})
        subproc_2 = sub_process(sub_pipeline_data_2)
        end = EmptyEndEvent()

        start.extend(act_1).extend(eg).connect(subproc_1, subproc_2).converge(end)

        pipeline = build_tree(start)
        node_map = recursive_replace_id(pipeline)

        self.assertEqual(len(node_map[pipeline["id"]]["subprocess"].keys()), 2)
        self.assertIn(
            node_map[pipeline["id"]]["activities"][subproc_1.id], node_map[pipeline["id"]]["subprocess"].keys()
        )
        self.assertIn(
            node_map[pipeline["id"]]["activities"][subproc_2.id], node_map[pipeline["id"]]["subprocess"].keys()
        )
