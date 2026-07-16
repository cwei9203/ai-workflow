# AI Development Workflow Specification

## Purpose

This project defines a reusable development workflow for coding agents. It is independent of any specific language, framework, repository, or AI vendor. A target repository supplies its own project facts through a project contract.

## Design Boundaries

The workflow is split into four responsibilities:

1. **Workflow kernel** — task kinds, lifecycle states, evidence requirements, and completion rules.
2. **Project contract** — exact commands, protected/generated paths, project context, and changed-file verification rules.
3. **Runtime** — initialization, discovery, diagnostics, task transitions, migration, and verification execution.
4. **Thin adapters** — `AGENTS.md` for Codex-compatible agents and `CLAUDE.md` for Claude Code.

The adapters contain no project rules. They point agents to the installed workflow and project contract.

## Installation Contract

Running `aiw init TARGET` must:

- inspect the existing repository without requiring it to be clean;
- create `.ai-workflow/` without deleting business files;
- discover common languages, manifests, commands, source/test/documentation roots, and generated paths;
- create an editable `.ai-workflow/project.json`;
- install workflow documents and a local runtime;
- add or replace only the managed block in `AGENTS.md` and `CLAUDE.md`;
- create root `aiw` and `aiw.cmd` launchers;
- be idempotent;
- never create `.github/copilot-instructions.md` or other Copilot adapters.

Existing content outside managed blocks must remain byte-for-byte unchanged.

## Two-Pass Project Onboarding

### Pass 1: deterministic discovery

The initializer identifies evidence that can be derived safely from repository files. It must record where each fact came from and flag uncertainty instead of inventing commands.

### Pass 2: agent semantic completion

When `project.onboarding.status` is not `complete`, the entry workflow requires the agent to:

1. inspect manifests, architecture documents, CI configuration, source/test layout, generated artifacts, and existing developer instructions;
2. correct discovered facts;
3. add project purpose, architecture boundaries, protected paths, generation triggers, and exact verification rules;
4. remove all placeholder text;
5. run `./aiw doctor --strict` and a verification dry run;
6. mark onboarding complete using `./aiw project complete`.

## Task Kinds and Lifecycles

### Analyze

`intake → context_ready → analyzing → reporting → completed`

Analyze tasks are read-only unless the user explicitly changes their scope.

### Change

`intake → context_ready → acceptance_defined → implementing → verifying → reviewing → completed`

A change task cannot complete without recorded acceptance criteria, passing verification evidence bound to the current product diff, and a completed self-review.

### Review

`intake → context_ready → reviewing → completed`

Review tasks report findings and do not mutate source files unless explicitly requested.

### Learn

`intake → context_ready → extracting → publishing → completed`

Learn tasks promote durable lessons with source-task references. They do not alter product source code.

## Verification

The project contract maps path patterns to named commands. `aiw verify --changed` obtains changed and untracked files from Git, selects all matching commands, executes each command in the repository root, and records command, duration, exit status, and outcome.

Before execution it rejects changes to protected paths. A generated output may
not change without a matching declared generator input, and a matching
generation rule places its generator command before ordinary verification
checks.

`aiw verify --all` executes every declared generator, default command, and rule-referenced command. Commands that are declared but not used by a generation or verification gate are not executed. `--dry-run` displays the selection without execution.

Any required command failure makes verification fail. An empty verification selection is not passing evidence for a change task.

Changed paths are read from Git with NUL-delimited raw output so quoted,
Unicode, whitespace, and newline-containing names cannot bypass matching.

## Legacy Copilot Migration

Legacy cleanup is explicit. `aiw migrate-copilot --apply` or `aiw init --remove-legacy-copilot` must:

- identify files whose path clearly names the legacy Copilot workflow, plus root adapters and known job prompts that match the complete legacy protocol signature;
- copy them into a timestamped backup inside `.ai-workflow/migrations/`;
- write a manifest containing original and backup paths;
- delete originals only after successful backup;
- leave unrelated `.github` content unchanged.

Without `--apply`, migration reports candidates and performs no mutation.

## Completion Evidence

The implementation is complete only when automated tests and an end-to-end fixture prove installation, idempotency, preservation, migration backup, project discovery, strict diagnostics, lifecycle gates, verification selection, failure propagation, and the absence of Copilot adapters.
