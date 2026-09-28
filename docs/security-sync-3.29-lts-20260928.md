# 3.29 LTS Mako 安全同步验证（2026-09-28）

## 基线与范围

- 目标：`ai/sync-mako-security-3.29-lts-20260928`，基线 `upstream/bamboo_pipeline_3.29_lts` 的 `cd9f7b8`。包版本保持 engine `2.11.3`、pipeline `3.29.9`。
- 安全实现与 master 同步分支 `ai/sync-mako-security-master-20260928` 的 `bamboo_engine/utils/mako_safety.py` 相同，并保留 Python 3.6/3.7 的 `ast.Index` 下标解包。下文全量数字来自该 master 端口在 Python 3.6/3.7 上的记录；本分支的定向复验写在版本说明中。
- 权威源：4.0 LTS `8a9f6ea6f0f1b6b216d68c1586c5531df6dbb7b1`、3.24 LTS `6979feba98d01ec2cd4594206ddbdf0ee99f045f`。
- 复用安全补丁 `519b063`、`5fbe338`、`4868979`、`1a5dcda` 及 `4de95c7` 文档；最终按源分支内容核对，不以祖先关系代替验证。
- 覆盖既有 filter callable、动态字符串、subscript、默认 shield、根白名单，以及 frame 属性、restricted builtins、危险属性/保留命名空间、导入过滤、合法 `_module`/caller/alias、仅 enforce 禁止 format。
- 同步可选 subprocess、受限协议、超时/大小边界、primitive-only reply、可信 parent 决定兼容回退、设施故障显式停止及恢复类别、执行/调度/完成钩子的故障处理。
- 安全模块 13 文件与 4.0 源的 AST 相同（比较时仅归一化本分支必需的 `ast.Index` 解包）。3.24 的同源 backend/稳定性测试差异仅为导入排版。
- 本分支 `Engine` 只改 `hook_dispatch`、`execute`、`schedule` 并增加 `_fail_rendering`；保留 SubCanvas、循环作用域、重试/跳过与输出聚合。普通业务失败保留 `error_ignorable`/`loop_fail_skip`，设施故障均停止。
- engine 和 legacy 的 `_get_subscript_key` 均保留 Python 3.6/3.7 `ast.Index` 解包，新增 `__class__`、`__builtins__`、`__globals__` 的 AST 和真实渲染回归。
- 未同步卡住治理、callback 诊断、SubCanvas 新功能或发布变更。应用默认配置、依赖声明/锁文件和版本不变：engine `2.11.3`、pipeline `3.29.9`；新 backend 默认 `inprocess`。
- 本分支在 Python 3.7.16 上复验 `tests/template` 的帧反射、属性策略、format 模式、导入过滤和模板回归，152 passed。

## 实测结果

| 环境 | engine 全量 | legacy core + engine core（SQLite） | 原始 A–D 替身探针 |
| --- | --- | --- | --- |
| Python 3.6.15 / Django 2.2.28 / Celery 5.1.2 | 621 passed, 1 skipped | 236 passed | 24/24 阻断，0 sink，6/6 对照通过 |
| Python 3.7.16 / Django 3.2.25 / Celery 5.2.7 | 621 passed, 1 skipped | 236 passed | 24/24 阻断，0 sink，6/6 对照通过 |

两套环境均为 Mako 1.1.4、MarkupSafe 2.0.1、Werkzeug 1.0.1、prometheus-client 0.9.0、pyparsing 2.4.7、pytest 6.2.5、mock 4.0.3。每套新增的 report/subscript/正常表达式 engine 回归为 30 项；循环失败恢复组合为 32 项，已包含在全量数字中。legacy 的模式和载荷使用 unittest subTest，不单独计为测试方法。

最终修正了沙箱测试原有的 `r3` 未断言问题，两个环境各定向复验该测试文件 103 项通过。后续仅有格式调整，复用同一实现状态下的全量结果。

- Black 20.8b1、flake8 4.0.1：45 个变更 Python 文件通过。
- Python 3.6/3.7：45 个变更 Python 文件分别编译通过。
- `git diff --check` 和暂存差异检查通过。
- CI YAML 可解析；master 的 PR 入口原本已使用本地 reusable workflow。本次独立 CI 提交增加显式 SQLite 安全测试步骤，直接使用当前 checkout，并在 tox 中禁用 pytest 插件自动加载。

## 复现命令

在分配的 master worktree 根目录执行。`output/security-master/venv36` 与 `venv37` 是本次专用环境；没有安装或修改共享环境。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  output/security-master/venv36/bin/python -m pytest tests -q --disable-warnings
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  output/security-master/venv37/bin/python -m pytest tests -q --disable-warnings

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD:$PWD/runtime/bamboo-pipeline:$PWD/runtime/bamboo-pipeline/test" \
  output/security-master/venv36/bin/python runtime/bamboo-pipeline/test/manage.py test \
  pipeline.tests.core pipeline.tests.engine.core \
  --settings=pipeline_sdk_use.security_settings --noinput
# 用 venv37 重复上面的 legacy 命令。

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD:$PWD/runtime/bamboo-pipeline" \
  output/security-master/venv37/bin/python \
  /Users/dengyh/Projects/bk-sops/output/mako_cnvd_verification_20260928/probe.py \
  master-security-worktree
# venv36 对同一探针也已验证；探针只替身记录命令调用。
```

原始日志保留在本 worktree 的 `output/security-master/`：`engine36.log`、`engine37.log`、`legacy-core36.log`、`legacy-core37.log`、`probe36.json`、`probe37.json`、`source-comparison.json`、`black.log`、`flake8.log` 和最终定向测试日志。

## 边界与限制

- 本机为 macOS，跳过项为 Linux-only rlimit 断言；Linux network namespace/资源限制和 GitHub 托管 CI 未实跑。CI 的 Python 3.6.12 也未本地执行，本地使用 3.6.15。
- legacy 使用独立内存 SQLite，未读取 dotenv、未连接业务/生产数据库；覆盖 core 与 engine core，未运行完整 pipeline 应用、MySQL、Celery 部署或生产流程验收。应用启动时建表前的注册日志不代表测试失败，以最终 runner 结果为准。
- 共享 Python 3.6 环境只读试跑过 engine；其 minimal legacy runner 缺 `ujson`，该试跑不计入通过证据，随后已用本 worktree 专用完整环境通过上述 236 项。
- `.format()` 在 off/warn 保留兼容行为，legacy 的安全检查按 `MAKO_SAFETY_CHECK=True` 验证；未修改调用方默认值。subprocess 共享宿主身份/文件系统，不等于容器隔离，详见 `mako-render-backend.md`。
- 未 push、创建 PR、merge 或 release。安全代码与 CI 分提交，便于 LTS 只移植安全提交并保留自己的 CI。
