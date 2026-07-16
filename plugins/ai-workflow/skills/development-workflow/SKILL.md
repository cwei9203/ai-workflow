---
name: development-workflow
description: Adopt or operate the AI Development Workflow in a code repository. Use when initializing a repository for Codex and Claude Code, implementing or reviewing changes under repository constraints, running evidence-based verification, migrating legacy Copilot instructions, or reviewing archived tasks for durable project knowledge.
---

# Development Workflow

Use the plugin's executable workflow instead of reproducing its rules in chat. The same repository state and gates apply to Codex and Claude Code.

## Locate the plugin and repository

Treat the directory containing this skill's parent `skills/` directory as `PLUGIN_ROOT`. Treat the nearest ancestor containing `.ai-workflow/project.json` as `PROJECT_ROOT`.

If the repository is not initialized, run:

```sh
"$PLUGIN_ROOT/aiw" init "$PROJECT_ROOT"
```

Then follow `$PROJECT_ROOT/.ai-workflow/workflow/onboard.md`. Do not mark onboarding complete until project commands, path rules, verification mappings, and project notes are supported by repository evidence.

## Operate an initialized repository

1. Read `AGENTS.md` or `CLAUDE.md`, then `.ai-workflow/workflow/entry.md`.
2. Inspect `.ai-workflow/project.json` and only the knowledge routed by `.ai-workflow/knowledge/index.md`.
3. Select analyze, change, review, or learn based on user intent.
4. Start and advance the task with `./aiw task ...`; keep evidence in its task directory.
5. For changes, define acceptance criteria before implementation and run `./aiw verify --changed` before review.
6. Archive only a completed task.

The runtime is a gate, not a substitute for engineering judgment. Never invent project commands or weaken a failing check to make a task pass.

## Handle durable knowledge

Run `./aiw knowledge status` to list archived tasks awaiting a decision. A SessionStart hook may remind the agent, but it is deliberately read-only.

- Publish only stable, scoped, evidenced lessons using `.ai-workflow/workflow/learn.md`.
- Cite every source task ID in `knowledge/learnings.md`, then run `./aiw knowledge mark TASK_ID published`.
- If no durable lesson exists, record the reason with `./aiw knowledge mark TASK_ID dismissed --reason "..."`.
- Never let a hook write formal knowledge, edit product code, or silently dismiss a candidate.

Read [host-compatibility.md](references/host-compatibility.md) when installing, packaging, or diagnosing host-specific behavior.
