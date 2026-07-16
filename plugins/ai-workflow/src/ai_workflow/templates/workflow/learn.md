# Learn Workflow

Use this workflow to promote durable knowledge from completed, evidenced tasks.
It is not a substitute for finishing a change and does not modify product
source code.

Lifecycle:

```text
intake -> context_ready -> extracting -> publishing -> completed
```

## Intake

- Run `./aiw knowledge status` from the repository root and select one or
  more pending, completed source tasks.
- State the scope of learning: repository architecture, coding constraints,
  testing behavior, operational caveats, or workflow improvement.
- Do not infer a durable rule from an abandoned experiment or unverified result.

## Context ready

- Read each source task's request, acceptance criteria, decisions,
  verification evidence, review, and final outcome.
- Compare the lesson with current code, project contract, and existing knowledge.
- Treat user corrections and repeated failure modes as strong signals, but
  verify that they still apply.

## Extracting

A publishable lesson must be:

- actionable in a future task;
- supported by named source-task evidence;
- scoped to the repository or a clearly named subsystem;
- stable enough to outlive the original implementation detail;
- non-duplicative and non-contradictory with current instructions.

Exclude one-off debugging transcripts, speculative preferences, secrets,
personal data, obsolete workarounds, and facts already expressed better by code
or the machine-enforced project contract.

## Publishing

- Put executable commands, path protections, and verification mappings in
  `../project.json`, not prose learnings.
- Put durable project guidance in `../knowledge/learnings.md` using its entry
  format and include every source task ID.
- Update `../knowledge/index.md` only when adding a new knowledge document or
  changing its routing description.
- Merge overlapping entries rather than creating near-duplicates. Preserve
  source references and mark superseded guidance explicitly.
- Validate any project-contract edits with `./aiw doctor --strict` and a
  verification dry run.
- After the source task ID appears in `learnings.md`, run
  `./aiw knowledge mark TASK_ID published` for every published source.
- When the evidence contains no durable lesson, do not manufacture one. Run
  `./aiw knowledge mark TASK_ID dismissed --reason "..."` with a concise,
  auditable reason.

The task is complete when every candidate has an explicit ledger decision and
every published statement is current, scoped, traceable, and placed in the
correct source of truth.
