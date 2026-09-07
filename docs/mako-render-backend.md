# Mako subprocess 渲染后端

默认仍为 `inprocess`。宿主需在首次获取后端前配置 `bamboo_engine.config.Settings`，或显式调用 `set_render_backend`。此库不会自动读取同名环境变量或 Django settings。

| 配置 | 默认值 | 行为 |
| --- | --- | --- |
| `MAKO_RENDER_BACKEND` | `inprocess` | `subprocess` 启用子进程后端 |
| `MAKO_RENDER_POOL_SIZE` | 4 | 同时占用的槽位及监督线程上限 |
| `MAKO_RENDER_MAX_USES` | 500 | 每个 worker 的复用次数；达到后回收，下次请求再创建 |
| `MAKO_RENDER_TIMEOUT` | 30 秒 | 排队、准备、启动、握手、发送、渲染和接收共享的时间预算 |
| `MAKO_RENDER_FALLBACK_INPROCESS` | False | 仅主进程确认 context/spec 不可移植时，允许显式兼容回退 |
| `MAKO_RENDER_NO_NETWORK` | True | 必须成功创建 Linux network namespace，否则不发送业务 context、不渲染 |
| `MAKO_RENDER_OS_HARDEN` | True | Linux core/CPU/地址空间的资源限制，与无网络要求分别生效 |
| `MAKO_RENDER_RLIMIT_CPU` | 30 秒 | worker 累计 CPU 时间上限（并非每次请求重置） |
| `MAKO_RENDER_RLIMIT_AS_MB` | 1024 MB | worker 地址空间上限 |

使用示例（测试环境显式允许联网；不代表已建立无网络边界）：

```python
from bamboo_engine.template.render_backend import SubprocessPoolRenderBackend, set_render_backend

set_render_backend(SubprocessPoolRenderBackend(pool_size=2, timeout=10, no_network=False))
```

## 故障行为

- 默认返回原始模板字符串，与既有渲染失败行为一致。
- 无 spec 同样服从 strict 配置。网络隔离失败、启动失败、通信异常、协议损坏、超时均不触发进程内回退。
- 时间预算覆盖阻塞的进程启动：每个槽位由一个持久监督线程负责。调用超时可先返回；尚未结束的启动仍占用原槽位，启动完成后回收，避免不断创建后台启动线程。所有槽位占满时，后续调用在预算内返回。
- 成功结果先返回，回收不再同步创建替代 worker。启动失败后保留槽位，下一次调用可以重试。
- POSIX 上使用独立 Python 解释器，可由 daemon/prefork 宿主启动；不重新导入宿主 `__main__`。fork 后重建本地池，只关闭继承的父进程连接副本。
- 回收使用独立进程组强杀；Linux worker 设置父线程死亡信号。监督线程与 worker 生命周期一致。宿主正常退出或关闭后端会回收 worker。

## Context 契约

请求来自受信任的服务端对象构造过程，以单向 pickle 发送。**这不是接收外部 pickle 的接口，也不能把任意不可信 Python 对象当作安全输入。**模板必须是普通字符串，spec 仅允许已知 flavor 和字符串配置，context 顶层键必须为普通字符串。

普通标量与容器递归保留；显式保留 `time.struct_time`、`Counter`、`Decimal`、日期/时间等支持类型。包含 property、公共方法或继承行为的未知对象、未知容器子类（包括自定义 namedtuple）会被明确判为不支持；不会先降级为 tuple/dict/属性包后再静默渲染错误。仅没有上述行为的结构化属性包转换为 `PortableRenderObject`，保留实例属性和受信任对象的字符串表示。受信任宿主注入的可导入函数可按引用传输，其模块可能加载应用代码。

对象图最多 8 层、100000 个元素、累计 8 MiB 字符/字节内容，整数最多 4096 bit；拒绝环。请求/回复帧分别最多 8 MiB（包括编码开销）。超出支持范围需要按日志回归，不能据此声称开启 subprocess 对所有历史 Python 对象语义均无影响。

worker 回复采用版本、请求 ID、状态和字符串结果组成的受限 JSON，主进程不反序列化 worker pickle。接收前校验帧长度，并校验字段类型、数字、版本和请求 ID；损坏回复会销毁 worker。

显式 `fallback_inprocess=True` 会让不支持的数据重新进入宿主渲染，只适合受信任兼容验证；回退本身不具备隔离后端的资源或安全保证。保持默认 strict 可以避免这条自动回退路径。

## 隔离边界与验证范围

解释器启动前应用环境变量白名单、关闭无关文件描述符并禁用 site 启动钩子。无网络要求在非 Linux 或权限不足（例如 EPERM）时失败关闭。启用 Linux 资源限制时，同时降低 soft/hard 上限。

该后端**不等同于无凭证容器沙箱**：仍共享宿主身份/文件系统，context、导入模块、挂载文件和路径型 Unix socket 可能暴露资源。Python 导入路径与模块配置必须由宿主信任。进程组不约束恶意主动脱组的后代，仍需部署层权限、文件系统、cgroup 等隔离。warm worker 复用也不提供不同请求间的强隔离；已被攻破的进程可能保留状态。`max_uses=1` 可关闭请求间复用，但不替代上述部署层隔离。

本地库级测试不能代替目标 Linux 容器权限检查、Celery 部署验证及业务流程回归。
