# Change Workflow

Use this workflow for features, defect fixes, refactoring, tests, documentation,
configuration, and any other request that changes repository content.

Lifecycle:

```text
intake -> context_ready -> acceptance_defined -> implementing -> verifying
       -> reviewing -> completed
```

The runtime must not allow completion without non-empty acceptance criteria,
passing verification evidence, and a completed self-review.

## Intake

- Preserve the user's requested outcome verbatim in the task record.
- Identify explicit constraints, excluded work, compatibility requirements, and
  externally visible effects.
- Inspect the working tree and note pre-existing changes that must be preserved.

## Context ready

- Read the project contract, project notes, relevant knowledge, nearest existing
  implementation, callers, tests, and affected public interfaces.
- Determine whether changed files will be generated, protected, or governed by
  special verification rules.
- For a defect, reproduce it or establish the strongest available failing
  evidence before editing. For a refactor, identify behavior that must remain
  unchanged. For a feature, find the closest established pattern and all
  affected states, errors, and compatibility boundaries.
- Choose the smallest complete change. Record important assumptions and risks.

## Acceptance defined

Write observable, testable acceptance criteria to the active task's
`acceptance.md`. Include:

- required behavior and important error or boundary behavior;
- behavior that must remain unchanged;
- required generated artifacts or documentation updates;
- the verification evidence expected from the project contract.

Criteria such as "code looks good" or "tests pass" are insufficient on their
own. They must say what user- or system-visible result is being proven.

## Implementing

- Follow existing architecture, naming, typing, error handling, and test style.
- Work in complete, reviewable slices. Re-read a shared file immediately before
  editing if concurrent changes are possible.
- Change generation inputs or generators, not declared generated outputs.
- Add or update focused tests at the level most likely to catch regression.
- Keep behavior changes separate from unrelated cleanup.
- Do not bypass errors, disable checks, reduce assertions, or broaden ignore
  rules merely to obtain a passing result.

## Verifying

Run the changed-file selector after the implementation is complete:

```sh
./aiw verify --changed
```

The selected set must be non-empty for a change task. If it is empty, the
project contract is incomplete: add or correct an evidence-based verification
rule, validate the contract, and run verification again.

Start with focused checks when useful for iteration, but final evidence must
cover every command selected by the contract. Investigate failures; do not
re-run an unchanged failing command without a reason. Record the commands,
outcomes, durations, and relevant output in the task's verification evidence.

## Reviewing

Inspect the complete diff and acceptance criteria. Check, as applicable:

- correctness, boundary and error paths, and regression coverage;
- all callers, types, schemas, migrations, generated consumers, and docs;
- security, privacy, destructive behavior, concurrency, and performance;
- compatibility and rollback implications;
- accidental secrets, debug code, unrelated formatting, or user-work loss.

Write the result to the active task's `review.md`. Fix actionable findings and
repeat affected verification before completion. "No actionable findings
remain" is valid only after inspecting the final diff.

## Completed

Complete only when every acceptance criterion is met, required verification is
recorded and passing, self-review is recorded, and no unexplained failure or
temporary workaround remains. Archive the task when no further work is needed.

Report what changed, the evidence actually run, and any residual risk. Do not
commit, push, deploy, or publish unless separately authorized.
