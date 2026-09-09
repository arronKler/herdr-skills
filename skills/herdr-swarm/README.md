# Herdr Swarm

An agent skill for running a **small agent swarm** (3–8 workers) through [Herdr](https://github.com/herdrdev/herdr): decompose a big goal into an ownership-split task tree, dispatch leaves through the [herdr-dispatch](../herdr-dispatch/README.md) skill, merge them one at a time with neutral arbitration, and accumulate shared memory across runs.

The protocol distills Cursor's research blog *Agent swarms and the new model economics* (July 2026). Key positions carried over, at Herdr scale:

- **Scalability comes from context efficiency, not parallelism.** Planners never implement; workers never plan. Each agent's context stays clean.
- **Swarm failures are coordination failures.** Split brain, planner feuds, merge wars, oversized files, ossification — each has a named countermeasure in [SKILL.md](SKILL.md).
- **Redundancy over perfection.** Reviews stack low-correlated perspectives instead of seeking one perfect reviewer.
- **Agents shape the environment.** The field guide records surprises so the next worker's path is shorter.
- **Hide the eval.** Ground-truth suites are never mentioned to workers; suspicious score jumps are inspected by hand.

What this is **not**: Cursor's scale (hundreds of agents, ~1,000 commits/sec, custom VCS). Herdr panes are heavyweight; this skill targets minute-scale swarms with single-digit concurrency over plain git worktrees. The coordination lessons transfer; the infrastructure does not need to.

## Install

Install both skills with the [Vercel skills CLI](https://github.com/vercel-labs/skills) — they live in the same repository:

```bash
npx skills add arronKler/herdr-skills
```

That installs every skill in the repository (herdr-dispatch and herdr-swarm). To install only the swarm stack explicitly:

```bash
npx skills add arronKler/herdr-skills --skill herdr-swarm
npx skills add arronKler/herdr-skills --skill herdr-dispatch
```

herdr-swarm requires herdr-dispatch in the same agent and the runtime described there (macOS/Linux, Python 3.9+, Herdr on PATH, the captain inside a Herdr pane).

## Use it with your agent

```text
Use herdr-swarm to implement docs/spec.md: decompose it into a task tree,
fan out the leaves, merge them one by one, and report scores after each wave.
```

The captain follows [SKILL.md](SKILL.md): doctor-checks via herdr-dispatch, plans the tree with disjoint ownership, dispatches `assign --worktree` waves, runs the merge queue, and finishes with a review pass.

## Layout

- [SKILL.md](SKILL.md) — protocol, roles, hard rules
- [references/task-tree.md](references/task-tree.md) — decomposition and ownership discipline
- [references/merge-queue.md](references/merge-queue.md) — merge order, neutral arbiter, bloat and breaking changes
- [references/field-guide.md](references/field-guide.md) — stigmergy memory rules
- [references/review.md](references/review.md) — review perspectives and stacking
- [references/benchmarking.md](references/benchmarking.md) — hidden-eval grading
- [templates/leaf-brief.md](templates/leaf-brief.md) — per-leaf brief template

## License

[MIT](LICENSE).
