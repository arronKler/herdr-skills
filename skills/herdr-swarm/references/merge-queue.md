# Merge queue and arbitration

Leaves work in separate worktrees (herdr-dispatch `--worktree`). Merges happen on the main tree, one at a time, driven by the captain.

## Order

Merge in dependency order (contracts consumed before contracts provided), then risk order: the leaf touching the most shared-adjacent paths goes later, when more of the tree is settled. Never merge two leaves concurrently, even with disjoint paths.

## Merge steps

For each collected leaf:

1. Read the deliverable. Unresolved decision questions go to `decisions.md` first — before the merge, so the merged code already matches the decision.
2. Apply the worktree to the main tree (merge, cherry-pick, or file copy — whatever fits the repo's git state; the captain does this itself).
3. Build and test the main tree. Green → record `merged` in `tree.md`. Red → one arbitration round, below.
4. Captain-owned file requests from the deliverable are applied now, by the captain.

## Neutral arbiter

When the merge fails, or when the merged code collides with an already-merged leaf, the captain does **not** fix it inline and never asks either author to judge their own conflict. Dispatch a fresh arbiter via herdr-dispatch `assign --worktree`:

- Kind different from both conflicting authors.
- Role: sole objective is a fair merge preserving **both** intents; no new features, no refactors beyond the conflict.
- Input: both sides' deliverables, the relevant `decisions.md` entries, and the conflicting paths. Nothing else — no author transcripts.
- One arbitration round. If the arbiter also fails, the captain merges the paths manually or re-plans the split; the swarm stops burning tokens on a conflict it cannot settle.

## Bloat and ossification

- **Oversized files**: a leaf's deliverable may report a file as bloated (many small additions, constant conflicts). The captain records it, freezes the path (no further leaf may touch it), and dispatches a dedicated splitter leaf whose only job is restructuring that file against the frozen contract.
- **Deliberate breaking changes**: a leaf that believes a core contract must change reports it instead of changing it. The captain records the decision, then lets the compiler/tests propagate the breakage — each failing leaf reads the decision entry and adapts. No silent core edits.

## Freeze rule

A frozen path stays frozen until the splitter leaf merges. Any leaf brief written during the freeze must list the path under "do not touch".
