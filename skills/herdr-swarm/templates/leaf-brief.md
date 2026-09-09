# Leaf brief template

The captain fills one of these per leaf, saves it to `.herd-dispatch/jobs/<name>/input.md`, and dispatches with herdr-dispatch `assign --worktree --message-file <path>`. Everything the worker needs to know is in this file or in the required reading — the worker must never need to ask.

```markdown
# <leaf name>

## Goal
<One sentence: the verifiable output of this leaf.>

## Required reading
- .herd-swarm/decisions.md
- .field-guide/<relevant files, if any>

## Ownership
You may create or modify only:
- <path or glob>
- <path or glob>

Do not touch:
- <shared files, captain-owned files, frozen paths>
If you believe one of those must change, report the needed change in your deliverable instead of changing it.

## Contract (frozen)
<The interface this leaf exposes to other leaves: names, signatures, file formats.
Do not change it. If it is wrong, report the problem and stop.>

## Task
<The actual work, decomposed enough to execute but not so much that it dictates implementation.>

## Deliverable
Write your answer to `.herd-dispatch/jobs/<name>/result.md` containing:
- changed files and how to verify them
- open questions or needed decisions (do not guess them)
- any file you consider bloated or conflict-prone
- field guide additions: surprises worth recording for later workers
```
