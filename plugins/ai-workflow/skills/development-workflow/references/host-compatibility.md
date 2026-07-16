# Host compatibility

## Shared layer

Both hosts use the same skill, workflow kernel, project contract, and local `aiw` runtime. Initialized repositories contain thin `AGENTS.md` and `CLAUDE.md` adapters pointing to the same `.ai-workflow/workflow/entry.md`.

## Codex

- Manifest: `.codex-plugin/plugin.json`
- Skill UI metadata: `skills/development-workflow/agents/openai.yaml`
- The validated Codex plugin schema does not declare lifecycle hooks. Run `./aiw knowledge status` explicitly; the workflow and knowledge gate do not depend on a hook.

## Claude Code

- Manifest: `.claude-plugin/plugin.json`
- Skill discovery: `skills/`
- Hook context output at SessionStart: plain stdout

The Claude hook descriptor uses `${CLAUDE_PLUGIN_ROOT}`. Its script uses only Python's standard library and keeps a Codex-compatible JSON output branch for environments that invoke it directly.

## Degraded operation

If lifecycle hooks are disabled or Python is unavailable, the workflow remains usable through the repository adapters and local runtime. Run `./aiw knowledge status` explicitly; Hook reminders are convenience, not correctness enforcement.
