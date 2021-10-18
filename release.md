## 1.5.1

- bugfix:
  - boorule multi threads context error fix

## 1.5.0

- feature:
  - (eri 5.0) 增加 skip_conditional_parallel_gateway API，支持对条件并行网关失败的网关节点进行跳过

## 1.4.0

- feature:
  - [(eri 4.0)](https://github.com/TencentBlueKing/bamboo-engine/pull/12/commits/8c882b7e84c7c743b0f49e0bb3ed01866346ea73)
    - task 模块 execute 方法增加 root_pipeline_id，parent_pipeline_id 参数
    - process 模块增加 get_sleep_process_info_with_current_node_id 接口
    - process 模块移除 get_sleep_process_with_current_node_id 接口
- optimization:
  - 优化 execute 事件中异常处理的逻辑

## 1.3.2

- optimization:
  - 对无效的 schedule 请求增加防御机制, 防止受到单个节点 schedule 请求风暴的影响

## 1.3.1
- bugfix:
  - 修复preview_node_inputs查看子流程节点数据失败问题

## 1.3.0

- feature:
  - （eri 3.0）增加 retry_subprocess API，支持对进入失败的子流程进行重试

## 1.2.1

- bugfix:
  - 修复engine执行过程异常时，`process_info` 未声明导致的问题
    
## 1.2.0

- feature:
  - (eri 2.1) API 增加 get_data 接口
- optimization:
  - 优化引擎在 context.hydrate 时的异常处理逻辑
- bugfix:
  - 修复 Settings.MAKO_SANDBOX_IMPORT_MODULES 无法导入多层级模块的问题
  - 修复子流程节点没有输出 `_inner_loop` 字段的问题
## 1.1.9

- feature:
  - (eri 2.0)引擎添加 inner_loop 记录当前流程循环次数功能
  - 添加 bamboo_engine.api.preview_node_inputs

## 1.1.8

- bugfix:
  - 修复 service_activity 节点执行后 outputs 中没有 _loop 的问题

## 1.1.7

- improvement:
  - 变量预渲染放在流程开始节点，支持变量引用情况

## 1.1.6

- feature: 
  - engine run_pipeline API 支持配置子流程预置上下文
  - eri version bump to 1.0.0
