# -*- coding: utf-8 -*-
from unittest import TestCase

from pipeline.contrib.rollback.graph import RollbackGraphHandler


class TestGraph(TestCase):
    def test_build_rollback_graph_with_cycle(self):
        node_map = {
            "start": {
                "id": "start",
                "type": "EmptyStartEvent",
                "targets": {"lf67ec0280323668ba383bc61c92bdce": "node_1"},
            },
            "node_1": {
                "id": "node_1",
                "type": "ServiceActivity",
                "targets": {"l5c6729c70b83c81bd98eebefe0c46e3": "node_2"},
            },
            "node_2": {
                "id": "node_2",
                "type": "ServiceActivity",
                "targets": {"ld09dcdaaae53cd9868b652fd4b7b074": "node_3"},
            },
            "node_3": {
                "id": "node_3",
                "type": "ExclusiveGateway",
                "targets": {"ld9beef12dd33812bb9b697afd5f2728": "node_4", "lffeab3bdb0139b69ac6978a415e3f54": "node_1"},
            },
            "node_4": {
                "id": "node_4",
                "type": "ServiceActivity",
                "targets": {"l995fa16e367312e99a1f8b54458ed6a": "node_5"},
            },
            "node_5": {
                "id": "node_5",
                "type": "ServiceActivity",
                "targets": {"l802b3f8e60e39518915f85d4c943a18": "node_6"},
            },
            "node_6": {
                "id": "node_6",
                "type": "ExclusiveGateway",
                "targets": {"l8ff0721ec8c3745b6f2183a7006d2c6": "node_7", "l5df5ee5497f3616aec4347c0e5913b8": "node_5"},
            },
            "node_7": {"id": "node_7", "type": "EmptyEndEvent", "targets": {}},
        }

        rollback_graph = RollbackGraphHandler(node_map=node_map, start_id="node_5", target_id="node_1")
        graph, other_nodes = rollback_graph.build_rollback_graph()
        self.assertListEqual(other_nodes, ["node_3"])
        self.assertListEqual(graph.as_dict()["nodes"], ["node_5", "node_1", "END", "START", "node_2", "node_4"])
        self.assertListEqual(
            graph.as_dict()["flows"],
            [["node_1", "END"], ["START", "node_5"], ["node_2", "node_1"], ["node_4", "node_2"], ["node_5", "node_4"]],
        )
        self.assertListEqual(list(graph.next("START")), ["node_5"])
