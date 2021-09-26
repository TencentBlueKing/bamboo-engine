<!-- TOC -->

- [Engine API](#1-EngineAPI)
    - [run_pipeline](#11-run_pipeline)
        - [example](#111-example)
    - [pause_pipeline](#12-pause_pipeline)
        - [example](#121-example)
    - [revoke_pipeline](#13-revoke_pipeline)
        - [example](#131-example)
    - [resume_pipeline](#14-resume_pipeline)
        - [example](#141-example)
    - [pause_node_appoint](#15-pause_node_appoint)
        - [example](#151-example)
    - [resume_node_appoint](#16-resume_node_appoint)
        - [example](#161-example)
    - [retry_node](#17-retry_node)
        - [example](#171-example)
    - [retry_subprocess](#18-retry_subprocess)
        - [example](#181-example)
    - [skip_node](#19-skip_node)
        - [example](#191-example)
    - [skip_exclusive_gateway](#110-skip_exclusive_gateway)
        - [example](#1101-example)
  - [skip_conditional_parallel_gateway](#111-skip_conditional_parallel_gateway)
      - [example](#1111-example)
    - [forced_fail_activity](#112-forced_fail_activity)
        - [example](#1121-example)
    - [callback](#113-callback)
        - [example](#1131-example)
    - [get_pipeline_states](#114-get_pipeline_states)
        - [example](#1141-example)
    - [get_children_states](#115-get_children_states)
        - [example](#1151-example)
    - [get_execution_data_inputs](#116-get_execution_data_inputs)
        - [example](#1161-example)
    - [get_execution_data_outputs](#117-get_execution_data_outputs)
        - [example](#1171-example)
    - [get_execution_data](#118-get_execution_data)
        - [example](#1181-example)
    - [get_data](#119-get_data)
        - [example](#1191-example)
    - [get_node_histories](#120-get_node_histories)
        - [example](#1201-example)
    - [get_node_short_histories](#121-get_node_short_histories)
        - [example](#1211-example)

<!-- /TOC -->






<a id="toc_anchor" name="#1-EngineAPI"></a>

# 1. Engine API

所有与 bamboo_engine 的交互都应该通过 bamboo_engine.api 来进行，所有的 Engine API 的返回对象均为 `bamboo_engine.api.EngineAPIResult`：

```python
class EngineAPIResult:
    def __init__(
        self,
        result: bool,
        message: str,
        exc: Optional[Exception] = None,
        data: Optional[Any] = None,
    ):
        """
        :param result: 是否执行成功
        :type result: bool
        :param message: 附加消息，result 为 False 时关注
        :type message: str
        :param exc: 异常对象
        :type exc: Exception
        :param data: 数据
        :type data: Any
        """
        self.result = result
        self.message = message
        self.exc = exc
        self.data = data
```

<a id="toc_anchor" name="#11-run_pipeline"></a>

## 1.1. run_pipeline

```python
def run_pipeline(
    self,
    pipeline: dict,
    root_pipeline_data: Optional[dict] = None,
    root_pipeline_context: Optional[dict] = None,
    subprocess_context: Optional[dict] = None,
    **options
):
    """
    运行流程

    :param pipeline: 流程数据
    :type pipeline: dict
    :param root_pipeline_data 根流程数据
    :type root_pipeline_data: dict
    :param root_pipeline_context 根流程上下文
    :type root_pipeline_context: dict
    :param subprocess_context 子流程预置流程上下文
    :type subprocess_context: dict
    """
```

<a id="toc_anchor" name="#111-example"></a>

### 1.1.1. example

```python
start = EmptyStartEvent()
act = ServiceActivity(component_code="example_component")
end = EmptyEndEvent()

start.extend(act).extend(end)

pipeline = builder.build_tree(start)

runtime = BambooDjangoRuntime()
api.run_pipeline(runtime=runtime, pipeline=pipeline).result
# True
```

<a id="toc_anchor" name="#12-pause_pipeline"></a>

## 1.2. pause_pipeline

```python
def pause_pipeline(
    runtime: EngineRuntimeInterface, pipeline_id: str
) -> EngineAPIResult:
    """
    暂停 pipeline 的执行

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param pipeline_id: piipeline id
    :type pipeline_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```
<a id="toc_anchor" name="#121-example"></a>

### 1.2.1. example

```python
runtime = BambooDjangoRuntime()
api.run_pipeline(runtime=runtime, pipeline_id="pipeline id").result
# True
```

<a id="toc_anchor" name="#13-revoke_pipeline"></a>

## 1.3. revoke_pipeline

```python
def revoke_pipeline(
    runtime: EngineRuntimeInterface, pipeline_id: str
) -> EngineAPIResult:
    """
    撤销 pipeline，使其无法继续执行

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param pipeline_id: pipeline id
    :type pipeline_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#131-example"></a>

### 1.3.1. example

```python
runtime = BambooDjangoRuntime()
api.revoke_pipeline(runtime=runtime, pipeline_id="pipeline id").result
# True
```

<a id="toc_anchor" name="#14-resume_pipeline"></a>

## 1.4. resume_pipeline

```python
def resume_pipeline(
    runtime: EngineRuntimeInterface, pipeline_id: str
) -> EngineAPIResult:
    """
    继续被 pause_pipeline 接口暂停的 pipeline 的执行

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param pipeline_id: pipeline id
    :type pipeline_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#141-example"></a>

### 1.4.1. example

```python
runtime = BambooDjangoRuntime()
api.resume_pipeline(runtime=runtime, pipeline_id="pipeline id").result
# True
```


<a id="toc_anchor" name="#15-pause_node_appoint"></a>

## 1.5. pause_node_appoint

```python
def pause_node_appoint(
    runtime: EngineRuntimeInterface, node_id: str
) -> EngineAPIResult:
    """
    预约暂停某个节点的执行

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 id
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#151-example"></a>

### 1.5.1. example

```python
runtime = BambooDjangoRuntime()
api.pause_node_appoint(runtime=runtime, node_id="node_id").result
# True
```

<a id="toc_anchor" name="#16-resume_node_appoint"></a>

## 1.6. resume_node_appoint

```python
def resume_node_appoint(
    runtime: EngineRuntimeInterface, node_id: str
) -> EngineAPIResult:
    """
    继续由于某个节点而暂停的 pipeline 的执行

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 id
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#161-example"></a>

### 1.6.1. example

```python
runtime = BambooDjangoRuntime()
api.resume_node_appoint(runtime=runtime, node_id="node_id").result
# True
```

<a id="toc_anchor" name="#17-retry_node"></a>

## 1.7. retry_node

```python
def retry_node(
    runtime: EngineRuntimeInterface, node_id: str, data: Optional[dict] = None
) -> EngineAPIResult:
    """
    重试某个执行失败的节点

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 失败的节点 id
    :type node_id: str
    :param data: 重试时使用的节点执行输入
    :type data: dict
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#171-example"></a>

### 1.7.1. example

```python
runtime = BambooDjangoRuntime()
api.retry_node(runtime=runtime, node_id="node_id", data={"key": "value"}).result
# True
```

<a id="toc_anchor" name="#18-retry_subprocess"></a>

## 1.8. retry_subprocess

```python
def retry_subprocess(runtime: EngineRuntimeInterface, node_id: str) -> EngineAPIResult:
    """
    重试进入失败的子流程节点

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 子流程节点 id
    :type node_id: str
    :return: [description]
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#181-example"></a>

### 1.8.1. example

```python
runtime = BambooDjangoRuntime()
api.retry_subprocess(runtime=runtime, node_id="node_id").result
# True
```

<a id="toc_anchor" name="#19-skip_node"></a>

## 1.9. skip_node

```python
def skip_node(runtime: EngineRuntimeInterface, node_id: str) -> EngineAPIResult:
    """
    跳过某个执行失败的节点（仅限 event，activity）

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 失败的节点 id
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#191-example"></a>

### 1.9.1. example

```python
runtime = BambooDjangoRuntime()
api.skip_node(runtime=runtime, node_id="node_id").result
# True
```

<a id="toc_anchor" name="#110-skip_exclusive_gateway"></a>

## 1.10. skip_exclusive_gateway

```python
def skip_exclusive_gateway(
    runtime: EngineRuntimeInterface, node_id: str, flow_id: str
) -> EngineAPIResult:
    """
    跳过某个执行失败的分支网关

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 失败的分支网关 id
    :type node_id: str
    :param flow_id: 需要往下执行的 flow id
    :type flow_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1101-example"></a>

### 1.10.1. example

```python
runtime = BambooDjangoRuntime()
api.skip_exclusive_gateway(runtime=runtime, node_id="node_id", flow_id="flow_id").result
# True
```

## 1.11. skip_conditional_parallel_gateway

```python
def skip_conditional_parallel_gateway(
    runtime: EngineRuntimeInterface, node_id: str, flow_ids: list, converge_gateway_id: str
) -> EngineAPIResult:
    """
    跳过执行失败的条件并行网关继续执行

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 失败的分支网关 id
    :type node_id: str
    :param flow_ids: 需要继续执行的流 ID 列表
    :type flow_ids: list
    :param converge_gateway_id: 目标汇聚网关 ID
    :type converge_gateway_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1121-example"></a>

### 1.12.1. example

```python
runtime = BambooDjangoRuntime()
api.skip_conditional_parallel_gateway(runtime=runtime, node_id="node_id", flow_id="flow_id").result
# True
```

<a id="toc_anchor" name="#112-forced_fail_activity"></a>

## 1.12. forced_fail_activity

```python
def forced_fail_activity(
    runtime: EngineRuntimeInterface, node_id: str, ex_data: str
) -> EngineAPIResult:
    """
    强制失败某个 activity 节点

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :param message: 异常信息
    :type message: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1131-example"></a>

### 1.13.1. example

```python
runtime = BambooDjangoRuntime()
api.forced_fail_activity(runtime=runtime, node_id="node_id", ex_data="forced fail by me").result
# True
```

<a id="toc_anchor" name="#113-callback"></a>

## 1.13. callback

```python
def callback(
    runtime: EngineRuntimeInterface, node_id: str, version: str, data: dict
) -> EngineAPIResult:
    """
    回调某个节点

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param version: 节点执行版本
    :param version: str
    :param data: 节点 ID
    :type data: dict
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1141-example"></a>

### 1.14.1. example

```python
runtime = BambooDjangoRuntime()
api.callback(runtime=runtime, node_id="node_id", version="version", data={"key": "value"}).result
# True
```

<a id="toc_anchor" name="#114-get_pipeline_states"></a>

## 1.14. get_pipeline_states

```python
def get_pipeline_states(
    runtime: EngineRuntimeInterface, root_id: str, flat_children=True
) -> EngineAPIResult:
    """
    返回某个任务的状态树

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param root_id: 根节点 ID
    :type root_id: str
    :param flat_children: 是否将所有子节点展开
    :type flat_children: bool
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1151-example"></a>

### 1.15.1. example

```python
runtime = BambooDjangoRuntime()
api.get_pipeline_states(runtime=runtime, root_id="pipeline_id").data

{'pc31c89e6b85a4e2c8c5db477978c1a57': {'id': 'pc31c89e6b85a4e2c8c5db477978c1a57', # 节点 ID
  'state': 'FINISHED', # 节点状态
  'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57', # 根流程 ID
  'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57', # 父流程 ID
  'version': 'vaf47e56f2f31401e979c3c47b2a0c285', # 状态版本
  'loop': 1, # 重入次数
  'retry': 0, # 重试次数
  'skip': False, # 是否被跳过
  'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
  'error_ignored': False, # 是否出错后自动跳过
  'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 688664, tzinfo=<UTC>), # 状态数据创建时间
  'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 688423, tzinfo=<UTC>), # 节点开始执行时间
  'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 775165, tzinfo=<UTC>), # 执行完成（成功或失败）时间
  'children': {'e42035b3f98374062921a191115fc602e': {'id': 'e42035b3f98374062921a191115fc602e',
    'state': 'FINISHED',
    'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'version': 've2d0fa10d7d842a1bcac25984620232a',
    'loop': 1,
    'retry': 0,
    'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
    'skip': False,
    'children': {},
    'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 744490, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 744308, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 746690, tzinfo=<UTC>)},
   'e327f83de42df4ebfab375c271bf63d29': {'id': 'e327f83de42df4ebfab375c271bf63d29',
    'state': 'FINISHED',
    'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'version': 'v893cdc14150d4df5b20f2db32ba142b3',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
    'children': {},
    'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 753321, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 753122, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 758697, tzinfo=<UTC>)},
   'e6c7d7a3721ca4b19a5a7f3b34d8387bf': {'id': 'e6c7d7a3721ca4b19a5a7f3b34d8387bf',
    'state': 'FINISHED',
    'root_id:': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'parent_id': 'pc31c89e6b85a4e2c8c5db477978c1a57',
    'version': 'v0c661ee6994d4eb4bdbfe5260f9a9f22',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
    'children': {},
    'created_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 767563, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 767384, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 3, 45, 54, 773341, tzinfo=<UTC>)}}}}
```

<a id="toc_anchor" name="#115-get_children_states"></a>

## 1.15. get_children_states

```python
def get_children_states(
    runtime: EngineRuntimeInterface, node_id: str
) -> EngineAPIResult:
    """
    返回某个节点及其所有子节点的状态

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 父流程 ID
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1161-example"></a>

### 1.16.1. example

```python
runtime = BambooDjangoRuntime()
api.get_children_states(runtime=runtime, node_id="pipeline_id").data


{'p07926dd8e81a4f0d9cd484d4856afd42': {'id': 'p07926dd8e81a4f0d9cd484d4856afd42',  # 节点 ID
  'state': 'FINISHED', # 节点状态
  'root_id:': 'p07926dd8e81a4f0d9cd484d4856afd42', # 根流程 ID
  'parent_id': 'p07926dd8e81a4f0d9cd484d4856afd42', # 父流程 ID
  'version': 'v512822ec7fbc4c3180bddb4a6e3f72ad', # 状态版本
  'loop': 1, # 重入次数
  'retry': 0, # 重试次数
  'skip': False, # 是否被跳过
  'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
  'created_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 725395, tzinfo=<UTC>), # 状态数据创建时间
  'started_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 725130, tzinfo=<UTC>), # 节点开始执行时间
  'archived_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 842400, tzinfo=<UTC>), # 执行完成（成功或失败）时间
  'children': {'e571501dfbf204e679347c4a74a4ad2ae': {'id': 'e571501dfbf204e679347c4a74a4ad2ae',
    'state': 'FINISHED',
    'root_id:': 'p07926dd8e81a4f0d9cd484d4856afd42',
    'parent_id': 'p07926dd8e81a4f0d9cd484d4856afd42',
    'version': 'vf72134b379224b5e95bd1b1c887b2b1e',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
    'created_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 806533, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 806038, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 809831, tzinfo=<UTC>)},
   'ea3e45c2685e148e9849e4a34e992a562': {'id': 'ea3e45c2685e148e9849e4a34e992a562',
    'state': 'FINISHED',
    'root_id:': 'p07926dd8e81a4f0d9cd484d4856afd42',
    'parent_id': 'p07926dd8e81a4f0d9cd484d4856afd42',
    'version': 'vbca6dd994806449bbfdfb372457189bc',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
    'created_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 817497, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 817295, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 823874, tzinfo=<UTC>)},
   'efdb8de56dec5419baa0c68ae9af6a671': {'id': 'efdb8de56dec5419baa0c68ae9af6a671',
    'state': 'FINISHED',
    'root_id:': 'p07926dd8e81a4f0d9cd484d4856afd42',
    'parent_id': 'p07926dd8e81a4f0d9cd484d4856afd42',
    'version': 'v957e052ef10d4d14b3fc039893ec70ae',
    'loop': 1,
    'retry': 0,
    'skip': False,
    'error_ignorable': False, # 是否出错后自动跳过（老版本 API 兼容字段）
    'error_ignored': False, # 是否出错后自动跳过
    'created_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 834135, tzinfo=<UTC>),
    'started_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 833957, tzinfo=<UTC>),
    'archived_time': datetime.datetime(2021, 3, 10, 11, 5, 22, 840337, tzinfo=<UTC>)}}}}
```

<a id="toc_anchor" name="#116-get_execution_data_inputs"></a>

## 1.16. get_execution_data_inputs

```python
def get_execution_data_inputs(
    runtime: EngineRuntimeInterface, node_id: str
) -> EngineAPIResult:
    """
    获取某个节点执行数据的输入数据

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1171-example"></a>

### 1.17.1. example

```python
runtime = BambooDjangoRuntime()
api.get_execution_data_inputs(runtime=runtime, node_id="node_id").data

{'_loop': 1}
```

<a id="toc_anchor" name="#117-get_execution_data_outputs"></a>

## 1.17. get_execution_data_outputs

```python
def get_execution_data_outputs(
    runtime: EngineRuntimeInterface, node_id: str
) -> EngineAPIResult:
    """
    获取某个节点的执行数据输出

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1181-example"></a>

### 1.18.1. example

```python
runtime = BambooDjangoRuntime()
api.get_execution_data_outputs(runtime=runtime, node_id="node_id").data

{}
```

<a id="toc_anchor" name="#118-get_execution_data"></a>

## 1.18. get_execution_data

```python
def get_execution_data(
    runtime: EngineRuntimeInterface, node_id: str
) -> EngineAPIResult:
    """
    获取某个节点的执行数据

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1181-example"></a>

### 1.19.1. example

```python
runtime = BambooDjangoRuntime()
api.get_execution_data(runtime=runtime, node_id="node_id").data

{'inputs': {'_loop': 1}, 'outputs': {}}
```

<a id="toc_anchor" name="#119-get_data"></a>

## 1.19. get_data

```python
def get_data(runtime: EngineRuntimeInterface, node_id: str) -> EngineAPIResult:
    """
    获取某个节点的原始输入数据

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```
<a id="toc_anchor" name="#1191-example"></a>

### 1.20.1. example

```python
runtime = BambooDjangoRuntime()
api.get_data(runtime=runtime, node_id="node_id").data

{'inputs': {'_loop': 1}, 'outputs': {}}
```

<a id="toc_anchor" name="#120-get_node_histories"></a>

## 1.20. get_node_histories

> 注意，只有进行过重试、跳过、重入的节点才会记录执行历史

```python
def get_node_histories(
    runtime: EngineRuntimeInterface, node_id: str, loop: int = -1
) -> EngineAPIResult:
    """
    获取某个节点的历史记录概览

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :param loop: 重入次数, -1 表示不过滤重入次数
    :type loop: int, optional
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1211-example"></a>

### 1.21.1. example

```python
runtime = BambooDjangoRuntime()
api.get_node_histories(runtime=runtime, node_id="node_id").data


[
    {
        "id": 1, # 历史 ID
        "node_id": "e34ef61258b134ffaae42efee2ab9ff1b", # 节点 ID
        "started_time": datetime.datetime(2021, 3, 10, 11, 10, 9, 350028, tzinfo=<UTC>), # 节点开始执行时间
        "archived_time": datetime.datetime(2021, 3, 10, 11, 10, 9, 352609, tzinfo=<UTC>), # 执行完成（成功或失败）时间
        "loop": 1, # 重入次数
        "skip": False, # 是否被跳过
        "version": "vg4ef61258b134ffaae42efee2ab9ff1b", # 状态版本
        "inputs": {}, # 输入执行数据
        "outputs": {}, # 输出执行数据
    }
]
```

<a id="toc_anchor" name="#121-get_node_short_histories"></a>

## 1.21. get_node_short_histories

> 注意，只有进行过重试、跳过、重入的节点才会记录执行历史

```python
def get_node_short_histories(
    runtime: EngineRuntimeInterface, node_id: str, loop: int = -1
) -> EngineAPIResult:
    """
    获取某个节点的简要历史记录

    :param runtime: 引擎运行时实例
    :type runtime: EngineRuntimeInterface
    :param node_id: 节点 ID
    :type node_id: str
    :param loop: 重入次数, -1 表示不过滤重入次数
    :type loop: int, optional
    :return: 执行结果
    :rtype: EngineAPIResult
    """
```

<a id="toc_anchor" name="#1211-example"></a>

### 1.21.1. example

```python
runtime = BambooDjangoRuntime()
api.get_node_histories(runtime=runtime, node_id="node_id").data


[
    {
        "id": 1, # 历史 ID
        "node_id": "e34ef61258b134ffaae42efee2ab9ff1b", # 节点 ID
        "started_time": datetime.datetime(2021, 3, 10, 11, 10, 9, 350028, tzinfo=<UTC>), # 节点开始执行时间
        "archived_time": datetime.datetime(2021, 3, 10, 11, 10, 9, 352609, tzinfo=<UTC>), # 执行完成（成功或失败）时间
        "loop": 1, # 重入次数
        "skip": False, # 是否被跳过
        "version": "vg4ef61258b134ffaae42efee2ab9ff1b", # 状态版本
    }
]
```