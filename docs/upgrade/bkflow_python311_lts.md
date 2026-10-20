# BKFlow 使用 4.0 LTS 的兼容性补齐

## 变更来源

BKFlow `75879886d914bc91bbefac411d703eeadb11cc94` 使用
`bamboo-pipeline==3.29.11rc1` / `bamboo-engine==2.11.5rc1`。
直接切换到原版 pipeline 4.0.5 / engine 3.0.6 时，接口模块会因缺少 `SubCanvas`
无法启动，现有节点循环、重试和跳过接口也无法保持原有行为。

本次以 `bamboo_pipeline_4.0_lts@c52fdd5311436ca2c94c0ebda78f8e0b94b2bbda` 为基础，
从 `bamboo-pipeline-v3.29.11rc1` 对应提交
`4161e8069de52ffd6e5124edcfdafa49eea8cbd0` 回移业务实现和回归测试：

- 子画布节点的构建、校验、解析、处理器及运行时上下文接口。
- 节点循环状态、循环变量与输出、循环失败重试和跳过。
- 扫描水位、回调和消息特征诊断、恢复记录，以及执行和调度消息的过期检查。
- 两套 Mako 表达式入口的安全修复与回归测试。

保留 4.0 LTS 的 Python 3.11、Django 4.2 依赖边界及已有迁移历史，
将回移代码中的旧翻译和字符转换接口适配为 Django 4.2 支持的接口。
核心接口中的新增可选能力提供默认实现，具体运行时实现位于 bamboo-pipeline。

## 数据库与默认行为

对于已经使用原版 4.0 LTS、且启用了 `pipeline.contrib.diagnostics` 的应用，
本次新增 `0002_diagnosticscancursor` 和 `0003_diagnosticrecovery`，
分别创建扫描水位表和恢复记录表，应在使用相应能力前正常执行迁移。
没有修改初始迁移，也没有批量转换流程实例、执行上下文或队列消息。

新增窗口扫描、消息特征扫描、回调扫描、恢复执行及 fence 开关默认关闭，
恢复模式默认 `preview`。原有诊断功能的开关默认值保持不变。
默认关闭这些能力不代表可以跳过已安装应用的数据库迁移。

BKFlow 本次升级的旧基线 3.29.11rc1 已经包含上述两条诊断迁移。
该应用组合实际只需增加 Celery Beat 0016–0019 的迁移记录；
这四条迁移在本地 MySQL 8.0.46 上生成的 SQL 均为 no-op。
该结果不能推广为所有 4.0 LTS 使用方都没有新增表。

## 2026-10-20 本地验证

验证环境为 Python 3.11.10、Django 4.2.30、Celery 5.3.6、
MySQL 8.0.46、Redis 7.2.5 和 RabbitMQ 4.3.6。
旧应用运行于 Python 3.9.12、Django 3.2.25、Celery 5.2.3。
应用切换演练包含对应的 BKFlow 适配，不能只替换引擎包后复用该结论。

| 验证项 | 结果 |
| --- | --- |
| bamboo-engine 核心测试 | 697 passed，1 skipped |
| pipeline 运行时及诊断测试 | 980 passed |
| BKFlow 引擎与 plugin_service 测试 | 694 passed，1 skipped |
| BKFlow 接口、插件等测试，包含内部 SDK | 2240 passed，1 skipped |
| 修改文件格式、静态检查和依赖一致性 | 通过 |
| 回调、定时、失败重试、未消费任务的旧 → 新及新 → 旧切换 | 通过 |
| 子画布两轮循环，等待回调期间双向切换 | 通过 |
| 新旧 worker 共用队列同时运行 | 40 个任务全部完成，双方各完成 20 个 |

切换使用真实 threads worker、共享的专用本地数据库和消息队列。
worker 收到 TERM 后正常退出；回滚保留升级后的数据库，没有还原数据或逆向迁移。
周期任务验证覆盖持久化配置的双向读取，没有运行 Beat 的实际周期触发。
空间变量及子任务事件接口使用本地夹具，未验证真实外部平台调用。
本地 RabbitMQ 单独开启了 `transient_nonexcl_queues` 兼容选项。

## 合入与发布

本地验证包使用 `bamboo-engine==3.0.6+bkflow.1` 和
`bamboo-pipeline==4.0.5+bkflow.1`，仅用于区分实验构建，未发布到远程包仓库。
本 PR 只交付源码与测试，不提交该本地版本后缀，不创建发行 tag。
正式发行时需分配新的版本号，先发布 engine，再更新 pipeline 的精确依赖和锁文件并发布 pipeline。
BKFlow 随后更新正式依赖引用，在目标环境完成灰度验证。
