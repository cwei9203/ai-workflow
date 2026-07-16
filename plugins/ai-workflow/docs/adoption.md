# 在存量项目中采用 AI Development Workflow

本文面向已有代码、历史约定和团队开发流程的仓库。目标是在不重写业务文件、不覆盖现有 agent 指令的前提下，安装通用工作流，并由 agent 补齐每个项目独有的事实。

## 采用后的职责边界

- `.ai-workflow/workflow/` 是可升级的通用内核，不放项目路径或命令。
- `.ai-workflow/project.json` 是项目命令、路径和验证规则的机器可执行来源。
- `.ai-workflow/project-notes.md` 保存简短的项目目的、架构说明和非结构化注意事项。
- `.ai-workflow/knowledge/` 保存按需读取的领域知识与有来源的长期经验。
- `AGENTS.md` 和 `CLAUDE.md` 只包含一个受管理入口块；原有团队内容继续保留。
- `./aiw` 与 `aiw.cmd` 是 agent、开发者和 CI 的共同执行入口。

## 阶段 0：确定采用边界

初始化不要求干净工作区，但在团队仓库中建议先了解现有改动和指令来源。确认：

- 谁维护项目契约；
- 哪些平台必须支持；
- 哪些目录是生成、vendored、外部同步或严禁自动修改的；
- 当前 CI 中哪些命令是完成改动的最低门槛；
- 是否要迁移旧的专用 agent 文件。

初始化器不会 commit、push、部署，也不会因工作区有改动而清理文件。

## 阶段 1：安全初始化

安装工具并在任意位置指定目标仓库：

```sh
python3 -m pip install /path/to/ai-development-workflow
aiw init /path/to/repository
```

Windows 可将安装命令中的 `python3` 换成 `py`，并传入普通 Windows 路径。初始化完成后，进入目标仓库使用 `aiw.cmd`；macOS/Linux 使用 `./aiw`。`aiw.cmd` 优先探测 PATH 中的 `python`，失败时回退到 Windows Python Launcher `py -3`，并在局部环境中恢复调用方目录和变量。

初始化器会：

1. 扫描 manifest、锁文件、常见目录和已有开发文档；
2. 创建 `.ai-workflow/`、本地运行时和两个根启动器；
3. 生成状态为 `needs_review` 的 `project.json`；
4. 在 `AGENTS.md`、`CLAUDE.md` 中添加或替换唯一的受管理块；
5. 保留受管理块以外的字节内容和所有业务文件。

重复运行同一命令应得到相同结果，而且不会覆盖已经人工维护的 `project.json`。初始化后先查看：

```sh
./aiw doctor
```

非严格模式用于显示发现结果和待接入状态；此时项目尚未完成语义接入。

## 阶段 2：让 Agent 补齐项目内容

使用 Codex、Claude Code 或其他遵循 `AGENTS.md` 的 agent 打开目标仓库，并提出正常的分析或开发请求。入口会先检查接入状态，然后执行 `.ai-workflow/workflow/onboard.md`。

Agent 应基于证据检查以下信息。

### 项目身份与结构

- `project.summary` 是否准确描述项目提供的能力；
- 语言、运行平台和 manifest 是否完整；
- source/test/documentation roots 是否真实且足够；
- `context.read_first` 是否只包含稳定而高价值的入口文档；
- `context.architecture_boundaries` 是否说明组件职责和允许的依赖方向。

### 编辑边界与代码生成

- `paths.protected` 是否覆盖 vendored、第三方、镜像或不可自动修改内容；
- `paths.generated` 是否覆盖所有生成输出；
- 每条 `generation.rules` 是否把输入、输出和已声明的生成命令关联起来；
- 生成后是否有验证真实消费者的命令，而不只检查生成器退出码。

### 命令与验证

- `commands` 中每个命令是否存在、非交互，并从仓库根目录可执行；
- `verification.default` 是否包含所有改动都必须运行的低成本门槛；
- `verification.rules` 是否覆盖源码、测试、文档、schema、迁移和生成输入等重要区域；
- 每个 `require` 名称是否都在 `commands` 中定义；
- 是否存在过宽规则造成无意义全量验证，或过窄规则留下空选择。

机器可执行规则写入 `project.json`；原因、术语和架构语义写入 `project-notes.md`。不要把相同命令复制到多个 agent 入口。

完成编辑后运行：

```sh
./aiw doctor --strict
./aiw verify --all --dry-run
./aiw project complete
```

严格诊断必须无错误，dry run 中的选择和顺序必须符合项目实际。dry run 只证明规则可选择，不证明命令已经通过。`project complete` 成功后，agent 才继续原始任务。

严格诊断还会确认 manifest、源码/测试/文档根目录及 `context.read_first` 中的精确路径确实存在，避免薄入口要求未来 Agent 读取不存在的项目上下文。

如果 strict doctor 报告仍有可明确识别的旧 Copilot 工作流文件，先按本文后面的迁移步骤预览、备份并清理；接入完成命令不会越过这些候选文件。清理必须保持显式，不能为了通过诊断删除普通 `.github` 内容。

## 阶段 3：小范围试运行

建议先选择两类低风险任务：

1. 一个只读 Analyze 任务，用来验证上下文索引是否足够；
2. 一个局部 Change 任务，用来验证验收条件、changed-file 选择、实际命令执行和自审门槛。

试运行后检查：

- agent 是否读取了正确的项目知识，而不是加载全部文档；
- `./aiw verify --changed --dry-run` 是否选中预期命令；
- 实际 `./aiw verify --changed` 是否在仓库根目录成功执行；
- 失败是否正确阻止 Change 任务完成；
- 验证后再次修改产品文件是否会因 diff 指纹变化而要求重新验证；
- 任务记录是否足以让另一个会话继续工作。

如果选择为空或遗漏检查，应修订项目契约，而不是在 prompt 中临时提醒。

## 阶段 4：接入团队门禁

Agent 自觉执行是第一层，CI 才是最终门禁。推荐让 CI 使用相同本地入口：

```sh
./aiw doctor --strict
./aiw verify --all
```

`verify --all` 执行默认命令和所有规则引用的命令，适合不依赖本地 Git diff 的合并门禁。将这两个步骤设为必过检查后，Markdown 规则、项目契约、agent 本地验证和服务端门禁使用同一个事实来源。

CI 的 Python 运行环境和项目依赖准备仍由项目自身负责；把这些真实前置条件记录在现有 CI 或开发文档中，不要硬编码进通用工作流。

## 阶段 5：沉淀长期知识

只有完成且有验证证据的任务才能成为 Learn 的来源。`./aiw knowledge status` 列出尚未裁决的归档任务；长期经验写入 `.ai-workflow/knowledge/learnings.md` 并引用 source task ID，然后用 `knowledge mark ... published` 登记。没有长期价值的候选必须以带原因的 `dismissed` 登记。命令、路径保护和验证映射应直接更新 `project.json`。

插件的 SessionStart Hook 只读检测候选并提醒，不直接写 `learnings.md` 或台账。这样可以自动避免遗忘，同时把“是否稳定、是否应推广”的语义判断保留在 Learn 审核阶段。

定期删除过时知识、合并重复规则，并在架构变化后重新运行 strict doctor 和验证 dry run。不要把原始日志、秘密、个人数据或一次性调试过程沉淀为长期上下文。

## 显式迁移旧专用文件

新工作流不会安装 Copilot adapter。若目标仓库存在旧文件，先预览：

```sh
./aiw migrate-copilot
```

确认候选列表后才执行：

```sh
./aiw migrate-copilot --apply
```

执行时会先将候选复制到 `.ai-workflow/migrations/<timestamp>/`，写入原路径与备份路径 manifest，全部备份成功后才删除原件。识别范围包括明确命名的旧文件、具有旧路由签名的根 Agent 入口以及具有完整旧协议签名的已知 job prompts。明确以 `copilot` 命名的旧构建/调试包装器也会被备份后删除，因此执行前应在预览列表中确认其替代命令已经能写入新项目契约。普通 `.github/workflows/`、无法明确识别的团队 prompt、未以 Copilot 命名的项目工具和知识文档不会被删除；这些项目资产应在 onboarding 时迁移到项目契约或新的 knowledge 索引。旧根入口会在迁移后重建为薄适配入口。

迁移备份默认由 `.ai-workflow/.gitignore` 排除，避免把可能包含旧环境信息的文件意外提交；确认迁移结果后再按团队保留策略处理本地备份。

首次安装也可显式合并执行：

```sh
aiw init /path/to/repository --remove-legacy-copilot
```

不传该选项时，初始化不会清理旧文件。

## 更新与团队自定义

再次运行 `aiw init TARGET` 可以刷新工作流内核、本地运行时、启动器和两个受管理入口块。人工维护的 `project.json`、项目知识和受管理块之外的现有说明必须保留。

团队若需要增加约束，优先判断它属于哪一层：

- 可执行项目事实：修改 `project.json`；
- 项目架构或术语：修改 `project-notes.md` 或新增 knowledge 文档并更新 index；
- 从任务证据得到的长期教训：通过 Learn 工作流更新 `learnings.md`；
- 对所有项目都成立的生命周期规则：才考虑升级工作流内核。

这样可以避免每个项目复制并逐渐分叉一套庞大 prompt。

## 故障处理

### Strict doctor 报 onboarding 未完成

不要直接修改 status。先消除 summary、review notes、未知命令引用、占位文本和验证覆盖等诊断，再运行 `./aiw project complete`。

### Change 验证没有选中命令

检查 Git 是否能看到相关修改，然后为对应路径补充 verification rule 或合理的 default command。空选择不能作为 Change 的通过证据。

### 初始化后原说明看似变化

检查 `AGENTS.md` 或 `CLAUDE.md` 的受管理标记。初始化器只应替换该块；若块外内容变化，停止采用并保留现场进行排查。

### 迁移候选包含不相关文件

不要使用 `--apply`。迁移预览是安全边界，应先修正候选识别或手工确认更小范围。
