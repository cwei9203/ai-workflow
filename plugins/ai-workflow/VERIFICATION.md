# Verification Report

Date: 2026-07-16

## Requirement audit

| Requirement | Evidence |
| --- | --- |
| Vendor-neutral workflow | The kernel contains only onboarding, analyze, change, review, and learn workflows. No Copilot adapter is installed. |
| Thin Codex and Claude entries | Installed `AGENTS.md` and `CLAUDE.md` contain one managed routing block and are 8 lines in a clean target. Existing CRLF content outside the block is byte-preserved. |
| Phased workflow | The runtime enforces task-specific ordered states, acceptance, verification, review, completion, and archive gates. |
| Existing-project entry | Both direct `aiw init TARGET` and wheel-installed `aiw init TARGET` were exercised successfully, including a target path containing spaces. |
| Project-specific completion | Deterministic discovery creates `needs_review`; strict contract, exact path, project-notes, and verification checks must pass before `project complete`. |
| Legacy cleanup | The real GacUI `.github` snapshot produced 20 legacy candidates. All were backed up and removed, zero candidates remained, while Guidelines and KnowledgeBase stayed present. |
| Codex/Claude plugin portability | Host manifests share one name, version, Skill directory, and runtime. Claude declares its SessionStart Hook; Codex keeps a validator-compatible manifest. Initialized repositories receive both thin adapters. |
| Knowledge promotion boundary | Archived non-Learn tasks become candidates; publication requires an exact source-task citation, dismissal requires a reason, and decisions cannot be silently overwritten. |
| Read-only Hook | Claude plain-text and Codex JSON context outputs were both exercised. The Hook leaves `ledger.json`, formal knowledge, and product source unchanged. |

## Automated tests

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 35 tests passed.

Coverage includes:

- idempotent installation and preservation of existing adapters;
- CRLF byte preservation and malformed-marker preflight;
- launcher and workflow-directory collision protection;
- legacy migration preview, backup, narrow allowlist, and thin-entry recreation;
- TypeScript/Node.js, Rust, and Go discovery;
- strict contract, project-note, generated-path, and repository-path validation;
- ordered task lifecycle and stale-verification fingerprint rejection;
- protected/generated path policies and generator ordering;
- Git staged, unstaged, untracked, Unicode, and newline-containing filenames;
- full onboarding → change → verification → review → completion → archive E2E.
- dual-host manifest/Hook wiring and environment-specific Hook output;
- knowledge candidate detection, citation-gated publication, reason-gated dismissal, and immutable decisions.

## Plugin and Skill validation

- The generated `development-workflow` Skill passes the Skill Creator validator.
- `scripts/validate-dual-host-plugin.py` passes shared identity, Hook-path, and SessionStart-only checks.
- The Codex manifest omits lifecycle hooks to remain compatible with the validated ingestion schema. Claude Code declares the read-only SessionStart Hook; Codex users invoke the same knowledge check through the Skill and `./aiw knowledge status`.

## Distribution test

A 0.2.0 wheel was built with Python 3.12 and installed into an isolated target whose path contained spaces. The installed package contained the runtime, all workflow resources, and the knowledge ledger template; `aiw init`, target-local `./aiw doctor`, and `./aiw knowledge status` succeeded.

## Remaining environment boundary

`aiw.cmd` has static and generated-content coverage for `python` probing, `py -3` fallback, `setlocal`, and `pushd/popd`, but was not executed on a real Windows host in this environment.
