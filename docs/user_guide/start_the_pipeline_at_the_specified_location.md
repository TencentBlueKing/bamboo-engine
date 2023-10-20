# 指定流程从某个位置开始执行

默认的 run_pipeline_api 只允许流程从开始节点开始，再某些特殊的场景下，用户可能会新起一个任务，并期望从指定的位置开始。
因此run_pipeline 支持了该特性，不过需要注意的是，该功能是受限的，这意味着你不能选择流程内的任意一个位置开始流程。

使用方式:

```python
from pipeline.eri.runtime import BambooDjangoRuntime
from bamboo_engine import api

pipeline = {}
# 可以使用root_pipeline_context的方式补充缺失的上下文信息
api.run_pipeline(runtime=BambooDjangoRuntime(),
                 pipeline=pipeline, 
                 start_node_id="xxxxx", 
                 root_pipeline_context={})
```

使用范围:

start_node_id 的指定需要遵循如下规则:

- 只允许开始节点和位于流程中的主干节点和分支网关内的节点进行回滚，不允许并行网关内的节点作为开始的起始位置，当分支网关处于并行网关内时，该分支网关内的节点也无法作为开始的起始位置。
- 位于主流程上的并行网关/条件并行网关/条件网关 允许作为起始节点，汇聚网关不允许作为流程的开始节点。
- 子流程节点不允许作为流程的开始节点
- 结束节点不允许作为流程的开始节点

下图红框内的节点表示允许作为起始位置的节点。

![run_pipeline.png](..%2Fassets%2Fimg%2Fstart_the_pipeline_at_the_specified_location%2Frun_pipeline.png)