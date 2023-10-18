### 功能介绍:


## 回滚配置

### 开启配置项

在开始体验回滚之前，我们需要在django_settings 中开启以下的配置:

```python
PIPELINE_ENABLE_ROLLBACK = True  
ROLLBACK_QUEUE = "default_test"  
PIPELINE_ENABLE_AUTO_EXECUTE_WHEN_ROLL_BACKED = False
```

其中：
- PIPELINE_ENABLE_ROLLBACK 表示开启回滚
- ROLLBACK_QUEUE: 表示回滚所使用的队列
- PIPELINE_ENABLE_AUTO_EXECUTE_WHEN_ROLL_BACKED: 是否开启回滚后自动开始，开启时，回滚到目标节点将会自动开始，未开启时流程回到目标节点将会暂停。

### Install App
之后需要在 `INSTALLED_APPS` 增加配置:
```python
INSTALLED_APPS += (  
	"pipeline.contrib.rollback", 
)
```

### 执行 migrate 操作
```bash
python manage.py migrate rollback
```

之后回滚的一切便已经就绪了。

## 回滚的边界条件

### Token 模式:


现阶段的回滚的行为受到严格限制，在TOKEN 模式下，回滚将不能随意的指向某个节点。流程回滚时将沿着原路径依次回滚(如果存在子流程，则先回滚子流程，再继续主流程的回滚)。
在流程回滚时, 节点的状态机如下:

![rollback.png](..%2Fassets%2Fimg%2Frollback%2Frollback.png)

以下是回滚的各项边界条件：

#### 任务状态

只有处于 `RUNNING` 和 `ROLL_BACK_FAILED` 状态的任务才允许回滚。当任务处于结束，暂停时，将不允许回滚。

#### 任务节点

在 token 模式下，**回滚的起始和目标节点的token须保持一致**。同时不允许同 token下 **存在正在运行的节点**。

##### 回滚的起点

- 回滚开始的节点的状态只支持`FINISHED` 或 `FAILED`, 正在运行的节点将不允许回滚。
- 回滚开始的节点必须是流程当前正在运行的节点之一，也就是流程的末端节点。

##### 回滚的目标节点

- 回滚的目标节点只支持`FINISHED` 状态，回滚的目标节点只支持任务类型的节点，网关节点不支持回滚。

#### 回滚预约
- 回滚预约只能预约为RUNNING状态的节点，当该节点结束时，将自动开始回滚。
- **一个流程同时只能有一个预约回滚的任务**


### ANY 模式:

当为ANY 模式的回滚时，流程可以从任何地方开始，回滚到之前的任意节点上去，此时流程**将不会按照路径调用回滚(不会调用节点的rollback方法)**，而是直接回到目标节点，并删除回滚路径上已经执行过的节点信息，从目标位置开始。

#### 任务状态

只有处于 `RUNNING` 的任务才允许回滚。当任务处于结束，暂停时，将不允许回滚。

#### 任务节点

在 any 模式下，回滚的边界条件将少得多，由于 any 状态下的回滚将直接回到目标节点并开始，类似于任务的任意节点跳转。

在 any 模式下，回滚开始前**不允许当前流程存在处于 running 状态的节点。**

##### 回滚的起点

- 回滚开始的节点必须是流程当前正在运行的节点，也就是流程的末端节点。
- -回滚开始的节点的状态只支持`FINISHED` 或 `FAILED`, 正在运行的节点将不再允许回滚。

##### 回滚的目标节点

- 回滚的目标节点只支持`FINISHED` 状态，回滚的目标节点只支持任务节点类型。

#### 回滚预约
- 回滚预约只能预约为running状态的节点，当该节点结束时，将自动开始回滚。
- **一个流程同时只能有一个预约回滚的任务**

#### 回滚的使用:

``` python
from pipeline.contrib.rollback import api


# 节点回滚，其中mode 有 TOKEN 和 ANY 两种模式可选
api.rollback(root_pipeline_id, start_node_id, target_node_id, mode="TOKEN")

# 回滚预约
api.reserve_rollback(root_pipeline_id, start_node_id, target_node_id, mode="TOKEN")

# 取消回滚预约
api.cancel_reserved_rollback(root_pipeline_id, start_node_id, target_node_id, mode="TOKEN")


# 获取本次回滚支持的范围
api.get_allowed_rollback_node_id_list(root_pipeline_id, start_node_id, mode="TOKEN")

```
