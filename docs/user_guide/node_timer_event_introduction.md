# 增强包 - 节点计时器边界事件

## 特性

- 支持节点边界事件扫描与处理
- 支持自定义节点计时器边界事件处理方式
- 支持自定义节点计时器边界事件相关消息队列

## 启动配置

0. 该功能依赖 `mq`、`Redis` 和 `DB` 三个服务，需要在启动时保证这三个服务已经启动。
1. 在 Django 项目配置文件的 INSTALLED_APPS 中添加 `pipeline.contrib.node_timer_event` 应用。
2. 执行 `python manage.py migrate` 命令，创建数据库表。
3. 启动计时器到期扫描进程，执行 `python manage.py start_node_timer_event_process` 命令。
4. 启动对应的 worker 进程，执行 `python manage.py celery worker -l info -c 4` 命令。

## 接口

目前，pipeline.contrib.node_timer_event 模块提供了以下接口或扩展：

1. Action

   SDK 内置了两个 Action 提供「节点超时」处理能力
    - `bamboo_engine_forced_fail`: 节点超时强制失败
    - `bamboo_engine_forced_fail_and_skip`: 节点超时强制失败并跳过

   SDK 也提供了比较友好的自定义 Action 扩展和接入能力，用于定义业务层计时器边界事件的处理动作，例如定义一个名为 `example`
   的 Action

   ```python
   import logging
   
   from pipeline.core.data.base import DataObject
   from pipeline.contrib.node_timer_event.handlers import BaseAction
   
   logger = logging.getLogger(__name__)
   
   class ExampleAction(BaseAction):
   def do(self, data: DataObject, parent_data: DataObject, *args, **kwargs) -> bool:
       logger.info("[Action] example do: data -> %s, parent_data -> %s", data, parent_data)
       return True
   
   class Meta:
       action_name = "example"

   ```

2. apply_node_timer_event_configs
   该接口用于在 pipeline_tree 中应用节点计时器边界事件，接口定义如下：
    ```python
   def apply_node_timer_event_configs(pipeline_tree: dict, configs: dict):
       """
       在 pipeline_tree 中应用节点时间事件配置
       :param pipeline_tree: pipeline_tree
       :param configs: 节点时间时间配置
       """
    ```
   例如，创建一个节点运行 10 min 后启动的计时器边界事件，事件处理动作为步骤 1. 定义的 `example` 的计时器边界事件配置，可以这样写：
    ```python
    pipeline_tree = {}  # 此处省略 pipeline_tree 的创建过程
    configs = {"node_id": [{"enable": True, "action": "example", "timer_type": "time_duration", "defined": "PT10M"}]}
    new_pipeline_tree = apply_node_timer_event_configs(pipeline_tree, configs)
    ```

   节点计时器边界事件配置中
    - enable 代表是否启用该节点的计时器事件配置
    - action 表示计时器触发时执行的动作
    - defined 代表计时器定义
    - timer_type 表示计时器类型
    - defined & timer_type 更多配置方式，请参考文末「附录」

3. batch_create_node_timeout_config
   该接口用于批量创建节点计时器边界事件，接口定义如下：
    ```python
   def batch_create_node_timer_event_config(root_pipeline_id: str, pipeline_tree: dict):
       """
       批量创建节点计时器边界事件配置
       :param root_pipeline_id: pipeline root ID
       :param pipeline_tree: pipeline_tree
       :return: 节点计时器边界事件配置数据插入结果
       """
    ```
   插入结果示例:
    ``` python
    {
        "result": True, # 是否操作成功, True 时关注 data，False 时关注 message
        "data": [...], # NodeTimerEventConfig Model objects 
        "message": ""
    }
    ```

## 自定义

节点计时器边界事件模块的自定义配置 Django Settings 来实现，配置项和默认值如下：

``` python
from pipeline.contrib.node_timer_event.handlers import node_timeout_handler

PIPELINE_NODE_TIMER_EVENT_KEY_PREFIX = "bamboo:v1:node_timer_event"  # Redis key 前缀，用于记录正在执行的节点，命名示例: {app_code}:{app_env}:{module}:node_timer_event
PIPELINE_NODE_TIMER_EVENT_HANDLE_QUEUE = None  # 节点计时器边界事件处理队列名称, 用于处理计时器边界事件， 需要 worker 接收该队列消息，默认为 None，即使用 celery 默认队列
PIPELINE_NODE_TIMER_EVENT_DISPATCH_QUEUE = None  # 节点计时器边界事件分发队列名称, 用于记录计时器边界事件， 需要 worker 接收该队列消息，默认为 None，即使用 celery 默认队列
PIPELINE_NODE_TIMER_EVENT_EXECUTING_POOL = "bamboo:v1:node_timer_event:executing_node_pool"  # 执行节点池名称，用于记录正在执行的节点，需要保证 Redis key 唯一，命名示例: {app_code}:{app_env}:{module}:executing_node_pool
PIPELINE_NODE_TIMER_EVENT_POOL_SCAN_INTERVAL = 1   # 节点池扫描间隔，间隔越小，边界事件触发时间越精准，相应的事件处理的 workload 负载也会提升，默认为 1 s
PIPELINE_NODE_TIMER_EVENT_MAX_EXPIRE_TIME = 60 * 60 * 24 * 15   # 最长过期时间，兜底删除 Redis 冗余数据，默认为 15 Days，请根据业务场景调整
PIPELINE_NODE_TIMER_EVENT_ADAPTER_CLASS = "pipeline.contrib.node_timer_event.adapter.NodeTimerEventAdapter" # 边界事件处理适配器，默认为 `pipeline.contrib.node_timer_event.adapter.NodeTimerEventAdapter`
```

## 使用样例

假设当前开发者已经准备好了对应的 pipeline_tree 和对应的节点计时器边界事件配置，那么在进行项目配置并启动对应的进程后，可以按照以下步骤进行处理：

1. 调用 apply_node_timer_event_configs 接口，将节点计时器边界事件配置应用到 pipeline_tree 中
2. 调用 batch_create_node_timeout_config 接口，将节点计时器边界事件配置插入到数据库中
3. 启动 pipeline 运行，等待动计时器到期扫描进程处理到期边界事件，验证时请确认节点执行完成时间大于设置的计时器到期时间
4. 查看节点计时器边界事件处理结果是否符合预期

## 附录

### 支持的计时器定义

| 计时器类型               | 配置值             | 描述                                                                   | `defined` 样例                                                                                                                                       | 备注                                                                                                               |
|---------------------|-----------------|----------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| 时间日期（Time date）     | `time_date`     | ISO 8601 组合日期和时间格式                                                   | `2019-10-01T12:00:00Z` - UTC 时间<br />`2019-10-02T08:09:40+02:00` - UTC 加上两小时时区偏移<br />`2019-10-02T08:09:40+02:00[Europe/Berlin]` - UTC 加上柏林两小时时区偏移 |                                                                                                                  |
| 持续时间（Time duration） | `time_duration` | ISO 8601 持续时间格式，模式：`P(n)Y(n)M(n)DT(n)H(n)M(n)S`                      | `PT15S` - 15 秒<br />`PT1H30M` - 1 小时 30 分钟<br /> `P14D` - 14 天<br />`P14DT1H30M` - 14 天 1 小时 30 分钟                                                 | `P` - 持续事件标识<br />`Y` - 年<br />`M` - 月<br />`D` - 天<br />`T` - 时间分量开始标识<br />`H` - 小时<br />`M` - 分钟<br />`S` - 秒 |
| 时间周期（Time cycle）    | `time_cycle`    | ISO 8601 重复间隔格式，包含重复次数模式：`R(n)` 及持续时间模式：`P(n)Y(n)M(n)DT(n)H(n)M(n)S` | `R5/PT10S` - 每10秒一次，最多五次<br />`R1/P1D` - 每天一次，最多一次                                                                                                 |                                                                                                                  |