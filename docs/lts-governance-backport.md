# 3.29 LTS 流程卡住治理同步说明

本分支把 3.24 LTS 已验证的流程卡住治理能力完整同步到 `bamboo_pipeline_3.29_lts`，供当前依赖 bamboo-pipeline 3.29.x、bamboo-engine 2.11.x 的应用接入。功能开关保持关闭或只读默认值，升级包本身不会自动启动扫描、拦截或重放。

## 同步范围

### 诊断底座

- 登记卡住案例、保存证据和审计记录，提供诊断页面及管理命令。
- 排除正常暂停、冻结、失败等待人工处理、等待外部回调和正常网关汇聚。
- 子进程完成通知按 `dead=False` 原子去重；调度锁内重新读取回调状态，避免并发回调覆盖结果。
- 单次回调锁冲突重试由服务的 `callback_lock_retryable` 显式允许，默认关闭。

### P3-1：检测全覆盖

- 回调扫描：发现回调已落库、后续调度消息未处理的 S4。
- 丢失类型扫描：按进程最后活动时间检查 S1、S2、S3、S5、S6。
- 无动静兜底扫描：按检查进度覆盖所有跨过 1 小时、24 小时阈值的根流程。
- 三个扫描器分别由 `PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED`、`PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED`、`PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED` 打开，默认均为 `False`。

### P3-2：防重复检查（设计里叫门禁）

- 正常执行和轮询消息可带上预期状态：执行消息记录节点及状态版本，轮询消息记录调度次数。
- 引擎入口发现预期状态不符时，可只记录 `would be dropped`，也可真正丢弃重复或过期消息。
- `FENCE_EMIT_ENABLED`、`FENCE_ENFORCE` 默认均为 `False`；接入方必须先完成全量 worker 升级，再依次打开消息携带预期状态和拦截。

### P3-3：人工重放与重放记录

- 根据数据库最新状态重新推导丢失消息，不复用登记时的旧证据。
- 支持 S1～S6 人工预览和重放；执行、轮询消息重放前要求防重复检查已经生效。
- 每次尝试写入 `DiagnosticRecovery` 重放记录，默认 180 秒后回查结果。
- `PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED`、`PIPELINE_DIAGNOSTICS_APPLY_ENABLED` 默认均为 `False`。

### P3-4：自动重放

- 仅当模式为 `apply`、案例类型在 `PIPELINE_DIAGNOSTICS_AUTO_REPLAY_TYPES` 中、范围解析函数允许当前根流程时自动重放。
- 同一卡点默认最多自动重放 3 次，每轮最多 20 个。
- 最近 5 分钟新登记的可重放案例超过 50 个时自动暂停，本轮只预览并记录指标。
- `PIPELINE_DIAGNOSTICS_RECOVERY_MODE` 默认 `preview`，自动重放类型和范围解析函数默认留空。

## 接入要求

接入应用还需要完成下列工作，不能只升级 Python 包：

1. 注册 `pipeline.contrib.diagnostics` 并执行 0001～0003 迁移。
2. 配置三个扫描任务和恢复任务的周期调用入口。
3. 提供 `PIPELINE_DIAGNOSTICS_RECOVERY_SCOPE_RESOLVER`，按项目或业务范围控制自动重放。
4. 按“检测 → 携带预期状态但只观察 → 开始拦截 → 人工重放 → 自动重放”的顺序逐级放开。

## 边界

- 本次不引入 `pipeline.contrib.reliable_events` 的 SHADOW/ACTIVE 回调补偿功能。
- 本次不修改包版本和依赖锁定；出包版本由后续独立发布提交维护。
- 诊断规则不执行流程表达式；当前 3.29 LTS 的 Mako 安全实现保持不变。

## 补充：同步节点推进中断（S7）治理

在上述三期主体已同步的基础上，本次再把 3.24 LTS 已发布的 S7 能力补齐到 3.29 LTS。标准运维 master 当前运行时为 `bamboo-pipeline==3.24.22`（精确依赖 `bamboo-engine==2.6.9`），S7 由 3.24 LTS 的发布 PR #319、#321、#322 提供。

移植提交（cherry-pick，保留原始提交信息）：

- `a747b7e` feat: 增加 S7 同步节点推进中断检测与安全恢复
- `3ba392a` fix: S7 同步推进在运行中暂停/撤销后正确标记进程，READY 后数据库中断重试不丢消息

新增能力：`SYNC_ADVANCE_CHECKPOINT_ENABLED` 开关（默认 `False`）、`SyncAdvanceCheckpoint` 模型与 `eri/0006_syncadvancecheckpoint.py` 迁移、引擎同步节点输出检查点与推进权竞争、`sync_advance_stalled` 诊断判据与快档检测、安全恢复接管，以及对应的引擎/诊断/ERI 测试。

与 3.24 LTS 的差异：

- `runtime.py` 的导入按 3.29 LTS 现有分组解析，仅新增 `SyncAdvanceMixin` 的 import 与基类。
- 3.29 LTS 的 `engine.py` 在节点成功后多了「预约回滚」分支（`runtime.get_config(PIPELINE_ENABLE_ROLLBACK)`）；S7 引擎单测的 `MagicMock` 默认对它返回真值会提前 `die()`，测试中显式设 `get_config.return_value = False`，使单测聚焦 S7 边界，不改变生产逻辑。
- `eri` 迁移编号 `0006` 在 3.29 LTS 下未被占用，依赖沿用 `0005_auto_20220422_1048`。

接入要求：完成 `eri/0006` 迁移后再启动新版 worker/cleaner；所有相关 worker 升级到含本改动的包后才可打开检查点开关；自动恢复类型名为 `sync_advance_stalled`。本次仍不引入 `reliable_events`，不修改包版本与依赖锁定，不覆盖生产部署、开关灰度与容量验证。
