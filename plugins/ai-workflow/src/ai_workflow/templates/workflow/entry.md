# Workflow Entry

This repository uses the AI Development Workflow. This file is the single
entry point for every coding agent. Project-specific facts live in
`../project.json`; do not add them to this workflow kernel or to agent adapter
files.

## Start here

1. Read `../project.json` and `../project-notes.md`.
2. If `onboarding.status` is not `complete`, follow `onboard.md` before doing
   any other work. Do not silently mark onboarding complete.
3. Read `../knowledge/index.md`, then load only the knowledge relevant to the
   current request.
4. Inspect the current working tree. Preserve unrelated edits and untracked
   files.
5. Classify the request and follow exactly one primary workflow:
   - read-only investigation or explanation: `analyze.md`;
   - source, test, documentation, or configuration changes: `change.md`;
   - findings-only assessment: `review.md`;
   - promotion of durable lessons from completed work: `learn.md`.

If the user changes the requested outcome, reclassify the task. If a request
combines modes, use `change.md` as the primary workflow and apply the relevant
analysis or review rules inside it.

## Shared rules

- Treat the user's requested outcome and the repository's current state as
  authoritative. Do not invent project facts or commands.
- Gather evidence before editing. Read the closest existing implementation,
  callers, tests, and relevant project instructions.
- Keep changes scoped to the requested result. Do not overwrite unrelated
  work, generated outputs, vendored code, or protected paths.
- Use commands declared in `project.json`. Do not substitute guessed commands.
- Obey generation rules: change the declared inputs or generator, then run the
  declared generator and consumer verification. Never hand-edit a generated
  output unless the contract explicitly permits it.
- Scale planning and validation with risk. A small documentation correction
  can stay lightweight; a cross-module or high-risk change needs explicit
  acceptance criteria, staged implementation, and broader evidence.
- Do not commit, push, publish, deploy, delete user data, or perform other
  external or destructive actions unless the user explicitly authorizes them.
- Record uncertainty as uncertainty. Separate observed facts, inferences, and
  unresolved questions.
- A command that was not run is not passing evidence. If required validation
  cannot run, report the exact blocker and residual risk.

## Task state

For work that is more than a trivial read-only answer, use the local `./aiw`
runtime to create and advance a task record. The runtime enforces the lifecycle
defined by the selected workflow and stores active work under
`../tasks/active/`. Keep acceptance, verification, and review evidence in that
record so another session can resume without reconstructing intent.

```sh
./aiw task start --kind <analyze|change|review|learn> "<task title>"
./aiw task status
./aiw task advance <next-state>
./aiw task archive
```

Only one task can be active. Advance after the evidence for the current state
has been recorded; archive only after the runtime accepts `completed`.

Do not force a state transition. A failed gate means the task remains in its
current state until the missing evidence is supplied.

## Completion

Before reporting completion:

1. compare the result with the original request and recorded acceptance
   criteria;
2. run the project-contract verification required for the actual changed
   files;
3. inspect the final diff for omissions, unrelated edits, secrets, debug
   residue, and accidental generated-file changes;
4. record verification and self-review evidence where the workflow requires
   it;
5. report the outcome, evidence actually obtained, and any remaining risk.
