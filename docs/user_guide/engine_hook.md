# Hook 事件

## 自定义组件主动处理机制

Bamboo 将以**同步**通知的方式，将事件推送到开启 hook 通知的 `ServiceActivity` 内，以此完善和增强 `ServiceActivity`
的生命周期可管理能力

### 开启自定义组件 Hook 功能

只需要在组件服务 `Service` 内声明 `__need_run_hook__ = True` 即可开启

```python
from pipeline.core.flow.activity import Service


class CustomService(Service):
    def node_execute_exception(self, data, parent_data):
        """节点 execute 异常后"""
        return True

    def node_schedule_exception(self, data, parent_data, callback_data=None):
        """节点调度失败后"""
        return True

    def node_enter(self, data, parent_data):
        """节点 execute 前"""
        return True

    def node_finish(self, data, parent_data):
        """节点执行结束"""
        return True

    ...
```

### 所有支持的 Hook

> 开发者可以在自定义 `ServiceActivity` 定义同名钩子方法用于消费事件

| hook                      | 事件                                  | 数据只读 |
|---------------------------|-------------------------------------|------|
| pre_resume_node           | 节点继续前                               | ✅    |
| post_resume_node          | 节点继续后                               | ✅    |
| pre_pause_node            | 节点暂停前                               | ✅    |
| post_pause_node           | 节点暂停后                               | ✅    |
| pre_retry_node            | 节点重试前                               | ✅    |
| post_retry_node           | 节点重试后                               | ✅    |
| pre_skip_node             | 节点跳过前                               | ✅    |
| post_skip_node            | 节点跳过后                               | ✅    |
| pre_forced_fail_activity  | 强制失败节点前                             | ✅    |
| post_forced_fail_activity | 强制失败节点后                             | ✅    |
| pre_callback              | 回调节点前                               |      |
| node_execute_fail         | 节点 execute 失败后，如果节点配置忽略失败，该钩子不会触发   |      |
| node_schedule_fail        | 节点 schedule 失败后， 如果节点配置忽略失败，该钩子不会触发 |      |
| node_execute_exception    | 节点 execute 异常后                      |      |
| node_schedule_exception   | 节点 schedule 异常后                     |      |
| node_enter                | 节点 execute 前                        |      |
| node_finish               | 节点执行结束                              |      |

什么是「数据只读」？数据只读表示活动节点数据（data、parent_data）在执行钩子函数过程中的变更（`set_outputs`）
是否会被保存。由于部分操作（resume、pause、retry）是异步操作，为了避免 Hook 和执行主逻辑同时加工数据带来的理解成本和不可控变更，对于这部分操作，仅提供数据只读，请避免在这些
hook 方法内使用 `set_outputs` 等方法保存数据。

## 开启引擎信号通知

只需要在 django.settings 里面加上:

> ⚠️注意，由于 django signal 是同步的信号机制，所以请不要在 signal handler 中执行耗时过长的逻辑，可能会影响引擎整体的执行效率

```python
ENABLE_PIPELINE_EVENT_SIGNALS = True
```

### 信号的结构

信号的内容由两部分组成，分别是 event_type 和 data。

```json
{
  "event_type": "self.event_type",
  "data": "self.data"
}
```

### 信号的使用

```python
from pipeline.eri.signals import pipeline_event


def event_dispatcher(
        sender, event, **kwargs
):
    pass


pipeline_event.connect(receiver=event_dispatcher)

```

### 信号的说明

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

event_type: node_execute_exception
desc: 节点 execute 方法异常后需要执行的钩子  
data:

```json
{
  "root_pipeline_id": "root_pipeline_id",
  "node_id": "node_id",
  "ex_data": "ex_data"
}
```

event_type: node_schedule_exception
desc: 节点 schedule 方法异常后需要执行的钩子  
data:

```json
{
  "root_pipeline_id": "root_pipeline_id",
  "node_id": "node_id",
  "ex_data": "ex_data"
}
```

event_type: node_execute_fail  
desc: 节点 execute 失败后需要执行的钩子，如果节点配置忽略失败，该钩子不会触发
data:

```json
{
  "root_pipeline_id": "root_pipeline_id",
  "node_id": "node_id"
}
```

event_type: node_schedule_fail  
desc: 节点 schedule 失败后需要执行的钩子，如果节点配置忽略失败，该钩子不会触发
data:

```json
{
  "root_pipeline_id": "root_pipeline_id",
  "node_id": "node_id"
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