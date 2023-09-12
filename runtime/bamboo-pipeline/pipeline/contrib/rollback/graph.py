# -*- coding: utf-8 -*-
import copy

from pipeline.contrib.rollback import constants
from pipeline.core.constants import PE

from bamboo_engine.utils.graph import Graph


class CycleHandler:
    """
    环处理器，作用是去除拓扑中的环
    """

    def __init__(self, node_map):
        self.node_map = copy.deepcopy(node_map)

    def get_nodes_and_edges(self):
        """
        从node_map 中解析出环和边
        """
        nodes = []
        edges = []
        for node, value in self.node_map.items():
            nodes.append(node)
            targets = value["targets"]
            for target in targets.values():
                # 过滤掉那些没有执行的分支
                if target not in self.node_map:
                    continue
                edges.append([node, target])
        return nodes, edges

    def has_cycle(self, nodes, edges) -> list:
        """
        判断是否有环，存在环是，将返回一个有效的list
        """
        graph = Graph(nodes, edges)
        return graph.get_cycle()

    def delete_edge(self, source, target):
        """
        删除环边
        """
        targets = self.node_map[source]["targets"]

        keys_to_remove = []
        for key, val in targets.items():
            if val == target:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del targets[key]

    def remove_cycle(self):
        while True:
            nodes, edges = self.get_nodes_and_edges()
            cycles = self.has_cycle(nodes, edges)
            if not cycles:
                break
            source = cycles[-2]
            target = cycles[-1]
            self.delete_edge(source, target)
        return self.node_map


class RollbackGraphHandler:
    def __init__(self, node_map, start_id, target_id):
        self.graph = Graph()
        # 回滚开始的节点
        self.start_id = start_id
        # 回滚结束的节点
        self.target_id = target_id
        self.graph.add_node(start_id)
        self.graph.add_node(target_id)
        # 去除自环边
        self.node_map = CycleHandler(node_map).remove_cycle()
        # 其他不参与回滚，但是需要被清理的节点，主要是网关节点和子流程节点
        self.others_nodes = []

    def build(self, node_id, source_id=None):
        node_detail = self.node_map.get(node_id)
        if node_detail is None:
            return
        node_type = node_detail["type"]

        if node_type in [PE.ExclusiveGateway, PE.ParallelGateway, PE.ConditionalParallelGateway, PE.ConvergeGateway]:
            self.others_nodes.append(node_id)

        if node_type == PE.ServiceActivity:
            next_node_id = node_detail.get("id")
            self.graph.add_node(next_node_id)
            if source_id and source_id != next_node_id:
                self.graph.add_edge(source_id, next_node_id)

            # 如果遍历到目标节点，则返回
            if node_id == self.start_id:
                return

            source_id = next_node_id
            targets = node_detail.get("targets", {}).values()
        elif node_type == PE.ExclusiveGateway:
            targets = [target for target in node_detail.get("targets", {}).values() if target in self.node_map.keys()]
        else:
            targets = node_detail.get("targets", {}).values()

        for target in targets:
            self.build(target, source_id)

    def build_rollback_graph(self):
        """
        这里将会从结束的节点往开始的节点进行遍历，之后再反转图
        """
        self.graph.add_node(constants.END_FLAG)
        # 未整个流程加上结束节点
        self.graph.add_edge(constants.END_FLAG, self.target_id)
        self.graph.add_node(constants.START_FLAG)
        self.graph.add_edge(self.start_id, constants.START_FLAG)
        self.build(self.target_id, self.target_id)

        return self.graph.reverse(), self.others_nodes
