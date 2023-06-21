# 自定义结束事件处理器

在某些场景下，我们可能会需要在一个任务结束之后执行一段自定义的业务逻辑，很多上层的应用都会封装自己的任务抽象，例如希望pipeline的任务结束时修改业务层的任务状态为**已完成**。

此时使用默认的`EmptyEndEvent` ，我们除了轮询任务状态之后我们将无法第一时间感知到任务结束的事件。

而`ExecutableEndEvent` 提供了一种可执行的结束事件，允许我们在运行到结束节点时执行一段特定的业务逻辑。

具体使用方式如下:

首先我们需要自定义一个我们自己的`ExecutableEndEvent`实现，并将它注册到FlowNodeClsFactory里面。通常我们建议这段逻辑放到应用初始化的阶段来做。

之后为们需要实现自己的 execute 方法，该方法接收三个参数：

- in_subprocess 是否是子流程的end事件
- root_pipeline_id 根 `pipeline id`
- current_pipeline_id 当前的`pipeline_id`

```python
from bamboo_engine.validator import api
from pipeline.core.flow import ExecutableEndEvent, FlowNodeClsFactory

class CustomExecutableEndEvent(ExecutableEndEvent):
    def execute(self, in_subprocess, root_pipeline_id, current_pipeline_id):
        print("it is executed")

api.add_sink_type("CustomExecutableEndEvent")
FlowNodeClsFactory.register_node("CustomExecutableEndEvent", CustomExecutableEndEvent)
```

之后我们需要再构建流程时使用ExecutableEndEvent并指定为我们自定义的`CustomExecutableEndEvent`。需要注意的是，构建流程的`ExecutableEndEvent` 使用的是`bamboo_engine.builder`模块下的。

构建一个新的实例:
```python

from pipeline.eri.runtime import BambooDjangoRuntime  
from bamboo_engine import api  
from bamboo_engine.builder import EmptyStartEvent, ServiceActivity, Data, build_tree,ExecutableEndEvent

start = EmptyStartEvent()
buy_ticket = ServiceActivity(component_code='example_component', name='example_component')
# 这里的type需要指定为我们自定义的type
end = ExecutableEndEvent(type="CustomExecutableEndEvent")
start.extend(buy_ticket).extend(end)
pipeline_data = Data()
pipeline = build_tree(start, data=pipeline_data)
api.run_pipeline(runtime=BambooDjangoRuntime(), pipeline=pipeline)
```

之后当流程运行到结束节点时，将会调用CustomExecutableEndEvent的execute方法了。