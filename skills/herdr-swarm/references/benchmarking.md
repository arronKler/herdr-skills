# Benchmarking a swarm

When the task has checkable ground truth (test suite, spec conformance, numeric target), run the swarm against a held-out evaluation — the way Cursor's SQLite swarm was graded against sqllogictest without the agents ever knowing.

## Rules

1. **Never mention the eval in any brief, `decisions.md` entry, or field-guide file.** The swarm optimizes whatever it is told; a leaked eval turns into a shortcut farm.
2. Grade from the main tree after each merge, never inside a leaf's worktree mid-run.
3. Record score + time per wave in `.herd-swarm/runs.md`. Score is the progress metric; commit counts and churn are not evidence of progress (busywork signature).
4. **Suspicious curves get inspected**: a jump much faster than the curve's established rate, or a sudden step after no visible structural change, triggers a manual read of the run and the diff before trusting the number. Check for memorized expected outputs, hardcoded answers, and tests disabled or weakened.
5. The eval may be disclosed to the human at the end; it stays hidden from workers for the lifetime of the run.

## When there is no ground truth

Fall back to review + human checkpoints: pick 2–3 wave boundaries where the human looks at the tree and the decisions log. Do not invent a synthetic eval mid-run — a benchmark made up while the swarm watches is indistinguishable from a leaked one.
