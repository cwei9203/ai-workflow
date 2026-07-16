# Analyze Workflow

Use this workflow for explanation, investigation, architecture questions, and
status reports that do not require repository changes.

Lifecycle:

```text
intake -> context_ready -> analyzing -> reporting -> completed
```

## Intake

- Restate the concrete question and the decision the answer should support.
- Record explicit scope, constraints, and requested output form.
- Default to read-only. Do not edit source, configuration, workflow, or task
  artifacts beyond the lifecycle record unless the user expands the scope.

## Context ready

- Read the project contract and only the relevant knowledge entries.
- Locate authoritative code, configuration, tests, history, or runtime evidence.
- Define what evidence would answer the question and stop gathering unrelated
  context once that threshold is met.

## Analyzing

- Trace behavior from entry point to outcome instead of inferring from names.
- Cross-check important claims against tests, consumers, or executable evidence
  when proportionate to the question.
- Label observations, inferences, and unknowns distinctly.
- For comparisons, use the same criteria for every option and make trade-offs
  explicit.

## Reporting

- Lead with the answer or conclusion.
- Cite concrete repository paths and symbols when they make the result
  verifiable.
- Explain material limitations, contradictions, and residual uncertainty.
- Do not describe a check as executed unless it was actually run.

The task is complete when the original question is answered with sufficient
evidence and no source mutation was introduced.
