"""
Render bamboo pipeline into mermaid flowchart diagram
Usage:
>> visualizer = Visualizer(pipeline_tree=my_pipeline, pipeline_data=my_pipeline_data_or_none)
>> print(visualizer.render())
"""

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import md5
from typing import Any, Dict, List, Optional, Tuple

LINK_NORMAL = ("---", '--"{}"--')
LINK_NORMAL_ARROW = ("-->", '--"{}"-->')
LINK_THICK = ("===", '=="{}"==')
LINK_THICK_ARROW = ("==>", '=="{}"==>')
LINK_DOTTED = ("-.-", '-."{}".-')
LINK_DOTTED_ARROW = ("-.->", '-."{}".->')

NODE_NORMAL = '["{}"]'
NODE_ROUND_EDGE = '("{}")'
NODE_STADIUM_SHAPE = '(["{}]")'
NODE_SUBROUTINE_SHAPE = '[["{}"]]'
NODE_ASYMMENTRIC_SHAPE = '>"{}"]'
NODE_HEXAGON = '{{{{"{}"}}}}'


@dataclass
class BambooPipelineData:
    key: str
    ref_id: str
    variable_data: Dict[str, Any]


visualizer_classes_styles: Dict[str, str] = {
    "Normal": "stroke:#9370db,fill:#ffffff",
    "Context": "stroke:#ffffff,fill:#efefef",
    "Flow": "stroke:#000000,fill:#ffffff",
    "SubProcess": "stroke:#000000,fill:#fefefe",
    "StartEvent": "stroke:#000000,fill:#ffffff",
    "EndEvent": "stroke:#000000,fill:#e0e0e0",
    "ServiceActivity": "stroke:#9370db,fill:#ecfcff",
    "ExclusiveGateway": "stroke:#9370db,fill:#8fd6f5",
    "ConvergeGateway": "stroke:#9370db,fill:#bbe4bd",
    "ParallelGateway": "stroke:#9370db,fill:#f5e08f",
    "ConditionalParallelGateway": "stroke:#9370db,fill:#f3d4bb",
    "PlainVar": "stroke:#000000,fill:#edf4e6",
    "SpliceVar": "stroke:#000000,fill:#e6f4f3",
    "LazyVar": "stroke:#000000,fill:#e8e6f4",
}

re_var = re.compile(r"\$\{.*?(?P<name>\w*).*?\}")


@dataclass
class BambooVisualizer:
    """
    流程图可视化渲染器
    """

    pipeline_tree: Optional[Dict[str, Any]] = None
    buffer: List[str] = field(default_factory=list)
    subprocesses: List[Dict[str, Any]] = field(default_factory=list)
    flow_annotations: Dict[str, str] = field(default_factory=dict)
    links: List[str] = field(default_factory=list)
    pipeline_data: Dict[str, BambooPipelineData] = field(default_factory=dict)

    def declare_flow_annotation(self, flow_id: str, annotation: str):
        self.flow_annotations[flow_id] = annotation

    def get_flow_annotation(self, flow_id: str) -> str:
        return self.flow_annotations.get(flow_id, "")

    def declare_pipeline_data(self, pipeline_id: str, key: str, variable_data: Dict[str, Any]):
        ref_id = md5(f"{pipeline_id}-{key}".encode()).hexdigest()
        pipeline_data = BambooPipelineData(key, ref_id, variable_data)
        self.pipeline_data[key] = pipeline_data
        return pipeline_data

    def declare_link(self, source: str, style: Tuple[str, str], target: str, annotation: str = ""):
        if annotation:
            link = style[1].format(self.escape_text(annotation))
        else:
            link = style[0]

        self.links.append(f"{source} {link} {target}")

    def get_pipeline_data(self, key: str) -> Optional[BambooPipelineData]:
        return self.pipeline_data.get(key)

    def write_line(self, ident: int, content: str):
        self.buffer.append(f"{'  ' * ident}{content}")

    def declare_node(self, ident: int, id: str, name: str, annotation_template: str, style: str = "Normal"):
        annotation = annotation_template.format(self.escape_text(name or id))
        self.write_line(ident, f"{id}{annotation}:::{style}")

    def escape_text(self, text: str, *candidates: str) -> str:
        if not text:
            for candidate in candidates:
                text = candidate
                if text:
                    break

        escape_char_mapping = {"{": "#123;", "}": "#125;", "[": "#91;", "]": "#93;", "|": "#124;", "$": "#36;"}

        for char, escape_char in escape_char_mapping.items():
            text = text.replace(char, escape_char)

        return text

    @contextmanager
    def declare_subgraph(self, ident: int, id: str, name: str, style_class: str = ""):
        self.write_line(ident, "")
        self.write_line(ident, f'subgraph {id}["{self.escape_text(name, id)}"]')

        yield ident + 1

        self.write_line(ident, "end")

        if style_class:
            self.write_line(ident, f"class {id} {style_class}")

        self.write_line(ident, "")

    def declare_start_event(self, pipeline_tree: Dict[str, Any], ident: int):
        start_event = pipeline_tree["start_event"]
        self.write_line(ident, f"{start_event['id']}(( )):::StartEvent")

    def declare_end_event(self, pipeline_tree: Dict[str, Any], ident: int):
        end_event = pipeline_tree["end_event"]
        self.write_line(ident, f"{end_event['id']}(( )):::EndEvent")

    def declare_activities(self, pipeline_tree: Dict[str, Any], ident: int):
        self.write_line(ident, "")

        for activity in pipeline_tree["activities"].values():
            self.declare_activity(activity, ident)
            self.declare_subprocesses(activity)

    def declare_activity(self, activity: Dict[str, Any], ident: int):
        self.declare_node(ident, activity["id"], activity["name"], NODE_NORMAL, activity["type"])
        self.declare_activity_inputs(activity)
        self.declare_activity_params(activity)

    def declare_variable_ref(self, target_id: str, key: str, variable_data: Dict[str, Any]):
        data_type = variable_data["type"]

        if data_type == "plain":
            return

        if data_type == "lazy":
            key = f"{key}({variable_data['custom_type']})"

        for var in re_var.findall(str(variable_data["value"])):
            pipeline_data = self.get_pipeline_data(var)
            if not pipeline_data:
                continue

            # 输入变量引用
            self.declare_link(pipeline_data.ref_id, LINK_DOTTED_ARROW, target_id, key)

    def declare_activity_inputs(self, activity: Dict[str, Any]):
        component = activity.get("component")
        if not component:
            return

        inputs = component.get("inputs")
        if not inputs:
            return

        for key, data in inputs.items():
            self.declare_variable_ref(activity["id"], key, data)

    def declare_activity_params(self, activity: Dict[str, Any]):
        params = activity.get("params")
        if not params:
            return

        for key, data in params.items():
            self.declare_variable_ref(activity["id"], key, data)

    def declare_subprocesses(self, activity: Dict[str, Any]):
        pipeline = activity.get("pipeline")

        if not pipeline:
            return

        self.declare_link(activity["id"], LINK_DOTTED, f"S-{activity['id']}", "extend")
        self.subprocesses.append(activity)

    def declare_gateways(self, pipeline_tree: Dict[str, Any], ident: int):
        self.write_line(ident, "")

        for gateway in pipeline_tree["gateways"].values():
            self.declare_node(ident, gateway["id"], gateway["name"], NODE_HEXAGON, gateway["type"])
            self.declare_gateway_conditions(gateway)

    def declare_gateway_conditions(self, gateway: Dict[str, Any]):
        conditions = gateway.get("conditions")
        if not conditions:
            return

        for flow_id, condition in conditions.items():
            self.declare_flow_annotation(flow_id, condition["evaluate"])

    def declare_flows(self, pipeline_tree: Dict[str, Any], ident: int):
        for flow in pipeline_tree["flows"].values():
            self.declare_flow(flow, ident)

    def declare_flow(self, flow: Dict[str, Any], ident: int):
        link_style = LINK_NORMAL_ARROW
        if flow["is_default"]:
            link_style = LINK_THICK_ARROW

        annotation = self.get_flow_annotation(flow["id"])
        self.declare_link(flow["source"], link_style, flow["target"], annotation)

    def declare_pipeline_context(self, pipeline_tree: Dict[str, Any], ident: int):
        for key, variable_data in pipeline_tree["data"]["inputs"].items():
            matched = re_var.search(key)
            if not matched:
                continue

            result = matched.groupdict()
            pipeline_data = self.declare_pipeline_data(pipeline_tree["id"], result["name"], variable_data)

            self.declare_node(
                ident, pipeline_data.ref_id, key, NODE_ASYMMENTRIC_SHAPE, f"{variable_data['type'].title()}Var"
            )
            self.declare_pipeline_context_outputs(key, pipeline_data)
            self.declare_pipeline_context_ref(key, pipeline_data)

    def declare_pipeline_context_outputs(self, key: str, pipeline_data: BambooPipelineData):
        variable_data = pipeline_data.variable_data

        if "source_act" not in variable_data:
            return

        # 输出变量引用
        node_outputs = []
        if isinstance(variable_data["source_act"], list):
            node_outputs = variable_data["source_act"]
        else:
            node_outputs.append(variable_data)

        for output in node_outputs:
            self.declare_link(output["source_act"], LINK_DOTTED_ARROW, pipeline_data.ref_id, output["source_key"])

    def declare_pipeline_context_ref(self, key: str, pipeline_data: BambooPipelineData):
        variable_data = pipeline_data.variable_data

        if variable_data["type"] == "plain":
            return

        self.declare_variable_ref(pipeline_data.ref_id, key, variable_data)

    def handle_pipeline(self, pipeline_tree: Dict[str, Any], ident: int):
        pipeline_id = pipeline_tree["id"]

        with self.declare_subgraph(ident, f"C-{pipeline_id}", "Context", "Context") as graph_ident:
            self.declare_pipeline_context(pipeline_tree, graph_ident)

        with self.declare_subgraph(ident, f"F-{pipeline_id}", "Flow", "Flow") as graph_ident:
            self.declare_start_event(pipeline_tree, graph_ident)
            self.declare_end_event(pipeline_tree, graph_ident)
            self.declare_activities(pipeline_tree, graph_ident)
            self.declare_gateways(pipeline_tree, graph_ident)
            self.declare_flows(pipeline_tree, graph_ident)

    def handle_subprocesses(self, ident: int):
        if not self.subprocesses:
            return

        for activity in self.subprocesses:
            with self.declare_subgraph(ident, f"S-{activity['id']}", activity["name"], "SubProcess") as subgraph_ident:
                self.handle_pipeline(activity["pipeline"], subgraph_ident)

    def render_json(self) -> str:
        assert self.pipeline_tree
        return json.dumps(self.pipeline_tree)

    def render(self) -> str:
        """渲染流程图"""

        assert self.pipeline_tree

        self.buffer = []
        ident = 0
        self.write_line(ident, "flowchart LR;")

        for name, style in visualizer_classes_styles.items():
            self.write_line(ident, f"classDef {name} {style}")

        self.handle_pipeline(self.pipeline_tree, ident)
        self.handle_subprocesses(ident)

        for link in self.links:
            self.write_line(ident, link)

        return "\n".join(self.buffer)
