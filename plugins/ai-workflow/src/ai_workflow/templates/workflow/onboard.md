# Project Onboarding

Use this workflow when `../project.json` has an onboarding status other than
`complete`. Its purpose is to adapt the reusable workflow to an existing
repository without changing product behavior.

Onboarding has two passes. The initializer has already performed deterministic
discovery; this workflow performs semantic completion. Discovery hints are
evidence to review, not facts to trust blindly.

## 1. Establish the repository baseline

- Inspect manifests, lockfiles, workspace definitions, build files, CI
  configuration, developer documentation, repository-level agent instructions,
  source and test layouts, scripts, generators, and representative modules.
- Inspect the working tree and preserve all pre-existing modifications.
- Read every item in `context.read_first`. Correct entries that are missing,
  obsolete, generated, or not useful as durable context.
- Review `discovery.evidence`, `discovery.warnings`, and
  `onboarding.review_notes`. Confirm each
  discovered fact from its source and retain unresolved uncertainty as a review
  note.

Do not run installation, migration, formatting, build, or test commands merely
to discover whether they exist. Prefer manifests and existing CI/developer
instructions as evidence.

## 2. Complete project semantics

Edit `../project.json` and `../project-notes.md` to describe this repository,
not an idealized project. At minimum, supply:

- the project's purpose and user-visible responsibilities;
- languages, platforms, source roots, test roots, and documentation roots;
- architecture boundaries and dependency constraints an agent must preserve;
- the smallest useful set of documents to read before common work;
- protected or vendored paths that agents must not edit;
- generated paths, their source inputs, generators, and required consumer
  checks;
- exact, non-interactive commands for build, test, lint, type checking,
  generation, and other validations that actually exist;
- changed-file rules mapping repository-relative glob patterns to named
  commands;
- default checks that apply to every change.

Use `project.json` for machine-enforced facts. Use `project-notes.md` for short
human-readable context, architectural rationale, and caveats that do not fit a
command or path rule.

## 3. Contract quality rules

- Every command name referenced by a verification or generation rule must be
  defined in `commands`.
- Commands must run from the repository root and work without an interactive
  shell prompt.
- Paths and patterns are repository-relative and use `/` separators.
- A protected path must not be contradicted by an instruction to modify it.
- Each generated output must identify both its inputs and its generator.
- Each significant source/test/documentation area must match at least one
  meaningful verification rule or an intentional default command.
- Remove all placeholder text and examples that are not true of this project.
- Do not weaken a known project check just to make onboarding pass.

## 4. Validate without changing product state

Run:

```sh
./aiw doctor --strict
./aiw verify --all --dry-run
```

Resolve every strict diagnostic. Inspect the dry-run selection and confirm that
the command order and coverage match the contract. The dry run is not evidence
that commands pass; it only validates selection.

When the contract is complete, run:

```sh
./aiw project complete
```

This command must refuse completion while strict diagnostics remain. After it
succeeds, re-read `workflow/entry.md`, classify the user's request, and continue
with the selected workflow.
