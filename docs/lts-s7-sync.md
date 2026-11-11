# 4.0 LTS：同步节点推进中断（S7）治理同步说明

本分支把 3.24 LTS 已发布的 S7 同步节点推进中断检测与安全恢复能力同步到 `bamboo_pipeline_4.0_lts`，供依赖 bamboo-pipeline 4.0.x、bamboo-engine 3.0.x（BKFlow Python 3.11 LTS）的应用接入。4.0 LTS 此前已通过 PR #274 / #316 具备流程卡住治理三期主体（诊断检测、门禁、人工/自动重放），本次仅补齐 S7；功能开关保持关闭，升级包本身不会自动启用检查点、拦截或重放。

## 来源

- 标准运维 master 当前运行时为 `bamboo-pipeline==3.24.22`（精确依赖 `bamboo-engine==2.6.9`），对应 3.24 LTS 的发布 PR #319、#320、#321、#322。
- 本次移植以下两个提交（cherry-pick，保留原始提交信息）：
  - `a747b7e` feat: 增加 S7 同步节点推进中断检测与安全恢复
  - `3ba392a` fix: S7 同步推进在运行中暂停/撤销后正确标记进程，READY 后数据库中断重试不丢消息

## 同步内容

- `bamboo_engine/config.py` 新增 `SYNC_ADVANCE_CHECKPOINT_ENABLED`，默认 `False`。
- `bamboo_engine/engine.py` 在同步节点输出持久化后写入输出检查点并竞争推进权；数据库中断后的续跑由 `wake_sync_recovery` 接管；运行构造时校验 runtime 是否实现三个检查点方法。
- `pipeline/eri/imp/sync_advance.py`（新增）与 `pipeline/eri/models.py` 的 `SyncAdvanceCheckpoint` 模型、迁移 `eri/0006_syncadvancecheckpoint.py`（新增）。
- 诊断侧在 `case_types.py` / `signatures.py` / `signature_scan.py` / `recovery.py` / `conf.py` 增加 `sync_advance_stalled` 类型、判据、快档检测和安全恢复条件。
- 新增配套测试 `tests/engine/test_sync_advance.py`、`pipeline/contrib/diagnostics/tests/test_sync_advance.py`、`pipeline/tests/eri/test_sync_advance_flow.py`。

## 与 3.24 LTS 的差异

- `runtime/bamboo-pipeline/pipeline/eri/runtime.py` 的导入顺序按 4.0 LTS 现有分组解析，仅新增 `SyncAdvanceMixin` 的 import 与基类，逻辑与源提交一致。
- 4.0 LTS 的 `engine.py` 在节点成功后多了「预约回滚」分支（检查 `runtime.get_config(PIPELINE_ENABLE_ROLLBACK)`）；S7 引擎单测里的 `MagicMock` 默认对 `get_config` 返回真值，会提前 `die()` 返回。测试中显式设 `get_config.return_value = False`，使单测聚焦于 S7 检查点边界，不改变生产逻辑、不关闭真实回滚能力。
- 迁移编号 `0006` 在 4.0 LTS 的 `eri` 应用下未被占用，依赖沿用 `0005_auto_20220422_1048`。

## 接入要求

1. 完成 `python manage.py migrate`，确认 `eri` 的 `0006_syncadvancecheckpoint` 标记为已应用；即使不打开 S7 开关，新版 cleaner 删除 Process 时也会访问检查点表。
2. 所有可能处理同步节点的 worker 升级到含本改动的包后，才能打开 `SYNC_ADVANCE_CHECKPOINT_ENABLED`；混合旧 worker 期间禁止接管。
3. 执行保护（门禁）与检测、人工/自动恢复开关继续沿用 4.0 LTS 已有配置；S7 自动恢复类型为 `sync_advance_stalled`。
4. 按「先观察、再拦截、再人工恢复、最后自动恢复」的顺序逐级放开，并评估检查点带来的额外数据库读写。

## 边界

- 本次不引入 `pipeline.contrib.reliable_events`（M2）的回调补偿功能；该模块在标准运维侧随包提供但未注册，不属本次引擎能力对齐范围。
- 本次不修改包版本和依赖锁定；出包版本由后续独立发布提交维护。
- 本说明只覆盖代码同步；生产部署、迁移执行、开关灰度与容量验证不在此范围。
