# Knowledge Index

This index routes agents to durable project knowledge. It is intentionally
small: read it at task start, then load only the documents relevant to the
request.

## Sources of truth

| Need | Source |
| --- | --- |
| Commands, protected/generated paths, and verification rules | `../project.json` |
| Project purpose, boundaries, and onboarding caveats | `../project-notes.md` |
| Reusable lessons derived from completed tasks | `learnings.md` |
| Published/dismissed decision per archived source task | `ledger.json` |
| Workflow lifecycle and completion gates | `../workflow/entry.md` and the selected workflow |

Do not duplicate executable project constraints in knowledge prose. Update the
project contract so agents and automation use the same rule.

## Topic documents

Add project-owned knowledge documents below only when they provide durable,
task-relevant context that cannot be discovered cheaply from code. For each
document, describe when an agent should read it.

| Document | Read when |
| --- | --- |
| `learnings.md` | A task touches an area covered by a durable lesson, or a learn task is consolidating evidence. |

<!-- Add rows during project onboarding or later learning work. -->

## Maintenance

- Prefer links to authoritative source and test locations over copied code.
- Remove or supersede stale material when architecture changes.
- Never store credentials, private user data, raw logs, or speculative notes.
- Keep `ledger.json` machine-managed through `./aiw knowledge mark`; do not use
  it as a prose knowledge store.
- Keep routing descriptions concrete enough that an agent can decide whether a
  document is relevant without opening every file.
