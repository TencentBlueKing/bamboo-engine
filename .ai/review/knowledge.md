# bamboo-engine 审查知识库

这是阅读源码的索引和契约说明，不是缺陷清单。记录以 2026-09-09 的远程 `master` 提交 `b69228fcb72d9862ff5d09d717b87824dfabc209` 为基线。审查时以本次 PR 的 base/head 和目标分支源码为准；文件存在、默认配置、依赖范围、CI 矩阵均可能变化。

## 1. 仓库与发行边界

| 范围 | 源码入口 | 审查含义 |
| --- | --- | --- |
| 核心发行包 `bamboo-engine` | 根 `pyproject.toml`、`bamboo_engine/__version__.py`、`bamboo_engine/` | 通用执行、调度、上下文和 ERI 接口；不依赖 Django 模型实现。基线版本 `2.11.4`。 |
| 运行时发行包 `bamboo-pipeline` | `runtime/bamboo-pipeline/pyproject.toml`、`runtime/bamboo-pipeline/pipeline/__init__.py` | 基线版本 `3.29.10`，依赖 `bamboo-engine = "^2.11.4"`。运行时源码不是根包自动包含的目录。 |
| 新引擎的 Django/Celery 适配 | `runtime/bamboo-pipeline/pipeline/eri/runtime.py`、`pipeline/eri/imp/`、`pipeline/eri/celery/`（后两者均在运行时包下） | `BambooDjangoRuntime` 实现核心 ERI；数据库、消息路由、组件适配和信号在此。 |
| 同包保留的旧引擎 | `runtime/bamboo-pipeline/pipeline/engine/`、`pipeline/core/`、`pipeline/parser/`（均在运行时包下） | 有独立 API、Status/PipelineProcess、处理器及数据表达式实现。改新引擎不自动修复旧链路；也不能要求每项新功能都复制到旧引擎，须先确认目标范围。 |
| 可选扩展 | `runtime/bamboo-pipeline/pipeline/contrib/` | rollback、node_timeout、node_timer_event、plugin_execute、engine_admin 等依赖宿主安装、配置或 worker，目录存在不等于接入方已启用。 |

核心 Python 声明为 `>=3.6,<4`；运行时为 `>=3.6,<4`、Django `>=2.2,<5`、Celery `>=4.4,<6`。这不代表所有组合均经验证。当前 CI 实际安装版本还受 lock、Python 兼容性及安装命令影响，不能只按声明上界或矩阵名称判断。

### LTS 是不同源码与依赖线

以下为同日读取远程 branch head 和两份 `pyproject.toml` 的快照，不表示包源已发布或业务已部署这些版本。

| 目标分支 | 完整 head SHA | engine / pipeline 版本 | Python；pipeline 对 engine 的声明 |
| --- | --- | --- | --- |
| `bamboo_pipeline_3.24_lts` | `02041ff974d80cd3ea48bc7e4c182302abab69ce` | `2.6.7` / `3.24.18` | `>=3.6,<3.8`；`2.6.7` 精确依赖 |
| `bamboo_pipeline_3.29_lts` | `cd9f7b80a340f89bd66711bbf8007dc23411f397` | `2.11.3` / `3.29.9` | `>=3.6,<4`；`^2.11.3` |
| `bamboo_pipeline_4.0_lts` | `8ee03f25d920c8802510f41b31674b9793fcfba3` | `3.0.5` / `4.0.4` | `>=3.11,<3.12`；`3.0.5` 精确依赖 |
| `bamboo_pipeline_5.0_lts` | `3ed8129532b6a23a51de4744b02adafadfc36148` | `4.0.0rc0` / `5.0.0rc0` | `>=3.12,<3.13`；`4.0.0rc0` 精确依赖 |

4.0/5.0 LTS 声明 Django `>=4.2,<5`、Celery `>=5.2,<6`、Mako `^1.3`；master/3.24/3.29 声明 Mako `^1.1.4`。以上四个 LTS 快照均没有 `bamboo_engine/handlers/subcanvas.py`；3.24 也没有 `pipeline/contrib/rollback/`。master 有这些路径。master、3.24、3.29、4.0 的核心配置均有默认 `MAKO_TEMPLATE_NAME_WHITELIST_MODE = "enforce"`，5.0 快照未声明该配置；这只是实现差异，不足以断言任一分支有可利用漏洞或已实现完整隔离。

回移修改时应在目标分支复核接口、迁移和实际渲染入口。历史 PR、tag 名称、版本号大小不证明包含修复；需要检查修复提交祖先关系及当前实现。

## 2. 从公开 API 到真实执行

1. `bamboo_engine/api.py` 是对外入口。`_ensure_return_api_result` 将异常包装为 `EngineAPIResult(result=False, message="fail", exc=..., data=None, exc_trace=...)`；正常返回统一放入 `data`。直接调用 `Engine` 与调用 API 的异常语义不同。API 派发成功不代表节点执行成功。
2. `bamboo_engine/engine.py:Engine.run_pipeline` 调用 `validator.validate_and_process_pipeline`、起始节点校验、运行前钩子，再调用 runtime 准备数据与派发任务。校验器会递归处理 SubProcess/SubCanvas，规范化输入输出并填充网关信息；它不是纯只读校验。
3. `runtime/bamboo-pipeline/pipeline/eri/runtime.py:BambooDjangoRuntime.prepare_run_pipeline` 在事务内创建 Process、根 State、Node、Data、ContextValue、ContextOutputs，返回 process_id。`Engine.run_pipeline` 随后调用 `runtime.execute`。宿主外层事务与消息可见性的关系仍须单独检查，不能认为该内部事务消除了所有提交/投递竞争。
4. `pipeline/eri/imp/task.py:TaskMixin`（运行时包下）用 `apply_async` 派发 `pipeline.eri.celery.tasks.execute/schedule`，携带 `process_id`、节点、恢复点和 route headers。`_retry_once` 失败后再次投递；不要据此假定消息恰好投递一次。
5. `pipeline/eri/celery/tasks.py` 构造 `BambooDjangoRuntime`、Execute/ScheduleInterrupter，进入 `Engine.execute/schedule`。`bamboo_engine/handler.py:HandlerFactory` 按 NodeType 选中 `bamboo_engine/handlers/` 中的处理器。
6. `ServiceActivityHandler` 经 `runtime.get_service` 获取组件适配器，准备上下文和 ExecutionData，调用 execute/schedule，记录输出、状态、历史及钩子，并推进下一节点或进入睡眠/调度。

`bamboo_engine/eri/interfaces.py` 是跨包兼容接口，涵盖 State、Process、Schedule、Context、Data、Service、Variable、Hooks 等 mixin；具体数据类在 `bamboo_engine/eri/models/`。更改签名、返回类型或新增必需方法时，要检查 Django 实现、mock 测试以及外部运行时的兼容方式，不能把本仓唯一实现当作所有使用者。

## 3. 状态、节点生命周期与调度

- `bamboo_engine/states.py` 定义合法转换、归档状态、睡眠状态和回滚状态。`CREATED`、`LOOP_READY`、`BLOCKED`、`SUSPENDED`、`FAILED`、`REVOKED` 的含义不同；枚举和各状态集合也不是等价集合。
- `pipeline/eri/imp/state.py:StateMixin.set_state` 校验转换，按可选 `version` 限制更新，并可刷新 version、计数及时间字段。`ignore_boring_set` 只有当前状态、传入版本和目标状态一致才提前返回；不能把它理解为所有写入幂等。`version=None` 的调用不具备相同的版本比较条件。
- `created_time`、`started_time`、`archived_time` 分别受创建和显式参数控制。设置终态并不会自动补所有时间；例如基线 `Engine.revoke_pipeline` 只传 `to_state=REVOKED`。审查状态查询/耗时修改时，要追踪具体 setter、根/子流程和宿主展示代码；这项事实本身不是本次 PR 的新增缺陷。
- `Engine.execute` 读取流程栈，检查根撤销、栈内暂停、预约节点暂停，再刷新运行状态、version、loop/inner_loop 并调用处理器。流程 Process 是数据库中的逻辑推进单元，不是操作系统 PID。
- `bamboo_engine/handlers/service_activity.py` 写入 `_result`、`_loop`、`_inner_loop` 与 `ex_data`。普通成功、需调度、失败暂停、error_ignorable、loop_fail_skip 的后继节点和输出提取不同；忽略失败可处于 FINISHED 且 `error_ignored=True`，不能只用 FINISHED 推断组件成功。
- `pipeline/eri/imp/service.py:ServiceWrapper` 适配旧组件 DataObject，`finally` 同步输入输出；组件 execute/schedule 返回 `None` 会转换为成功。`interval` 对应 POLL，无 interval 根据多回调开关选择 CALLBACK/MULTIPLE_CALLBACK。更改返回值判断、数据复制或调度结束判断时须保留这些契约。
- `Engine.callback` 查找当前节点的睡眠 Process、读取 `(node_id, version)` 的 Schedule、拒绝过期版本或已结束/过期调度，保存 CallbackData 后派发。执行版本用于区分重试/重入轮次，不是调用者权限凭证。
- `Engine.schedule` 检查 finished、版本和 RUNNING 状态后取调度锁。`pipeline/eri/imp/schedule.py:apply_schedule_lock` 用 `filter(scheduling=False).update(scheduling=True)` 判定唯一获取者；多回调争锁失败会保留 callback_data_id 延时重试，其他类型有不同处理。审查锁释放、恢复点、下一轮投递、finish_schedule 与再次执行的顺序，不要仅把它改成普通内存锁或无条件 update。
- `Engine`、`ServiceActivityHandler` 的 pre/post、node_enter/node_finish、失败/异常信号及 hooks 在不同成功/异常/恢复路径触发，不能把钩子重排视为无行为变化。

## 4. 并行、子流程与上下文

`bamboo_engine/handlers/parallel_gateway.py`、`conditional_parallel_gateway.py` 通过 runtime fork 分出逻辑 Process；Engine join 后派发子任务，子任务到 destination 时调用 `pipeline/eri/imp/process.py:child_process_finish`。该方法在事务内标记子 Process dead、用 F 表达式累加 ack，并通过 `ack_num=need_ack` 条件更新决定唤醒父进程。修改时检查多分支同时完成、重复确认、嵌套并行和恢复重放；事务存在不自动证明重复确认已去重。`ConvergeGatewayHandler` 自身不承担全部汇聚并发控制。

`bamboo_engine/validator/` 校验连接、环、网关和流程流向。`cycle_tolerate` 只改变环检查，不等于允许任何非法拓扑。从指定位置执行只能使用经过计算的主干合法节点，不能直接允许并行分支或子流程内部节点跳入。排他网关还受 `PIPELINE_EXCLUSIVE_GATEWAY_STRATEGY` 与表达式函数影响，不能将“多个条件命中”一律按相同策略处理。

| 数据/节点 | 当前源码契约 | 审查入口 |
| --- | --- | --- |
| 普通、拼接、计算变量 | PLAIN 直接取值；SPLICE 经模板引用解析；COMPUTE 经 runtime 取计算变量，可能执行宿主代码。hydrate 可去除 `${}`，mute_error 会将异常变成文本。 | `bamboo_engine/context.py:Context`、`pipeline/eri/imp/variable.py` |
| 定义数据与执行数据 | Data 保存 need_render 输入和输出映射；ExecutionData 保存本次实际输入输出；CallbackData 独立保存回调数据。不能混用配置值、渲染值和执行值。 | `bamboo_engine/eri/models/runtime.py`、`pipeline/eri/imp/data.py`、`pipeline/eri/models.py` |
| 上下文范围 | 以 `(pipeline_id,key)` 唯一标识；读取直接及传递引用，更新普通变量会清空 code/references。顶层输入、当前栈顶上下文和子流程上下文有不同 ID。 | `pipeline/eri/imp/context.py`、`pipeline/eri/utils.py` |
| SubProcess | 从父上下文解析明确输入，注入自身上下文并压栈；结束事件取声明输出回填父上下文、出栈并继续父节点后继。 | `bamboo_engine/handlers/subprocess.py`、`empty_end_event.py` |
| SubCanvas | 复制父流程全部上下文到自身，保留变量类型、code 和 references；当前复制使用 update_or_create。不能直接套用 SubProcess 的显式输入映射。 | `bamboo_engine/handlers/subcanvas.py`、`pipeline/eri/imp/context.py:copy_context_values_to_new_pipeline` |
| 循环输出 | `Context.extract_outputs` 对 loop_enabled 节点追加一轮输出，包含 result/inner_loop；loop、inner_loop、retry 是不同维度。 | `bamboo_engine/context.py`、`bamboo_engine/eri/models/node.py` |

表中 `pipeline/...` 均相对 `runtime/bamboo-pipeline/`。普通 upsert、列表追加、子画布复制的并发/恢复语义不同。检查重复 key、并行首次创建同名变量、重入覆盖、浅拷贝共享对象及恢复后重复追加；只有能由本次修改触发并沿调用链证实的情况才作为 finding。

## 5. Mako、可信数据与执行边界

两条主要表达式路径：新引擎 `bamboo_engine/template/template.py:Template`，旧引擎 `runtime/bamboo-pipeline/pipeline/core/data/expression.py:ConstantTemplate`。两者分别使用对应目录下的 mako_safety、mako_utils/checker 与 sandbox；它们不是同一入口的别名。

基线已有以下行为，安全审查应确认修改未绕过，而不是声称这些保护不存在：

- AST visitor 限制危险属性/名称/下标、import、format/format_map；checker 还检查表达式过滤器与标签过滤器调用。只检查 `${expr}` 中 expr 的 AST 不覆盖完整 Mako 过滤器语法。
- 核心 Settings 默认名称白名单 `enforce`；`warn` 只记录，`off` 不做该白名单检查。白名单由上下文、允许的内置名、配置的导入模块及额外名称构成；扩充模块或可调用对象会改变能力边界。旧表达式路径另受 Django `MAKO_SAFETY_CHECK` 控制。
- 被禁止或检查失败的模板片段通常保留原文并继续处理，而不是统一向外抛异常。调用者因此可能获得未解析的 `${...}`；新逻辑需明确兼容语义和数据流。
- 完整 `${name}` 可直接返回上下文原对象；可选 `ENABLE_RENDER_OBJ_BY_MAKO_STRING` 支持特定嵌套索引对象取值。混合字符串渲染与整对象引用的类型不同。Template 对 dict 的处理会修改持有的数据，需要关注上层复制边界。
- `bamboo_engine/template/sandbox.py` 组织屏蔽名与导入模块；实际 Mako render 和组件调用发生在执行调用链内。它不是操作系统隔离沙箱。SubProcess/Process 命名也不证明有独立 OS 进程、资源限额或无网络权限；不能将 BKFlow 等下游项目的 Python 子进程执行器当成本仓实现。

检查模板安全须走真实公开渲染入口，用无破坏性副作用探针确认检查发生在执行之前，同时覆盖允许的变量、普通过滤器、不同白名单模式和旧表达式入口。AST 检查通过、历史修复 PR、有限绕过测试通过均不足以证明“完全安全”。禁止在审查中执行读取凭据、连接外网或破坏文件的 payload。

`pipeline/eri/imp/serializer.py` 的持久化格式优先 JSON，不能 JSON 序列化时使用 base64/pickle，并按 serializer 标记反序列化。`pipeline/eri/codec.py` 则是可配置 encoder/object_hook 的 JSON 编解码。两者不能随意替换；改变格式须考虑已有数据库行及恢复点。pickle 数据必须维持可信来源，不能将外部请求可控字节直接送入反序列化。仅发现 pickle 使用不能认定 PR 新增远程代码执行。

公开核心 API 没有宿主业务的用户/项目权限上下文；评审对外暴露接口须追踪宿主鉴权。`pipeline/contrib/engine_admin/views.py` 使用可选 `PIPELINE_ENGINE_ADMIN_API_PERMISSION` 回调；是否配置、是否挂载、宿主登录控制均需证据。不要把节点 ID 或 version 当作权限，也不要仅凭核心函数没有 request 参数就报告越权。

## 6. 事务、恢复与可选能力

- `bamboo_engine/interrupt.py`、`bamboo_engine/eri/models/interrupt.py` 保存 execute/schedule 关键点、运行版本和已经完成的 handler 结果。`pipeline/eri/imp/interrupt.py` 当前将 Django OperationalError/InternalError 视作中断错误。修改恢复点字段时检查序列化兼容、旧消息反序列化、状态已写但 checkpoint 未写、组件已执行但结果未持久化等窗口。
- 恢复路径可复用已执行结果，跳过组件重复调用；新加副作用不能放在未受相应恢复点约束的位置。数据库事务、Celery 重试和外部系统写入不是同一原子操作，不能承诺 exactly-once。
- `pipeline/eri/models.py` 中 State/Data/ExecutionData 的 node_id 唯一、Schedule 的 `(node_id,version)` 唯一、ContextValue 的 `(pipeline_id,key)` 唯一属于持久化契约。更改键长、约束、默认值、索引或序列化标记须同时看迁移、旧数据和并行写入。
- rollback 位于 `pipeline/contrib/rollback/`，核心配置默认关闭，需安装 app、迁移并配置 worker/队列。TOKEN 模式沿受 token 限制的路径执行回退；ANY 模式跳转/清理执行信息而不调用节点 rollback 方法。具体边界以该分支 `api.py`、`handler.py`、`graph.py` 为准；文档见 `docs/user_guide/rollback.md`。
- timeout/timer、node_finish 信号与预约 rollback 可能在节点结束或异常时竞争。涉及它们的修改应核对根/子流程、version、任务重复触发及接入配置，不能仅验证 happy path。

## 7. 测试入口与证据边界

| 改动类型 | 本仓入口 | 证据边界 |
| --- | --- | --- |
| 核心状态/调度/处理器 | 根 `tox.ini`；`tests/engine/`、`tests/handlers/`、`tests/interrupt/`、`tests/eri/` | 根 tox 使用 `poetry run coverage run -m pytest tests -vv --disable-pytest-warnings`。mock runtime 的单测不证明数据库竞争或消息重投安全。 |
| 变量/模板/图校验 | `tests/test_context.py`、`tests/template/test_template.py`、`tests/validator/`、`tests/builder/` | Mako 测试已有过滤器副作用、允许过滤器、白名单、format 绕过相关回归。新增安全结论须证明真实 render 行为。 |
| Django 包单元测试 | `.github/workflows/runtime_pipeline_unittest.yml`；`runtime/bamboo-pipeline/pipeline/tests/` | CI 在 test 工程复制两包源码后执行 `manage.py test pipeline.tests`，使用 MySQL。旧表达式测试在 `pipeline/tests/core/data/test_expression.py`。 |
| 新 ERI 集成 | `.github/workflows/runtime_pipeline_end_to_end_test.yml`；`runtime/bamboo-pipeline/test/eri_imp_test_use/tests/` | 测试目录有 control、execution、data_transfer、advanced、hook、chaos 等；CI 需 MySQL、Redis、RabbitMQ、迁移与可响应的 Celery worker。 |
| 旧引擎集成 | `.github/workflows/pipeline_end_to_end_test.yml`；`runtime/bamboo-pipeline/test/pipeline_test_use/tests/` | 同样需真实服务；与新 ERI 集成用例是两套入口。 |

当前 `.github/workflows/pr_check.yml` 触发 master/develop PR 的 lint、核心单测、运行时单测和两组集成测试。核心矩阵为 Python 3.6.12/3.7.16；运行时矩阵还列 Django 2.2/3.0，但安装命令是 `Django>矩阵值`，不能把矩阵标签当作最终版本。按目标分支 workflow 及安装日志确认真实版本，不假定 LTS 自动具有相同检查。

CI 将源码复制到 `runtime/bamboo-pipeline/test/`；本地复用测试环境时检查复制的代码是否最新，避免测试旧副本。SQLite 成功不能替代 MySQL 行锁/事务行为；单个 pytest 子集、全部 CI、包构建、包源可解析、宿主部署和业务验收是不同层次，报告必须分别描述。

## 8. 版本与发行审查

入口是 `docs/release_process.md`、`.github/workflows/engine_python_package_poetry.yml`、`.github/workflows/runtime_pipeline_python_package_poetry.yml`。核心版本需同步根 pyproject 与 `bamboo_engine/__version__.py`；运行时版本需同步自身 pyproject 与 `pipeline/__init__.py`。运行时依赖调整还需核对 `runtime/bamboo-pipeline/poetry.lock`。

核心以 `bamboo-engine-v*.*.*` tag 发行，运行时以 `bamboo-pipeline-v*.*.*` tag 发行。运行时依赖新的核心版本时，先确认核心发行包在包源可解析，再发行运行时；tag 名称、提交中的版本、wheel/sdist 元数据应一致。根目录测试使用新核心源码通过，不证明已发布的运行时可以解析它声明的依赖。审查任务本身不授权创建 tag、发布、合并或修改业务环境。
