# AI Development Workflow

一套可安装到存量代码仓库的、与具体 AI 厂商和技术栈无关的开发工作流。它把通用任务生命周期、项目独有事实和可执行验证拆开管理，让 Codex、Claude Code 及其他读取 `AGENTS.md` 的 coding agent 共用同一套约束。

这不是一个长提示词。工作流用 Markdown 解释执行顺序，用 `project.json` 声明项目事实，用本地 `aiw` 运行时检查状态和执行验证；插件 Hook 只承担非关键的只读提醒，即使 Hook 被禁用，核心门禁仍然成立。

## Codex 与 Claude Code 插件

本目录本身就是双宿主插件：Codex 使用 `.codex-plugin/plugin.json`，Claude Code 使用 `.claude-plugin/plugin.json`，两边共享 `skills/development-workflow/` 和同一套运行时。Claude Code 额外通过 `hooks/claude-hooks.json` 启用只读知识候选提醒；Codex 使用显式 `./aiw knowledge status`，核心门禁不依赖 Hook。插件负责“发现和调用能力”，初始化后的目标仓库仍通过 `AGENTS.md`、`CLAUDE.md` 和本地 `aiw` 保持可移植。

## 核心结构

| 层 | 职责 | 是否项目定制 |
| --- | --- | --- |
| Workflow kernel | analyze/change/review/learn 生命周期和完成门槛 | 否 |
| Project contract | 命令、架构边界、保护/生成路径、变更验证规则 | 是 |
| Runtime | 初始化、发现、诊断、任务状态、迁移和验证执行 | 否 |
| Thin adapters | 从 `AGENTS.md`、`CLAUDE.md` 指向统一入口 | 否 |

项目规则只维护在 `.ai-workflow/project.json` 和必要的项目知识中；两个 agent 入口不复制项目内容。

## 安装到已有项目

从本仓库直接运行入口即可把工作流接入目标项目：

```sh
/path/to/ai-workflow/aiw init /path/to/existing-repository
```

也可以先安装为系统命令，再传入目标仓库路径：

```sh
python3 -m pip install /path/to/ai-workflow
aiw init /path/to/existing-repository
```

Windows 可将安装命令中的 `python3` 换成 `py`，随后使用同一个 `aiw init` 全局入口。

初始化不要求工作区干净，并且可以重复运行。它会先从 manifest、锁文件、目录和现有文档中做确定性发现，再安装：

```text
target-repository/
├── .ai-workflow/
│   ├── project.json          # 可编辑的项目契约
│   ├── project-notes.md      # 项目语义和架构说明
│   ├── workflow/             # 通用工作流内核
│   ├── knowledge/            # 索引和长期经验
│   ├── tasks/                # 可恢复的任务证据
│   └── runtime/              # 本地运行时
├── AGENTS.md                 # 仅添加一个受管理的薄入口块
├── CLAUDE.md                 # 仅添加一个受管理的薄入口块
├── aiw                       # macOS/Linux 本地入口
└── aiw.cmd                   # Windows 本地入口
```

已有 `AGENTS.md` 和 `CLAUDE.md` 中受管理块以外的内容会原样保留；业务文件和无关 `.github` 内容不会被初始化器删除。

## 两阶段项目接入

### 第一阶段：确定性发现

`aiw init` 只记录能从仓库直接证明的事实，例如语言、manifest、已有脚本以及常见源码/测试目录。来源记录在 `discovery.evidence`，不确定项记录为 warning；工具不会猜测不存在的命令。

### 第二阶段：Agent 语义补全

首次在目标仓库中启动 agent 时，薄入口会引导它读取 `.ai-workflow/workflow/entry.md`。只要 `onboarding.status` 还不是 `complete`，agent 就必须执行 `workflow/onboard.md`：

1. 阅读 manifest、CI、架构文档、源码/测试布局和现有开发说明；
2. 校正发现结果，补充项目目的、架构边界、保护和生成规则；
3. 写入真实的非交互构建、测试、lint、类型检查等命令；
4. 将文件 glob 映射到必须执行的命令；
5. 运行严格诊断和验证选择预览；
6. 按需清理仍被识别到的旧专用工作流文件；
7. 通过 `./aiw project complete` 标记接入完成。

参考契约见 [examples/project.json](examples/project.json)，完整接入步骤见 [docs/adoption.md](docs/adoption.md)。

## 工作模式

| 模式 | 生命周期 | 默认是否修改产品代码 |
| --- | --- | --- |
| Analyze | intake → context_ready → analyzing → reporting → completed | 否 |
| Change | intake → context_ready → acceptance_defined → implementing → verifying → reviewing → completed | 是 |
| Review | intake → context_ready → reviewing → completed | 否 |
| Learn | intake → context_ready → extracting → publishing → completed | 否 |

Change 任务只有在以下证据齐全后才能完成：可观察的验收条件、非空且通过的项目验证、最终 diff 自审。

## 常用命令

在已经接入的目标仓库根目录运行本地入口：

```sh
./aiw doctor
./aiw doctor --strict
./aiw verify --changed --dry-run
./aiw verify --changed
./aiw verify --all
./aiw project complete
./aiw knowledge status
```

`verify --changed` 从 Git 的已修改和未跟踪文件计算需要执行的命令，按契约去重并记录命令、耗时、退出码和结果。Git 路径使用 NUL 分隔原始协议，因此中文、空格乃至换行文件名都不会逃过规则。生成输入变化时，生成命令会排在普通检查之前；受保护路径改动及没有对应输入的生成输出改动会被直接拒绝。任意必要命令失败即验证失败；Change 任务中“没有选中任何命令”也不是通过证据。通过结果会绑定当前产品 diff 指纹，验证后继续修改产品文件必须重新运行验证。`verify --all` 会运行所有声明的生成命令、默认检查和规则引用检查，但不会执行未被任何门禁引用的普通命令。

任务子命令用于创建、推进和归档带状态的工作记录。以 `./aiw --help` 和 `./aiw task --help` 显示的当前接口为准。

归档后的非 Learn 任务会成为知识候选。Claude Code 的 SessionStart Hook 只提醒存在候选，不自动发布；其他宿主显式运行 `./aiw knowledge status`。审核后，先让 `knowledge/learnings.md` 引用来源任务 ID，再执行 `./aiw knowledge mark TASK_ID published`；若没有稳定经验，则执行 `./aiw knowledge mark TASK_ID dismissed --reason "..."`。这条边界避免把偶然调试结论自动升级成长期约束。

## 旧工作流迁移

旧的 Copilot 专用文件不会成为新工作流的一部分。清理是显式、可预览且可恢复的：

```sh
./aiw migrate-copilot
./aiw migrate-copilot --apply
```

预览不会修改文件。`--apply` 只处理文件名能够明确识别的旧 Copilot 文件、带旧入口签名的 `AGENTS.md` / `CLAUDE.md`，以及带完整旧协议签名的已知 job prompts。它会先备份到 `.ai-workflow/migrations/<timestamp>/` 并写 manifest，备份成功后才删除原件。明确以 `copilot` 命名的旧构建/调试包装器也属于迁移候选；普通 CI、无法确认归属的团队 prompt、未以 Copilot 命名的项目工具、知识文档和其他 `.github` 文件保持不变。旧入口被清理后会立即重建为新的薄入口。也可以在首次安装时显式使用：

```sh
aiw init /path/to/existing-repository --remove-legacy-copilot
```

## 设计原则

- 通用流程只定义“何时做什么”，不包含语言、框架或仓库路径。
- 项目契约是命令和路径规则的唯一机器可执行来源。
- Agent 与 CI 应调用同一个 `aiw verify`，避免提示词与门禁分叉。
- 自动发现只记录证据；必须由 agent 或维护者完成语义判断。
- 初始化保持幂等，迁移保持显式，受管理块以外的用户内容保持不变。
- 不自动 commit、push、发布或部署。

## 本项目开发

本实现只依赖 Python 标准库，要求 Python 3.9 或更高版本。运行测试：

```sh
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

规范见 [docs/specification.md](docs/specification.md)。
