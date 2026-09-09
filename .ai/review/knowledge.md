# bamboo_pipeline_4.0_lts 审查知识库

这是当前 LTS 的源码索引和契约，不是缺陷清单。2026-09-09 刷新远程基线：`8ee03f25d920c8802510f41b31674b9793fcfba3`。AI CI 从已合入 master 的 `30438665e61945b90bf4c6789db94e7cf42f31d4` 接入，业务源码事实以本分支为准；以后审查需再次读取实际 PR base/head。

## 1. 发行包与分支边界

| 范围 | 当前版本/声明 | 入口 |
| --- | --- | --- |
| 核心 bamboo-engine | `3.0.5`；Python `>=3.11,<3.12` | 根 `pyproject.toml`、`bamboo_engine/__version__.py` |
| Django/Celery 运行时 bamboo-pipeline | `4.0.4`；engine 依赖 `3.0.5（精确）` | `runtime/bamboo-pipeline/pyproject.toml`、`runtime/bamboo-pipeline/pipeline/__init__.py`、`runtime/bamboo-pipeline/poetry.lock` |
| 运行时其他依赖 | Django >=4.2,<5；Celery >=5.2,<6；Mako ^1.3 | 以 pyproject/lock 和安装日志为准，声明范围不是所有组合的测试证明 |

核心与运行时分别构建发行。`bamboo_engine/eri/interfaces.py` 定义通用运行时契约，核心不依赖 Django 模型；`runtime/bamboo-pipeline/pipeline/eri/runtime.py:BambooDjangoRuntime` 与同级 `imp/` 实现数据库、组件和消息适配。运行时还保留 `runtime/bamboo-pipeline/pipeline/engine/`、`runtime/bamboo-pipeline/pipeline/core/`、`runtime/bamboo-pipeline/pipeline/parser/` 旧引擎链路，具有独立 API、Status/PipelineProcess 和表达式实现。

本分支没有 SubCanvas handler、SubCanvas 集成测试或 copy_context_values_to_new_pipeline 接口。不能将 master 的子画布语义当作已有能力。不同 LTS 的版本号、Python、Mako、节点接口和扩展能力不是线性包含关系；安全修复的历史 PR/tag 不证明当前目标分支已含相同实现。

4.0 已有回滚状态、从指定主干位置启动及 Service HookType/hook_dispatch，但没有 3.29 的 LOOP_READY、loop_enabled/loop_fail_skip、循环列表输出和计算变量 inner_loop 签名；已有 loop/inner_loop 重入状态字段并不等于节点循环能力。

## 2. API、执行、状态与调度

1. `bamboo_engine/api.py` 对外包装 `EngineAPIResult`，异常转为 result=False、exc/exc_trace；直接调用 Engine 与包装 API 的异常传播不同。run_pipeline 派发成功不等于流程执行结束。
2. `bamboo_engine/engine.py:Engine.run_pipeline` 先调用 `bamboo_engine/validator/api.py` 递归校验/规范化流程，再经过运行前钩子、runtime.prepare_run_pipeline 和 runtime.execute。校验含连接、环及网关处理，会修改流程结构，不是纯只读函数。
3. `runtime/bamboo-pipeline/pipeline/eri/runtime.py:prepare_run_pipeline` 在内部事务中创建 Process、根 State、Node、Data、ContextValue、ContextOutputs。之后投递消息仍受宿主外层事务与 broker 可见性影响，不是数据库和队列的统一原子提交。
4. `runtime/bamboo-pipeline/pipeline/eri/imp/task.py` 通过 Celery apply_async 派发；`runtime/bamboo-pipeline/pipeline/eri/celery/tasks.py` 创建 Runtime 与 Execute/ScheduleInterrupter，调用 Engine.execute/schedule。恢复点和 route headers 是队列消息契约。
5. `bamboo_engine/handler.py:HandlerFactory` 选择 `bamboo_engine/handlers/` 处理器。ServiceActivityHandler 准备上下文与执行数据，经运行时 ServiceWrapper 调用组件，写状态/输出并推进或睡眠调度。

`bamboo_engine/states.py` 定义转换和状态集合；CREATED、BLOCKED、SUSPENDED、FAILED、REVOKED 含义不同。`runtime/bamboo-pipeline/pipeline/eri/imp/state.py:set_state` 校验转换，以可选 version 参与条件更新，可刷新版本和计数；ignore_boring_set 只对指定相同版本/状态的重复设置生效。不能把不传 version 的更新当作具有相同并发保护。created_time/started_time/archived_time 受创建和显式 setter 参数控制，终态不会自动补全所有时间；读取耗时应追踪根/子流程真实写入路径。

Engine.execute 按 pipeline_stack 检查根撤销、栈内暂停及预约节点暂停，再处理节点运行、重入与后继。`runtime/bamboo-pipeline/pipeline/eri/imp/service.py:ServiceWrapper` 把 DataObject 输入输出在 finally 中同步回来，组件 execute/schedule 返回 None 按成功处理。`bamboo_engine/handlers/service_activity.py` 保存 `_result`、`_loop`、`_inner_loop` 和异常 ex_data；失败忽略可使节点 FINISHED 且 error_ignored=True，不能只凭 FINISHED 推断组件业务成功。

callback 使用节点执行 version 查找 Schedule，拒绝旧版本/完成/过期调度，保存 CallbackData 后异步派发。version 区分重试/重入，不能用作用户权限凭据。schedule 校验版本、finished 和 RUNNING，再通过 `runtime/bamboo-pipeline/pipeline/eri/imp/schedule.py` 的条件 UPDATE 争取 scheduling 锁。POLL、CALLBACK、MULTIPLE_CALLBACK 的继续/结束语义不同，重投要保留 callback_data_id 并正确释放锁。

本分支争锁失败时仅 MULTIPLE_CALLBACK 随机延迟重投，未实现 3.24 的 callback_lock_retryable 协议。Engine/ServiceActivityHandler 有 HookType/hook_dispatch，检查 hooks 对异常与恢复的顺序及副作用。

`bamboo_engine/interrupt.py`、`bamboo_engine/eri/models/interrupt.py` 保存关键点、运行版本和已经完成的 handler 结果。`runtime/bamboo-pipeline/pipeline/eri/imp/interrupt.py` 将 OperationalError/InternalError 作为中断错误。审查组件已执行但输出/状态/恢复点未写完、恢复消息重复到达、旧消息版本兼容等窗口。数据库事务和消息重试不保证外部副作用恰好执行一次。

## 3. 并行、SubProcess 和上下文

并行/条件并行处理器通过 runtime fork 产生数据库逻辑 Process，Engine join 后投递子任务。子任务到 destination 调用 `runtime/bamboo-pipeline/pipeline/eri/imp/process.py:child_process_finish`：事务内标记子进程 dead，用 F 表达式增加 ack，并用 ack_num=need_ack 的条件写判定父进程唤醒。汇聚并发控制不只位于 ConvergeGatewayHandler；审查重复确认、并行同时完成、嵌套和恢复重放，不能由 atomic 推断重复消息已去重。

`bamboo_engine/handlers/subprocess.py` 从父上下文渲染明确输入，注入子流程上下文并压栈；`bamboo_engine/handlers/empty_end_event.py` 提取声明输出、回填父上下文、出栈并推进。这里 Process/SubProcess 是流程逻辑概念，不是 OS PID。

`bamboo_engine/context.py` 区分 PLAIN 直接取值、SPLICE 模板拼接和 COMPUTE 运行时变量；hydrate 可去除 `${}`，mute_error 会把异常变成文本。`runtime/bamboo-pipeline/pipeline/eri/imp/context.py` 以 `(pipeline_id,key)` 隔离上下文，计算直接和传递引用；普通 upsert 清空 code/references。根流程输入、当前栈顶变量和子流程变量不能用同一个 ID 代替。Data 是定义输入/输出映射，ExecutionData 是实际执行值，CallbackData 是回调记录，见 `runtime/bamboo-pipeline/pipeline/eri/imp/data.py` 与 `runtime/bamboo-pipeline/pipeline/eri/models.py`。

Context.extract_outputs 只按映射写普通值，不接受 node，不追加循环结果；Context 构造和计算变量接口没有 3.29 的 inner_loop 扩展。SubProcess 仍重置/推进自身内部重入计数，不能因此给旧组件传入不存在的循环参数。起始节点只允许校验器计算的主干合法位置，不能跳入并行/子流程内部。

State/Data/ExecutionData 的 node_id 唯一、Schedule 的 `(node_id,version)` 唯一、ContextValue 的 `(pipeline_id,key)` 唯一是持久化契约。修改读后写、首次插入、输出覆盖、唯一约束或迁移时需考虑旧数据和真实并发；SQLite 成功不证明 MySQL 事务行为。

## 4. Mako 与可信输入

新入口为 `bamboo_engine/template/template.py:Template.render`，旧入口为 `runtime/bamboo-pipeline/pipeline/core/data/expression.py:ConstantTemplate.resolve_data`。两者拥有各自的安全检查和 sandbox 路径。完整 `${name}` 可直接返回上下文原对象，混合字符串则不同；模板对 dict 处理会修改持有对象，审查者应追踪复制边界与 need_render 透传语义。

核心 Settings 默认 MAKO_TEMPLATE_NAME_WHITELIST_MODE=enforce；旧表达式 MAKO_SAFETY_CHECK 默认 True。两套 checker 有 AST、过滤器、属性/名称/下标及 format/format_map 检查；off/warn/enforce 的限制不同，放宽到 off 不得声称保持相同防护。当前模板测试明确包含 test_mako_self_module_namespace_executes_when_whitelist_off 以及 enforce/过滤器/format 回归；测试存在说明设计边界，不等于本次已经执行或运行配置就是 off。

本分支没有 3.24 的 render_backend.py/render_transport.py。实际 Mako render 位于当前宿主调用链；sandbox 屏蔽名和模块导入不是 OS 隔离。ENABLE_RENDER_OBJ_BY_MAKO_STRING 默认 False，打开时纯嵌套表达式可能返回原生对象，混合字符串/禁止片段的语义需分别核对。

`runtime/bamboo-pipeline/pipeline/eri/imp/serializer.py` 的持久化格式优先 JSON，不可 JSON 序列化时使用 base64/pickle；`runtime/bamboo-pipeline/pipeline/eri/codec.py` 则是可配置 encoder/object_hook 的 JSON 编解码。修改必须兼容已有数据库行、上下文和恢复点。pickle 数据应保持可信来源；只有证明本次修改让外部请求可控字节进入危险入口，才能报告新增注入，不能把现存机制自动判为本 PR 漏洞。

核心 API 不含宿主业务用户权限上下文。管理接口位于 `runtime/bamboo-pipeline/pipeline/contrib/engine_admin/views.py`，使用可选 PIPELINE_ENGINE_ADMIN_API_PERMISSION 回调；是否挂载、宿主登录和权限配置要沿调用链确认。节点 ID 和 version 都不是授权机制。

## 5. 扩展与真实测试入口

`runtime/bamboo-pipeline/pipeline/contrib/rollback/` 默认关闭，需 app、迁移和回滚队列；TOKEN 与 ANY 的业务补偿差异见 `docs/user_guide/rollback.md` 与当前 handler/graph。还包含 node_timeout、node_timer_event、plugin_execute 和 `runtime/bamboo-pipeline/pipeline/contrib/diagnostics/`；诊断事件/管理操作需核对权限、状态与失败隔离。没有 3.24 的 reliable_events。测试中 hook、plugin_execute 入口存在，但无 SubCanvas/节点循环输出场景。

| 验证层次 | 本分支入口 | 证据边界 |
| --- | --- | --- |
| 核心单元测试 | `tox.ini`（py311）；`tests/engine/`、`tests/handlers/`、`tests/interrupt/`、`tests/eri/`、`tests/test_context.py`、`tests/validator/` | tox 使用 poetry run coverage run -m pytest tests；mock runtime 不证明数据库竞争/真实消息重投 |
| 模板双入口 | `tests/template/test_template.py`、`runtime/bamboo-pipeline/pipeline/tests/core/data/test_expression.py` | 必须区分 checker 通过与真实 render 未执行副作用；只运行无破坏性探针 |
| Django 单测 | `.github/workflows/runtime_pipeline_unittest.yml`、`runtime/bamboo-pipeline/pipeline/tests/` | CI 复制两包源码到 test 工程，使用 MySQL 执行 manage.py test pipeline.tests；复用本地副本需防止测旧代码 |
| 新 ERI 集成 | `.github/workflows/runtime_pipeline_end_to_end_test.yml`、`runtime/bamboo-pipeline/test/eri_imp_test_use/tests/` | control、execution、data_transfer、advanced、chaos 等入口；需迁移、MySQL、Redis、RabbitMQ 和可响应的 Celery worker |
| 旧引擎集成 | `.github/workflows/pipeline_end_to_end_test.yml`、`runtime/bamboo-pipeline/test/pipeline_test_use/tests/` | 与新 ERI 是两组独立协议测试；旧 Status/PipelineProcess、组件、回调和表达式不能用新引擎子集替代 |

当前业务 CI 配置：Python 3.11.10，Django 矩阵标签 4.2，ubuntu-22.04，Poetry 2.0.0。运行时安装命令使用 `Django>矩阵值`，标签不是最终安装版本。`.github/workflows/pr_check.yml` 的目标分支过滤为 master、develop、python_upgrade_master。该过滤不包含当前 LTS，不能按 workflow 文件存在推断已触发。 新增 AI workflow 独立使用无分支过滤的 pull_request_target；接入本 LTS 并不自动修复/扩大旧业务 CI，也不证明其历史 runner 仍可用。按运行记录区分未触发、等待 runner、跳过、执行失败和通过。

## 6. 版本、发行与审查证据

核心版本同步根 pyproject 与 `bamboo_engine/__version__.py`；运行时同步自身 pyproject 与 `pipeline/__init__.py`，依赖变更核对 runtime 的 poetry.lock。两包分别通过 `.github/workflows/engine_python_package_poetry.yml` 与 `.github/workflows/runtime_pipeline_python_package_poetry.yml` 构建，tag 模式分别是 `bamboo-engine-v*.*.*` 和 `bamboo-pipeline-v*.*.*`。确认本分支解释器、构建目录与最终包元数据，不套用 master 的发布步骤。本分支没有 docs/release_process.md；现有发行 workflow 使用 Python 3.11/Poetry 2.0.0。

若 runtime 依赖新的 engine 版本，先确认核心包源可解析，再发行 runtime。源码存在、检查通过、tag 创建、包发布、宿主安装、worker 配置、真实业务读写回验是不同证据。AI CI 接入不升级业务依赖、不运行生产迁移、不自动合入或发布；历史问题只有由本次 diff 引入/放大且有可达证据才作为 finding。
