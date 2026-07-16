# Review Workflow

Use this workflow for a findings-only review of code, a proposed change, a task
plan, or repository state.

Lifecycle:

```text
intake -> context_ready -> reviewing -> completed
```

Review is read-only by default. Do not implement fixes, rewrite reviewed files,
or change product behavior unless the user explicitly converts the request to a
change task.

## Intake

- Define the review target, baseline, scope, and requested emphasis.
- Identify whether the user wants code correctness, security, architecture,
  test adequacy, migration safety, performance, or general review.
- Preserve any supplied acceptance criteria and distinguish them from your own
  recommendations.

## Context ready

- Read the project contract and relevant knowledge.
- Inspect the full changed region plus enough surrounding implementation,
  callers, types, tests, and configuration to reason about behavior.
- Determine the intended baseline. Do not assume an arbitrary branch or commit.
- Run read-only or non-mutating checks only when they materially strengthen the
  review and are safe in the current working tree.

## Reviewing

Prioritize defects that are concrete, introduced or exposed by the reviewed
work, and actionable. For each finding include:

- severity and concise title;
- exact file and smallest useful line or symbol range;
- triggering inputs or conditions;
- observable consequence;
- why existing checks do not prevent it, when relevant;
- the direction of a fix without unnecessarily prescribing an implementation.

Focus first on correctness, data loss, security, breaking compatibility,
concurrency, and missing verification. Avoid style-only findings unless style
causes ambiguity or violates an enforced project rule.

## Completed

List findings in descending severity, then summarize remaining test or evidence
gaps. If no actionable findings exist, say so explicitly and still identify any
meaningful residual risk or checks that were not run.
