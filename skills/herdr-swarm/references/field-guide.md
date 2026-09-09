# Field guide (stigmergy memory)

`.field-guide/` at the repository root is memory the swarm leaves behind for itself: agents shape the environment, the environment shapes the next agent. The location and entry rules match the herdr-dispatch convention, so single jobs and swarm leaves share one memory.

## What gets written

Only **surprises** — things the next worker would not predict from the spec or the code alone:

- Environment quirks (tool versions, build flags, CI oddities)
- Non-obvious invariants that cost someone a debugging session
- Approaches that looked right but failed, and why

Model weights are frozen: the guide is the only place learned knowledge persists across the swarm. Routine information, re-statements of the spec, and status updates do not belong there.

## Rules

- Entries are append-only: nobody edits or deletes existing entries. Stale entries get a dated one-line correction from the captain, never a rewrite.
- One short file per topic (`build-quirks.md`, `test-harness.md`, …). A new entry that grows past ~30 lines gets split by the captain.
- Every leaf brief lists which guide files are required reading. A worker that hits an unrecorded surprise notes it in its deliverable under `## field guide additions`; the captain transcribes those into the guide at merge time. Workers never write to the guide directly — the captain curates, so the guide never accumulates noise.
- Entries cite what happened and where (paths, error strings), not opinions.

## Lifecycle

The guide belongs to the repository, not to one swarm run. Leave it in place after the swarm ends; it is most valuable to the next task in the same codebase, and to single herdr-dispatch jobs, which use the same convention.
