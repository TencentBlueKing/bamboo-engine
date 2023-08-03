# 增强包 - 节点超时功能

## 特性
- 支持节点超时扫描与处理
- 支持自定义节点超时时间 
- 支持自定义节点超时处理方式
- 支持自定义节点超时相关消息队列

## 启动配置
0. 该功能依赖 mq、Redis 和 DB 三个服务，需要在启动时保证这三个服务已经启动。
1. 在 Django 项目配置文件的 INSTALLED_APPS 中添加 `pipeline.contrib.node_timeout` 应用。
2. 执行 `python manage.py migrate` 命令，创建数据库表。
3. 启动任务节点超时扫描进程，执行 `python manage.py start_node_timeout_process` 命令。
4. 启动对应的 worker 进程，执行 `python manage.py celery worker -l info -c 4` 命令。

## 接口
目前，pipeline.contrib.node_timeout 模块提供了以下接口：

1. apply_node_timout_configs
    该接口用于在 pipeline_tree 中应用节点超时配置，接口定义如下：
    ```python
    def apply_node_timout_configs(pipeline_tree: dict, configs: dict):
        """
        在 pipeline_tree 中应用节点超时配置
        :param pipeline_tree: pipeline_tree
        :param configs: 节点超时配置
        :return: 插入了节点超时配置的新 pipeline_tree
        """
    ```
    例如，创建一个超时时间为 10 分钟，超时处理方式为强制失败节点的超时配置，可以这样写：
    ```python
    pipeline_tree = {}  # 此处省略 pipeline_tree 的创建过程
    configs = {"node_id": {"enable": True, "action": "forced_fail", "seconds": 10}}
    new_pipeline_tree = apply_node_timout_configs(pipeline_tree, configs)
    ```

    超时配置中
    - enable 代表是否启用该节点的超时配置
    - action 代表超时处理方式，默认支持的处理方式有：forced_fail (强制失败)、forced_fail_and_skip (强制失败并跳过)
    - seconds 代表超时时间，单位为秒

2. batch_create_node_timeout_config
    该接口用于批量创建节点超时配置，接口定义如下：
    ```python
    def batch_create_node_timeout_config(root_pipeline_id: str, pipeline_tree: dict):
        """
        批量创建节点超时配置
        :param root_pipeline_id: pipeline root ID
        :param pipeline_tree: pipeline_tree
        :return: 节点超时配置数据插入结果
        """
    ```
    插入结果示例:
    ``` python
    {
        "result": True, # 是否操作成功, True 时关注 data，False 时关注 message
        "data": [...], # TimeoutNodeConfig Model objects 
        "message": ""
    }
    ```

## 自定义
节点超时自定义通过配置 Django Settings 来实现，配置项和默认值如下：

``` python
from pipeline.contrib.node_timeout.handlers import node_timeout_handler

PIPELINE_NODE_TIMEOUT_HANDLER = node_timeout_handler  # 节点超时处理器配置字典，key 为对应的配置 action，value 为对应的处理器，需继承 NodeTimeoutStrategy 并实现接口
PIPELINE_NODE_TIMEOUT_HANDLE_QUEUE = None  # 节点超时处理队列名称, 用于处理超时节点， 需要 worker 接收该队列消息，默认为 None，即使用 celery 默认队列
PIPELINE_NODE_TIMEOUT_DISPATCH_QUEUE = None  # 节点超时记录分发队列名称, 用于记录超时节点， 需要 worker 接收该队列消息，默认为 None，即使用 celery 默认队列
PIPELINE_NODE_TIMEOUT_EXECUTING_POOL = "executing_node_pool"  # 执行节点池名称，用于记录正在执行的节点，需要保证 Redis key 唯一
```

## 使用样例
假设当前开发者已经准备好了对应的 pipeline_tree 和对应的超时配置，那么在进行项目配置并启动对应的进程后，可以按照以下步骤进行处理：
1. 调用 apply_node_timout_configs 接口，将超时配置应用到 pipeline_tree 中
2. 调用 batch_create_node_timeout_config 接口，将超时配置插入到数据库中
3. 启动 pipeline 运行，等待超时处理进程处理超时节点，验证时请确认节点执行时间大于超时时间
4. 查看超时处理结果是否符合预期