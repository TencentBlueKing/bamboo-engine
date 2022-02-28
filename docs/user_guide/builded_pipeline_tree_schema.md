## Pipeline生成树字段摘要

当调用`pipeline_tree=builder.build_tree()`之后，我们可快速获得pipeline流程对应的生成树，生成树对应的字段和含义如下：

```yaml
pipeline_tree:
  description: The builded tree of bamboo engine
  type: dict
  properties:
    id: 
      description: The uuid of tree
      type: string
    start_event: 
      description: The start event node of tree
      type: dict
      properties:
        id:
          description: The uuid of start event node
          type: string
        incoming:
          description: The incoming flow of start event node
          type: string
        name: 
          description: The name of start event node
          type: string
        outgoing:
          description: The outgoing flow of start event node
          type: string
        type: 
          description: The node type of start event node
          type: string
    end_event: 
      description: The end event node of tree
      type: dict
      properties:
        id:
          description: The uuid of end event node
          type: string
        incoming:
          description: The incoming flows of end event node
          type: list[string]
        name: 
          description: The name of end event node
          type: string
        outgoing:
          description: The outgoing flow of end event node
          type: string
        type: 
          description: The node type of end event node
          type: string
    activities: 
      description: The activity nodes in pipeline
      type: dict
      properties: 
        $node_id:
          description: The activity node
          properties: 
            id: 
              description: The uuid of activity node
              type: string
            name: 
              description: The name of activity node
              type: string
            incoming: 
              description: The incoming flows of activity node
              type: list[string]
            outgoing:
              description: The outgoing flow of activity node
              type: string
            type: 
              description: The node type of activity node
              type: string
            error_ignore: 
              description: If the failure of node be ignored
              type: boolean
            optional:
              description: If the node can be excluded when executing
              type: boolean
            retryable: 
              description: If the node can be retried
              type: boolean
            skippable: 
              description: If the node can be skipped
              type: boolean
            timeout: 
              description: Deprecated field
            component: 
              description: The component which defines the activity of the node
              type: dict
              properties: 
                code: 
                  description: The unique code of the component
                  type: string
                inputs: 
                  description: The inputs defined in the component
                  type: dict
    flows:
      description: The flows in pipeline
      type: dict
      properties: 
        $flow_id:
          description: The flow
          type: dict
          properties: 
            id: 
              description: The uuid of flow
              type: string
            source:
              description: The node id which is the source of flow
              type: string
            target:
              description: The node id which is the target of flow
              type: string
            is_default:
              description: Deprecated field
    gateways: 
      description: The gateways in pipeline
      type: dict
      properties: 
        $gateway_id:
          description: The gateway
          type: dict
          properties: 
            id: 
              description: The uuid of gateway
              type: string
            name: 
              description: The name of gateway
              type: string
            outgoing: 
              description: The outgoing flows of gateway
              type: list
    data: 
      description: pipeline data
      type: dict
      properties: 
        inputs: 
          description: The inputs of pipeline
          type: dict
        outputs:
          description: The outputs of pipeline
          type: list
```

下面是一个流程树生成之后的示例：
```json
{
    "activities": {
        "eb456a70affdf47ae9d96c5d196d36b09": {
            "component": {
                "code": "example_component",
                "inputs": {}
            },
            "error_ignorable": False,
            "id": "eb456a70affdf47ae9d96c5d196d36b09",
            "incoming": [
                "f216d744eae614b71b3ca88002fe81439"
            ],
            "name": "",
            "optional": False,
            "outgoing": "f42b0a808b63f4315bb9b51159617797c",
            "retryable": True,
            "skippable": True,
            "timeout": None,
            "type": "ServiceActivity"
        }
    },
    "data": {
        "inputs": {},
        "outputs": []
    },
    "end_event": {
        "id": "e1f45d04d298a4a1e8510fb6d7dd496d2",
        "incoming": [
            "f42b0a808b63f4315bb9b51159617797c"
        ],
        "name": "",
        "outgoing": "",
        "type": "EmptyEndEvent"
    },
    "flows": {
        "f216d744eae614b71b3ca88002fe81439": {
            "id": "f216d744eae614b71b3ca88002fe81439",
            "is_default": False,
            "source": "e817acc99284348cf9caa45fe0dd0cff4",
            "target": "eb456a70affdf47ae9d96c5d196d36b09"
        },
        "f42b0a808b63f4315bb9b51159617797c": {
            "id": "f42b0a808b63f4315bb9b51159617797c",
            "is_default": False,
            "source": "eb456a70affdf47ae9d96c5d196d36b09",
            "target": "e1f45d04d298a4a1e8510fb6d7dd496d2"
        }
    },
    "gateways": {},
    "id": "pa08352b3bded40768f90912731820b87",
    "start_event": {
        "id": "e817acc99284348cf9caa45fe0dd0cff4",
        "incoming": "",
        "name": "",
        "outgoing": "f216d744eae614b71b3ca88002fe81439",
        "type": "EmptyStartEvent"
    }
}
```