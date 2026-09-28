# 5.0 LTS Mako 安全修复同步验收（2026-09-28）

## 范围与基线

- 目标：`ai/sync-mako-security-5.0-lts-20260928`，基于 `upstream/bamboo_pipeline_5.0_lts` 的 `3ed8129532b6a23a51de4744b02adafadfc36148`。
- 权威内容：4.0 LTS `8a9f6ea6f0f1b6b216d68c1586c5531df6dbb7b1`；3.24 LTS `6979feba98d01ec2cd4594206ddbdf0ee99f045f` 交叉核对。
- 同步 filter callable、动态字符串/下标防护及默认 shield（#265/#268），根白名单（#266/#270），frame/builtins/always-on 属性与保留命名空间/导入安全及兼容性（#284），可选隔离渲染及协议/资源/回退边界（#285/#287），设施故障停止节点和 legacy 传播/恢复标记（#296），4.0 后续 hook 故障修复。
- 主要源提交：`519b063`、`5fbe338`、`4868979`、`1a5dcda`、`4de95c7`。较早基础防护按权威分支最终文件同步，并非只使用尚不完整的 PR #283。
- 保留 5.0 的嵌套对象渲染、hooks、rollback、events。没有同步 callback 诊断/锁重试、卡住治理、SubCanvas 或发布改动。
- 两套 pyproject/lock、包版本、Python 约束保持基线内容；渲染后端默认仍为 `inprocess`。没有修改宿主应用配置。

## 内容复核

12 个核心文件（engine config/template/sandbox/render_backend/render_transport/mako_safety/checker；legacy expression/mako_safety/sandbox/sandbox_builder/checker）与 4.0 权威源的 Python AST 一致；格式调整不改变语义。

Engine 仅调整 `hook_dispatch`、`execute`、`schedule` 并新增 `_fail_rendering`。除 `schedule` 保留 5.0 原有 callback/锁逻辑外，其余变更方法与权威源 AST 一致。legacy schedule 仅增加设施故障处理，未引入源分支的回调刷新逻辑。

4.0 与 3.24 的 render backend/transport/sandbox 核心一致；安全 visitor 的差异主要是 Python AST 版本兼容，5.0 保留 Python 3.12 所需行为。下标、合法 `_module`、光杆 `caller`、导入 alias、`.format` 仅 enforce，以及正常表达式均有回归覆盖。

新增 A–D 真实渲染回归进入 engine pytest 与 legacy Django tests，均将 `os.system`、`os.popen`、`subprocess.Popen` 替换为无副作用 mock，并断言未调用。导入的旧攻击用例也增加同类保护。正常 subprocess 后端测试只启动测试 Python worker，不执行攻击载荷中的命令。

## 环境与结果

本地专用环境位于本 worktree 的 `venv/`、`venv/django5/`，未修改共享虚拟环境。macOS / Python **3.12.4**；CI 原 Python **3.12.10** 矩阵保留。

- Mako 1.3.12、pytest 7.4.4、mock 5.2.0、Black 23.12.1、flake8 6.1.0。
- 声明范围环境：Django 4.2.30、Celery 5.6.3、django-timezone-field 5.1、Werkzeug 3.1.9、pyparsing 3.3.3。
- 兼容性环境：同上，单独强制安装 Django 5.2.17；此环境不满足既有 timezone-field 的 Django `<5` 元数据要求，不能视为可直接部署的依赖组合。

| 检查 | 实测结果 |
| --- | --- |
| 全 engine `tests` | **581 passed，1 skipped**；跳过 Linux-only rlimit 测试 |
| Django 4.2，legacy `pipeline.tests.core` + `pipeline.tests.engine.core` | **235 通过** |
| 独立 legacy sandbox builder pytest 函数 | **6 通过**（Django 4.2/5.2 环境各一次） |
| 用户提供的 minimal SQLite runner，四个渲染测试模块 | **70 通过**（Django 4.2/5.2 环境各一次） |
| 仓库内最小设置，Django 5 渲染专项 | **70 通过** |
| 原始安全替身探针，engine/legacy × off/warn/enforce × A–D | **24/24 保留原文、0 命令调用**；12 次正常控制通过；两套 Django 环境均通过 |
| 扩查 legacy 全 `pipeline.tests`（SQLite/Django 4.2） | 680 项中 **676 通过、4 失败**；下述 4 项在原始基线全部复现 |
| Black / flake8 / Python compile | 全部变更 Python 文件通过 |
| workflow YAML/本地复用路径、`git diff --check` | 通过 |

上表存在重叠测试集，不能将各行简单累加。pytest 的弃用警告未被当作通过证据；本地验证不代表远程 CI、MySQL E2E 或 Linux 容器权限验证已通过。

### 已复现的基线限制

1. SQLite 扩查失败：`ProcessMixinTestCase.test_child_process_finish`；`ScheduleMixinTestCase.test_apply_schedule_lock`、`test_apply_schedule_lock__all_fail`、`test_release_schedule_lock`。这些多线程数据库锁用例在 `3ed8129` 原始代码和相同隔离设置下 **4/4 同样失败**，不属于本次引入。未为了通过而修改或跳过这些业务测试。
2. Django 5 全应用不能启动：`pipeline.contrib.node_timer_event.models.NodeTimerEventConfig.Meta.index_together` 不被 Django 5 接受，原始 `3ed8129` 也出现相同 `TypeError`。此外原始 runtime pyproject 为 `Django >=4.2,<5`、`django-timezone-field ^5`，并不是一个已完成 Django 5 升级的依赖集合；按任务边界保留这些声明。Django 5 本次仅确认渲染/数据边界测试，不声称全应用支持。
3. 未连接生产、未运行数据库迁移/真实 broker 集成，未验证 Linux network namespace/权限。后端 fail-closed 的非 Linux、协议、超时、启动失败、恢复与 hook 行为已由本地回归覆盖。

## 可复核命令

均在此 worktree 根目录运行。pytest 显式禁用自动插件，清除 `DJANGO_SETTINGS_MODULE`，使用原有 `tests/__init__.py` 与默认 import mode。

```sh
env -u DJANGO_SETTINGS_MODULE PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  venv/bin/python -m pytest tests -q -rs --disable-warnings

PYTHONPATH=.:runtime/bamboo-pipeline:runtime/bamboo-pipeline/test \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  venv/bin/python -m django test --settings=pipeline_sdk_use.security_test_settings \
  pipeline.tests.core pipeline.tests.engine.core --noinput

env -u DJANGO_SETTINGS_MODULE PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=.:runtime/bamboo-pipeline venv/bin/python -m pytest \
  runtime/bamboo-pipeline/pipeline/tests/core/data/test_sandbox_builder.py -q

PYTHONPATH=.:runtime/bamboo-pipeline:runtime/bamboo-pipeline/test \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  venv/django5/bin/python -m django test --settings=pipeline_sdk_use.security_render_settings \
  pipeline.tests.core.data.test_expression pipeline.tests.core.data.test_sandbox \
  pipeline.tests.core.data.test_render_infrastructure pipeline.tests.core.data.test_cnvd_frame_render --noinput

env -u DJANGO_SETTINGS_MODULE PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=.:runtime/bamboo-pipeline venv/bin/python \
  /Users/dengyh/Projects/bk-sops/output/mako_cnvd_verification_20260928/probe.py security-5.0-lts

git diff --check
```

用户提供的 minimal runner 调用：以 `venv/bin/python` 或 `venv/django5/bin/python` 运行
`/Users/dengyh/Projects/bk-sops/output/bamboo_security_sync_20260928/run_legacy_data_tests.py`，显式传入上面四个渲染模块 labels；不引用本分支不存在的 `test_private_subscript` 模块。

证据保留在本 worktree 的 `.cache/security-sync/`：`engine-final.log`、`legacy-related-django42.log`、`legacy-minimal.log`、`legacy-render-django5.log`、`sandbox-builder*.log`、`probe*.json`、`legacy-full-django42.log`、`legacy-baseline-sqlite.log`、`legacy-full-django5.log`、`legacy-baseline-django5.log` 和 `versions.json`。基线复现使用 `git archive 3ed8129` 在本 worktree 缓存目录的只用于验证的副本，没有切换或修改主检出/其他分支。

## CI 与交付边界

`pr_check.yml` 增加本 LTS 目标，六个 job 全部复用本 checkout 的 workflow，不再引用失效的 `python_upgrade_master`。runtime 单测区分 Django 4.2 全应用与 Django 5 渲染专项，补上 Django runner 不会收集的 sandbox builder pytest 函数。原 E2E 的宽泛 `Django>4.2` 改为当前矩阵的 `Django~=4.2.0`，遵守原依赖范围，避免无意安装不兼容主版本；没有将 Python 降至 3.11。

只创建本地 commit；未 push、未创建 PR、未 merge、未发布。后续统一交付时仍需远程 CI/MySQL E2E 结果，Django 5 全应用升级应单独处理。
