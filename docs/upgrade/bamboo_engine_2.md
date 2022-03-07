
## 升级到 2.x 版本

在 2.X 版本中，引擎对外暴露的 API 接口没有变化，只对引擎运行时接口进行了[调整](https://github.com/TencentBlueKing/bamboo-engine/pull/52/files#diff-7e7d71f69842dc771bf9fe729e858cccd95fcf73e6a16178d047f61ab8ca25b0)：

### 移除

现在引擎运行时不需要再实现以下接口

- Service.pre_execute
- Task.start_timeout_monitor
- Task.stop_timeout_monitor
