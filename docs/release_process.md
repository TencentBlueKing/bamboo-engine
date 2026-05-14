# 发包流程

本文档用于记录 `bamboo-engine` 与 `bamboo-pipeline` 的发包顺序。发包动作在目标发布仓库的 GitHub Actions 中触发，本地只做版本号、依赖、lock 文件和 tag 准备。

以下命令中的 `<remote>` 表示目标发布仓库对应的本地 Git remote 名称，请按当前机器的实际配置替换。

## 包与触发方式

- `bamboo-engine`
  - 代码位置：仓库根目录
  - 版本文件：`pyproject.toml`、`bamboo_engine/__version__.py`
  - 触发 tag：`bamboo-engine-v*.*.*`
  - GitHub Actions：`.github/workflows/engine_python_package_poetry.yml`
- `bamboo-pipeline`
  - 代码位置：`runtime/bamboo-pipeline`
  - 版本文件：`runtime/bamboo-pipeline/pyproject.toml`、`runtime/bamboo-pipeline/pipeline/__init__.py`
  - 依赖文件：`runtime/bamboo-pipeline/pyproject.toml`、`runtime/bamboo-pipeline/poetry.lock`
  - 触发 tag：`bamboo-pipeline-v*.*.*`
  - GitHub Actions：`.github/workflows/runtime_pipeline_python_package_poetry.yml`

## 发布前确认

1. 确认当前分支已同步目标发布仓库的 `master`：

   ```bash
   git fetch <remote> --tags
   git checkout master
   git pull --ff-only <remote> master
   ```

2. 根据合入内容确认发包范围：

   ```bash
   git diff --name-only <previous_release_commit> HEAD
   ```

3. 如果本次 `bamboo-pipeline` 依赖了新的 `bamboo-engine` 版本，必须先发布 `bamboo-engine`，等包源可用后再发布 `bamboo-pipeline`。

## bamboo-engine 发包

1. 修改根目录版本号：

   - `pyproject.toml`
   - `bamboo_engine/__version__.py`

2. 提交并推送到目标发布仓库的 `master`。

3. 确认远端不存在同名 tag：

   ```bash
   git ls-remote --tags <remote> 'refs/tags/bamboo-engine-vX.Y.Z'
   ```

4. 创建并推送 tag 触发 Actions：

   ```bash
   git tag bamboo-engine-vX.Y.Z
   git push <remote> refs/tags/bamboo-engine-vX.Y.Z
   ```

5. 等待 `Engine python package` workflow 成功，并确认 `bamboo-engine X.Y.Z` 已在包源可用。

## bamboo-pipeline 发包

仅当 `bamboo-engine` 新版本已经发布成功且包源可解析后，再进行 `bamboo-pipeline` 发包。

1. 修改 `bamboo-pipeline` 版本号：

   - `runtime/bamboo-pipeline/pyproject.toml`
   - `runtime/bamboo-pipeline/pipeline/__init__.py`

2. 如果依赖了新的 `bamboo-engine`，同步修改：

   - `runtime/bamboo-pipeline/pyproject.toml` 中的 `bamboo-engine = "^X.Y.Z"`
   - `runtime/bamboo-pipeline/poetry.lock` 中锁定的 `bamboo-engine` 版本

3. 在 `runtime/bamboo-pipeline` 目录更新 lock 文件：

   ```bash
   cd runtime/bamboo-pipeline
   poetry lock --no-update
   poetry check
   ```

4. 提交并推送到目标发布仓库的 `master`。

5. 确认远端不存在同名 tag：

   ```bash
   git ls-remote --tags <remote> 'refs/tags/bamboo-pipeline-vA.B.C'
   ```

6. 创建并推送 tag 触发 Actions：

   ```bash
   git tag bamboo-pipeline-vA.B.C
   git push <remote> refs/tags/bamboo-pipeline-vA.B.C
   ```

7. 等待 `Runtime Pipeline python package` workflow 成功，并确认 `bamboo-pipeline A.B.C` 已在包源可用。

## 注意事项

- tag 对应的提交中，包版本号必须与 tag 版本一致；只改 tag 不改版本文件，会导致 Actions 打出旧版本包。
- `bamboo-pipeline` 的 `poetry.lock` 必须随版本和依赖变更一起提交；否则本地开发、CI 验证和最终包依赖可能不一致。
- 如果 `bamboo-pipeline` 先于它依赖的 `bamboo-engine` 新版本发布，用户升级时可能出现依赖解析失败。
- 已经推送或发布过的异常版本不要复用。如果包已经发布，应提升到下一个版本号重新发布。
- 如果 tag 已推送但 workflow 尚未发布成功，应先取消对应 workflow，再根据实际情况删除远端 tag 或改用新版本号。
