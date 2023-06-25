# 修改某个节点的输出

在某些特定的场景下，一个节点执行失败且需要跳过，而后续的节点又依赖了该节点的某个输出，这个时候如果直接跳过该节点则会导致流程异常。

目前提高了可以修改流程中某个节点上输出并同步修改流程上下文的能力，需要注意的是，该api不会在系统内留下任何修改记录。为了保证因为修改流程上下文而导致的流程问题，该api提供了三个限制:
- 只运行修改状态为运行中的任务
- 只允许更新状态为失败的节点的输出
- 内置变量不允许修改

该API 主要做了以下两件事:
- 更新pipeline context values的值，如果没有匹配到则不更新，这里修改的值是后续使用该变量实际的值。
- 更新该节点的执行数据的outputs部分。


使用方法:
该api的使用方法非常简单:
```python
from pipeline.contrib.mock import api

context_values = {
	"${status_code}": 500
}
api.update_pipeline_context("pipeline_id", "node_id", context_values)
```

当上下文更新失败时，将会抛出`UpdatePipelineContextException` 异常

