#### 开启引擎信号通知

只需要在 django.settings 里面加上:

> ⚠️注意，由于 django signal 是同步的信号机制，所以请不要在 signal handler 中执行耗时过长的逻辑，可能会影响引擎整体的执行效率


```python
ENABLE_PIPELINE_EVENT_SIGNALS = True
```

##### 信号的结构:
信号的内容由两部分组成，分别是 event_type 和 data。
```json
{  
	"event_type": "self.event_type",  
	"data": "self.data"
}
```

#### 信号的使用:

```python
from pipeline.eri.signals import pipeline_event

def event_dispatcher(
        sender, event, **kwargs
):
	pass

pipeline_event.connect(receiver=event_dispatcher)

```

### 信号的说明:

event_type:  pre_prepare_run_pipeline  
desc: 调用 pre_prepare_run_pipeline 前执行的钩子  
data:  
```python
{
    "pipeline": "",
    "root_pipeline_data": "root_pipeline_data",
    "root_pipeline_context": "root_pipeline_context",
    "subprocess_context": "subprocess_context"
}
```

event_type: post_prepare_run_pipeline  
desc: 调用 pre_prepare_run_pipeline 后执行的钩子  
data:  
```json
{
    "pipeline": "",
    "root_pipeline_data": "root_pipeline_data",
    "root_pipeline_context": "root_pipeline_context",
    "subprocess_context": "subprocess_context"
}
```

event_type: pre_pause_pipeline  
desc: 暂停 pipeline 前执行的钩子  
data:
```json
{
    "pipeline": ""
}
```

event_type: post_pause_pipeline  
desc: 暂停 pipeline 后执行的钩子  
data:
```json
{
    "pipeline_id": ""
}
```

event_type: pre_revoke_pipeline  
desc: 撤销 pipeline 前执行的钩子  
data: 
```json
{
    "pipeline_id": ""
}
```

event_type: post_revoke_pipeline  
desc: 撤销 pipeline 前执行的钩子  
data: 
```json
{
    "pipeline_id": ""
}
```

event_type: pre_resume_pipeline  
desc: 继续 pipeline 前执行的钩子  
data: 
```json
{
    "pipeline_id": ""
}
```

event_type: post_resume_pipeline  
desc: 继续 pipeline 后执行的钩子  
data:  
```json
{
    "pipeline_id": ""
}
```

event_type: pre_resume_node  
desc: 继续节点后执行的钩子  
data:
```json
{
    "node_id": ""
}
```

event_type: post_resume_node  
desc: 继续节点后执行的钩子  
data:
```json
{
    "node_id": ""
}
```

event_type: pre_pause_node  
desc: 暂停节点前执行的钩子  
data:
```json
{
    "node_id": ""
}
```

event_type: post_pause_node  
desc: 暂停节点后执行的钩子  
data:
```json
{
    "node_id": ""
}
```

event_type: pre_retry_node  
desc: 重试节点前执行的钩子  
data:
```json
{
    "node_id": "",
    "data": {}
}
```

event_type: post_retry_node  
desc: post_retry_node  
data:
```json
{
    "node_id": "",
    "data": {}
}
```

event_type: pre_skip_node  
desc: pre_skip_node  
data: 
```json
{
    "node_id": ""
}
```


event_type: post_skip_node  
desc: 跳过节点后执行的钩子  
data:
```json
{
    "node_id": ""
}
```


event_type: pre_skip_exclusive_gateway  
desc: 跳过分支网关前执行的钩子  
data:
```json
{
    "node_id": "",
    "flow_id": ""
}
```

event_type: post_skip_exclusive_gateway  
desc: 跳过分支网关后执行的钩子  
data:  
```json
{
    "node_id": "",
    "flow_id": ""
}
```

event_type: pre_skip_conditional_parallel_gateway  
desc: 跳过条件并行网关前执行的钩子  
data:   
```json
{
    "node_id": "",
    "flow_ids": "",
    "converge_gateway_id": ""
}
```

event_type: post_skip_conditional_parallel_gateway  
desc: 跳过条件并行网关后执行的钩子  
data:
```json
{
    "node_id": "",
    "flow_ids": "",
    "converge_gateway_id": ""
}
```

event_type: pre_forced_fail_activity  
desc: 强制失败节点前执行的钩子  
data:
```json
{
    "node_id": "",
    "ex_data": ""
}
```

event_type: post_forced_fail_activity  
desc: 强制失败节点后执行的钩子  
data:
```json
{
    "node_id": "",
    "ex_data": "",
    "old_version": "",
    "new_version": ""
}
```

event_type: pre_callback  
desc: 回调节点前执行的钩子  
data:
```json
{
    "node_id": "",
    "version": "",
    "data": ""
}
```

event_type: post_callback  
desc: 回调节点后执行的钩子  
data:
```json
{
    "node_id": "",
    "version": "",
    "data": ""
}
```

event_type: pre_retry_subprocess  
desc: 子流程重试前执行的钩子  
data:
```json
{
	"node_id": ""
}
```


event_type: post_retry_subprocess  
desc:  子流程重试后执行的钩子  
data:
```json
{
	"node_id": ""
}
```

event_type: node_execute_fail  
desc: 节点execute方法异常需要执行的钩子  
data:
```json
{
    "root_pipeline_id": "root_pipeline_id",
    "node_id": "node_id",
    "ex_data": "ex_data"
}
```

event_type: node_schedule_fail  
desc: 节点schedule方法异常需要执行的钩子  
data:
```json
{
    "root_pipeline_id": "root_pipeline_id",
    "node_id": "node_id",
    "ex_data": "ex_data"
}
```

event_type: node_enter  
desc: 进入节点前  
data:
```json
{
    "root_pipeline_id": "root_pipeline_id",
    "node_id": "node_id",
    "ex_data": "ex_data"
}
```

event_type: node_finish  
desc: 离开节点需要执行的钩子  
data:
```json
{
    "root_pipeline_id": "root_pipeline_id",
    "node_id": "node_id"
}
```

event_type: pipeline_finish  
desc: 离开节点需要执行的钩子  
data:
```json
{
    "root_pipeline_id": "root_pipeline_id",
    "node_id": "node_id"
}
```