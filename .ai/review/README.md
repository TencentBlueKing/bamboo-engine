# GLM-5.3 自动代码审查

本仓库使用 CodeBuddy 公司通道 `glm-5.3-ioa`。审查仅辅助人工决策，不替代既有 lint、单测、发布检查或真实集成验收。

## 触发与权限

- PR 新建、更新、重新打开或退出草稿时运行；PR 作者和事件发起人都必须拥有仓库 write/maintain/admin 权限。外部贡献者的 PR 会明确跳过，可由维护者人工审查；不能靠加标签放开凭据。
- 管理员在 GitHub 仓库 Actions Secrets 中配置 `CODEBUDDY_API_KEY`，值为公司 CodeBuddy API key；不使用 OpenClaw OAuth token。缺少或失效会失败，不发布“无问题”结论。密钥到期前由维护者更新该 Secret。
- `pull_request_target` 只执行目标分支代码和知识库。当前接入 PR 合入前，不能据此 PR 的检查证明自动模型审查已生效；后续 PR 事件才会加载本方案。
- 不创建自动合入、自动批准或发布任务；暂不把 AI 判断设为必需合入门禁。

## LTS 与开发分支覆盖

工作流、审查脚本和知识规则必须分别合入每条需要接收 PR 的目标分支。主分支已经接入、工作流没有 `branches` 过滤，都不意味着其他 LTS 自动获得这套检查。新建或保留维护分支时，应将这六份接入文件一起补齐，并按照该分支的真实模块、版本和兼容约束调整知识与规则。

仓库级 `CODEBUDDY_API_KEY` Secret 由同一仓库的分支共享，无需逐分支创建。合入后用新的维护 PR 验证 `review` 调用模型、`publish` 发布对应 head 的评论；仅 `validate` 通过只能证明 runner 单测通过。已有 PR 不会因目标分支补接入而自动重跑，需要后续更新、重新打开或退出草稿事件。

## 审查上下文

- `.ai/review/knowledge.md`：仓库模块、依赖与协议事实。
- `.ai/review/rules.md`：按改动范围追踪的约束及证据要求。
- 每次针对 merge-base 到事件 head 的完整 diff；不依赖单次 webhook 的增量片段。模型可以用 Read/Glob/Grep 阅读 head 的普通文件快照，不能执行 PR 脚本、测试或修改文件；StructuredOutput 只提交结构化结果。
- PR 中的新规则仅作为待审查内容，本轮使用已合入目标分支的规则，避免 PR 自行改变审查标准。
- 不加载项目/用户 CodeBuddy 设置或 MCP；Read/Glob/Grep 使用快照目录的默认读取边界，目录外请求在非交互模式下拒绝；快照排除符号链接、Git/Agent 配置和大于 250 KB 的文件。过滤清单进入提示和结果边界，diff 仍保留相关改动。diff 超过 400 KB、差异定位结构超过 96 KB 或快照超过 60 MB 会失败并提示拆分，避免把不完整阅读报成全量通过。

## 输出与故障处理

最多报告 8 个有触发条件、调用链、影响和修复建议的 P1/P2 问题，用中文输出到一条可更新的 PR 评论，附本次 commit 的源码行链接。仅允许引用本次新增/删除行。重复运行更新同一评论；发布前重新检查 head 和 base，过期结果不发布。

模型任务只有仓库只读权限；评论发布在独立 job 中持有 PR 写权限。CLI 原始输出由私有临时文件接收，避免进程退出时尚未写完的管道造成长 JSON 截断；文件关闭即删除。仅传递验证后的结果和提交元数据，不上传原始对话、源码快照或配置目录。Actions 固定到提交 SHA，CLI 固定 `@tencent-ai/codebuddy-code@2.147.0`。

模型调用、JSON 校验或凭据失败会使检查失败；查看失败步骤处理，不能据“没有评论”认定通过。更新依赖或约束后先跑下列验证，再用正常业务 PR 检查结果。AI 输出有误由人工判定，修正知识规则后随 PR 更新重跑。

## 验证

```bash
python3 -I -m unittest discover -s .github/scripts -p test_ai_review.py -v
```

该测试不需要模型凭据，覆盖 diff 定位、返回结构、链接与提及转义、路径穿越/符号链接、export-ignore/export-subst、特殊文件名、过期结果和评论更新；同时验证模型进程不继承 GitHub 凭据、runner 命令文件和外部工具授权，以及超过 1 MB 的 CLI JSON 在立即退出后仍完整读取。工作流的 `pull_request` 校验 job 不接收模型 Secret；业务代码应另按知识库列出的现有测试执行。

参考：[GitHub Actions 安全指南](https://docs.github.com/en/actions/reference/security/secure-use)。
