### 功能介绍:

节点回退允许流程回退到某个特定的节点重新开始。**该回退会删除目标节点之后所有已执行过的节点信息和数据，让流程表现的是第一次执行的样子。**

需要注意的流程的回退并不是无限制的，需要满足以下条件的节点才允许回退。
- 只能回退运行中的流程
- 子流程暂时不支持回退
- 目标节点的状态必须为已完成状态
- 并行网关内的节点不允许回退。并行网关包含条件并行网关和并行网关
- 网关节点不允许回退
- 条件网关只允许条件网关内已经运行的节点允许回退，未执行到的分支不允许回退。

节点在回退前会强制失败掉当前运行的节点，只有流程中没有正在运行的节点时才会开始执行回退逻辑。
节点回退的过程无法中断，因为中断导致的回退失败可能会导致无法通过再次回退重试成功

针对如下图的流程，蓝色框所标注的节点是允许回退的节点。

![rollback.png](..%2Fassets%2Fimg%2Frollback%2Frollback.png)

### 使用事例:

查询可以回退的节点列表:
```python
from pipeline.contrib.rollback import api

# 获取该pipeline允许回滚的节点列表
result = api.get_allowed_rollback_node_id_list(pipeline_id)
node_ids = result.data
```

节点的回退使用非常简单，只需要指定pipeline_id和node_id即可，如下所示:
```python
from pipeline.contrib.rollback import api

result = api.rollback(pipeline_id, node_id)

if result.result:
    pass
```