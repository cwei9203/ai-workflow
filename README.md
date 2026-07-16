# AI Workflow

一套面向 Codex、Claude Code 和其他 coding agent 的约束式开发工作流。

它不依赖一段越来越长的系统提示词，而是把开发规则拆成四个可以审查和执行的层次：

| 层次 | 作用 |
| --- | --- |
| Workflow kernel | 定义分析、修改、评审和知识沉淀的生命周期 |
| Project contract | 声明项目命令、路径边界、生成规则和验证映射 |
| Runtime | 执行初始化、诊断、任务状态和验证门禁 |
| Host adapters | 让 Codex 与 Claude Code 进入同一套项目工作流 |

初始化之后，项目规则保存在仓库内，而不是某个 Agent 的个人配置中。Codex 读取 `AGENTS.md`，Claude Code 读取 `CLAUDE.md`，两者最终都会进入 `.ai-workflow/workflow/entry.md`。

## 能解决什么问题

- Agent 修改代码前没有读取项目约束；
- README、提示词和 CI 使用不同的构建或测试命令；
- 验证通过后继续改代码，却仍然声称验证有效；
- 受保护文件或生成文件被直接修改；
- 一次性调试结论被自动沉淀成长期知识；
- Codex 与 Claude Code 各自维护一套重复且逐渐分叉的规则。

## 环境要求

- Python 3.9 或更高版本；
- Git；
- Codex CLI 或 Claude Code，仅在采用对应插件安装方式时需要。

核心运行时只使用 Python 标准库。目标项目可以使用任意语言和构建系统。

## 安装

### 方式一：安装为 Codex Plugin

注册 GitHub Marketplace，然后安装插件：

```sh
codex plugin marketplace add cwei9203/ai-workflow --ref main
codex plugin add ai-workflow@cwei-ai-workflow
```

重新打开 Codex 任务后，可以直接对 Agent 说：

```text
Use $development-workflow to initialize this repository and complete onboarding.
```

插件提供工作流 Skill；项目初始化完成后，真正的约束保存在目标仓库中，因此其他没有安装插件的协作者仍可通过 `AGENTS.md` 和 `./aiw` 使用工作流。

### 方式二：安装为 Claude Code Plugin

```sh
claude plugin marketplace add cwei9203/ai-workflow
claude plugin install ai-workflow@cwei-ai-workflow
```

重新启动 Claude Code，然后请求：

```text
Use the development-workflow skill to initialize this repository and complete onboarding.
```

Claude Code 插件还会注册一个只读 `SessionStart` Hook。它只检查是否存在待审核的知识候选并提醒 Agent，不会自动修改知识库或产品代码。

### 方式三：只安装 `aiw` CLI

不使用插件系统时，可以直接从 GitHub 子目录安装 Python 包：

```sh
python3 -m pip install "git+https://github.com/cwei9203/ai-workflow.git#subdirectory=plugins/ai-workflow"
```

然后初始化任意已有仓库：

```sh
aiw init /path/to/existing-repository
```

也可以不安装 Python 包，直接克隆后运行：

```sh
git clone --depth 1 https://github.com/cwei9203/ai-workflow.git
./ai-workflow/plugins/ai-workflow/aiw init /path/to/existing-repository
```

Windows 可以使用：

```powershell
py -m pip install "git+https://github.com/cwei9203/ai-workflow.git#subdirectory=plugins/ai-workflow"
aiw init C:\path\to\existing-repository
```

## 初始化后会生成什么

```text
target-repository/
├── .ai-workflow/
│   ├── project.json          # 项目命令、路径和验证契约
│   ├── project-notes.md      # 项目目的、架构和关键语义
│   ├── workflow/             # 通用工作流内核
│   ├── knowledge/            # 长期知识和候选决策台账
│   ├── tasks/                # 可恢复的任务证据
│   └── runtime/              # 项目本地运行时
├── AGENTS.md                 # Codex 薄入口
├── CLAUDE.md                 # Claude Code 薄入口
├── aiw                       # macOS/Linux 入口
└── aiw.cmd                   # Windows 入口
```

初始化不会覆盖 `AGENTS.md` 或 `CLAUDE.md` 中已有的项目内容，只会维护一个带边界标记的入口块。重复执行 `aiw init` 会刷新工作流内核和运行时，同时保留项目契约、项目知识及入口块之外的内容。

## 首次项目接入

`aiw init` 只写入能够从仓库直接证明的事实。首次打开项目后，Agent 需要执行 `.ai-workflow/workflow/onboard.md`：

1. 阅读 manifest、CI、架构文档和源码/测试结构；
2. 补全项目目的、架构边界和关键约束；
3. 登记真实、非交互式的构建、测试、lint 和类型检查命令；
4. 将文件 glob 映射到必须运行的验证命令；
5. 标记受保护路径、生成路径及对应生成输入；
6. 运行严格诊断和验证选择预览；
7. 执行 `./aiw project complete` 完成接入。

接入完成前，运行时会阻止正式工作流任务启动。

## 日常使用

### 诊断项目配置

```sh
./aiw doctor
./aiw doctor --strict
./aiw project show
```

### 创建并推进修改任务

```sh
./aiw task start "Add user search" --kind change
./aiw task status
./aiw task advance
```

Change 生命周期为：

```text
intake
  → context_ready
  → acceptance_defined
  → implementing
  → verifying
  → reviewing
  → completed
```

任务不能跳过状态。完成 Change 任务至少需要：

- 可观察的验收条件；
- 根据当前 diff 选择并通过的验证命令；
- 验证后未发生新的产品改动；
- 对最终 diff 的评审记录。

### 运行验证

```sh
./aiw verify --changed --dry-run
./aiw verify --changed
./aiw verify --all
```

`verify --changed` 会读取 Git 的 staged、unstaged 和 untracked 文件，根据 `project.json` 选择必要命令，并检查：

- 受保护路径是否被修改；
- 生成输出是否缺少对应输入变化；
- 生成命令是否先于普通检查执行；
- 验证结果是否仍与当前工作区指纹一致。

### 完成和归档任务

```sh
./aiw task advance completed
./aiw task archive
```

归档后的 Analyze、Change 和 Review 任务会成为潜在知识来源。

## 知识沉淀

查看尚未裁决的知识候选：

```sh
./aiw knowledge status
```

如果任务产生了稳定、可复用且有证据的项目知识：

1. 按 `.ai-workflow/workflow/learn.md` 审核来源任务；
2. 将经验写入 `.ai-workflow/knowledge/learnings.md`；
3. 在条目的 `Source tasks` 中准确引用任务 ID；
4. 登记发布决定：

```sh
./aiw knowledge mark TASK_ID published
```

如果只是一次性问题，没有长期价值：

```sh
./aiw knowledge mark TASK_ID dismissed --reason "One-off external service outage"
```

设计上，Hook 只负责发现候选，不能直接发布或驳回知识。语义判断必须经过 Learn 工作流；命令、路径保护和验证映射则应更新到机器可执行的 `project.json`，而不是复制到知识 prose 中。

## 旧 Copilot 工作流迁移

先预览候选：

```sh
./aiw migrate-copilot
```

确认后执行：

```sh
./aiw migrate-copilot --apply
```

执行时会先备份到 `.ai-workflow/migrations/`，再删除能够明确识别的旧 Copilot 文件。普通 CI、团队文档、知识库及无法确认归属的文件不会被删除。

## 更新和卸载

### Codex

```sh
codex plugin marketplace upgrade cwei-ai-workflow
codex plugin remove ai-workflow@cwei-ai-workflow
codex plugin add ai-workflow@cwei-ai-workflow
```

### Claude Code

```sh
claude plugin marketplace update cwei-ai-workflow
claude plugin update ai-workflow@cwei-ai-workflow
```

卸载：

```sh
claude plugin uninstall ai-workflow@cwei-ai-workflow
```

### CLI

```sh
python3 -m pip install --upgrade "git+https://github.com/cwei9203/ai-workflow.git#subdirectory=plugins/ai-workflow"
python3 -m pip uninstall ai-development-workflow
```

卸载插件或 Python 包不会删除已经初始化到业务仓库中的 `.ai-workflow/`、`AGENTS.md` 管理块或项目知识。

## 仓库结构

```text
.
├── .agents/plugins/marketplace.json   # Codex Marketplace
├── .claude-plugin/marketplace.json    # Claude Code Marketplace
├── plugins/ai-workflow/               # 插件与 Python 运行时
└── .github/workflows/ci.yml           # 自动测试与打包验证
```

插件内部设计和更完整的项目接入说明见：

- [插件技术说明](plugins/ai-workflow/README.md)
- [项目接入指南](plugins/ai-workflow/docs/adoption.md)
- [工作流规范](plugins/ai-workflow/docs/specification.md)
- [验证报告](plugins/ai-workflow/VERIFICATION.md)

## 本地开发

```sh
git clone https://github.com/cwei9203/ai-workflow.git
cd ai-workflow/plugins/ai-workflow
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/validate-dual-host-plugin.py
python3 -m pip wheel --no-deps .
```

当前测试覆盖初始化幂等性、入口内容保护、状态机门禁、Git 特殊路径、受保护/生成文件规则、知识候选裁决、Hook 只读行为以及完整 Change 生命周期。

## 许可证

[MIT](LICENSE)
