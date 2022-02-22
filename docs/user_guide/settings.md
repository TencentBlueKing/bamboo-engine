<!-- TOC -->

- [设置引擎日志的有效期](#设置引擎日志的有效期)

<!-- /TOC -->

## 设置引擎日志的有效期
周期任务每天执行一次清理过期的引擎日志，引擎日志的有效期默认为30天
如需修改，请在`settings.py`中添加`LOG_PERSISTENT_DAYS`配置引擎日志的有效期
```python
LOG_PERSISTENT_DAYS = 1
```