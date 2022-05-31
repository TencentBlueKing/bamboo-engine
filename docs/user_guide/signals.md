
## Django Signal

pipeline runtime 提供了以下 django signal，可作为流程运行生命周期中的钩子使用。

> ⚠️注意，由于 django signal 是同步的信号机制，所以请不要在 signal handler 中执行耗时过长的逻辑，可能会影响引擎整体的执行效率

### post_set_state

```python
post_set_state = Signal(providing_args=["node_id", "to_state", "version", "root_id", "parent_id", "loop"])
```

某个节点的状态修改后触发的信号

sender 为 `pipeline.eri.models.State`

参数

- `node_id: str`: 节点 ID
- `to_state: str`: 节点的目标状态，可能的值为 `bamboo_engine.states.StateType` 中的枚举
- `version: str`: 节点状态的当前版本
- `root_id: str`: 节点所属根流程 ID
- `parent_id: str`: 节点所属父流程 ID
- `loop: int`: 节点当前 loop 值

### execute_interrupt

```python
execute_interrupt = Signal(providing_args=["event"])
```

发生 execute 中断后触发的信号

sender 为 `bamboo_engine.eri.models.ExecuteInterruptEvent` 的实例

参数

- `event: bamboo_engine.eri.models.ExecuteInterruptEvent`: 中断事件

### schedule_interrupt

```python
schedule_interrupt = Signal(providing_args=["event"])
```

发生 schedule 中断后触发的信号

sender 为 `bamboo_engine.eri.models.ScheduleInterruptEvent` 的实例

参数

- `event: bamboo_engine.eri.models.ScheduleInterruptEvent`: 中断事件

### pre_service_execute

```python
pre_service_execute = Signal(providing_args=["service", "data", "parent_data"])
```

ServiceActivity 对应的 Service execute 前触发的信号

sender 为 `pipeline.eri.imp.service.ServiceWrapper`

参数

- `service: pipeline.core.flow.activity.Service`: 即将执行的 Service 实例
- `data: pipeline.core.data.base.DataObject`: 即将传递给的 Service.execute 的 data
- `parent_data: pipeline.core.data.base.DataObject`: 即将传递给的 Service.execute 的 parent_data

### pre_service_schedule

```python
pre_service_schedule = Signal(providing_args=["service", "data", "parent_data", "callback_data"])
```

ServiceActivity 对应的 Service schedule 前触发的信号

sender 为 `pipeline.eri.imp.service.ServiceWrapper`

参数

- `service: pipeline.core.flow.activity.Service`: 即将执行的 Service 实例
- `data: pipeline.core.data.base.DataObject`: 即将传递给的 Service.schedule 的 data
- `parent_data: pipeline.core.data.base.DataObject`: 即将传递给的 Service.schedule 的 parent_data
- `callback_data: dict`: 即将传递给的 Service.schedule 的 callback_data
