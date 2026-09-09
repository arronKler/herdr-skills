# Task tree and ownership

The task tree is the captain's decomposition of the goal. Root = goal; leaves = dispatchable work units. Depth is at most 2: root → leaf. Mid-level groupings are just organization in `tree.md`, not extra agents.

## Writing a leaf

A leaf is ready to dispatch when its brief has all five parts of [../templates/leaf-brief.md](../templates/leaf-brief.md):

1. **Goal** — one sentence of verifiable output ("crate X parses all SELECT forms listed in spec §Y").
2. **Ownership** — explicit allow-list of paths the leaf may create or modify, plus an explicit "do not touch" note for anything shared (e.g. `Cargo.toml` root workspace entries, which the captain owns).
3. **Contract** — frozen interface: names, signatures, file formats other leaves will depend on. Contracts are decided by the captain and never left "to be agreed by the workers".
4. **Required reading** — `decisions.md` and any field-guide entries that matter here.
5. **Deliverable** — the file the worker writes to report back: changed files, how to verify, open questions, and bloat reports.

## Ownership discipline

- Ownership sets of concurrently `working` leaves must be disjoint. Serialized leaves may reuse paths, but the later brief must name the merged predecessor so the worker knows the file state changed.
- Files everyone needs (root manifests, config, registries) are **captain-owned**: workers report the needed change in their deliverable; the captain applies it during merge.
- If decomposition forces shared ownership, that is a tree bug. Restructure: split the file into per-leaf modules plus a captain-owned glue file.

## Frozen contracts

Contracts change only through `decisions.md`. When the captain revises a contract mid-run, every affected live leaf gets a `send` from herdr-dispatch naming the decision entry — do not let a worker discover the change from a merge failure.

## Tree file format

`.herd-swarm/tree.md` is plain markdown, captain-maintained:

```markdown
# Swarm: <goal>

## Leaves
- [ ] impl-parser   owner: paths src/parser/**        status: working   worktree: yes
- [x] impl-lexer    owner: paths src/lexer/**         status: merged    review: rev-lexer
```

Update it at every state transition. It is what the human and the next captain turn read to recover the swarm's state.
