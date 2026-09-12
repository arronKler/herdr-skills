---
name: herdr-swarm
description: Run a small agent swarm (3-8 workers) through Herdr for large tasks that one agent cannot hold in context — goal decomposition into an ownership-split task tree, merge queue with neutral arbitration, shared decision log, field guide memory, hidden benchmarks. Use when the user wants a swarm, fan-out implementation of a big spec, multi-agent build from a spec, or says swarm/蜂群. Built strictly on top of the herdr-dispatch skill.
license: MIT
metadata:
  version: "0.2"
  runtime: herdr
---

# Herdr Swarm

Small-scale swarm protocol, distilled from Cursor's "Agent swarms and the new model economics" (Jul 2026): scalability comes from **context efficiency and coordination discipline**, not raw parallelism. This skill is the orchestration layer; it never touches `herdr` directly — all spawning, collecting, and messaging goes through the **herdr-dispatch** skill's verbs (`doctor`, `assign`, `watch`, `collect`, `send`, `handoff`, `stop`).

## Preconditions

1. herdr-dispatch must be installed and its `doctor` must pass. If not, stop and tell the human.
2. The task must be big enough that one agent would lose context: multiple modules, a full spec, hours of work. For a single-file fix, use herdr-dispatch directly instead.
3. `--worktree` isolation is mandatory for every implementation leaf. Read-only leaves may share the main tree.

## Roles

- **Captain (this session) = planner.** Decomposes, decides, arbitrates merge order, reviews. The captain never implements code itself and never hand-waves a design decision into a brief — undecided design questions stop the tree until the captain decides them (or asks the human).
- **Workers = executors.** One leaf each. Workers do not plan, do not dispatch, and do not talk to each other. All cross-worker information flows through files the captain points at.
- Depth is at most 2 (captain → leaf). Nested captains are forbidden by herdr-dispatch; do not ask for them.

## Scale limits

- 3–8 leaves total in the task tree. More means the captain becomes the bottleneck; split the goal into sequential swarms instead.
- At most 10 workers `working` at once (herdr-dispatch cap). Dispatch what fits, supervise with `watch`, collect settled jobs, then dispatch the next wave.

## Model mix

Follow the blog's model economics: very little of a big task truly needs frontier intelligence — the initial decomposition, the design decisions, the key trade-offs. Everything else is execution against a settled spec, which cheaper models do well:

- **Planning**: the strongest model available — that is this captain session.
- **Implementation leaves**: prefer fast, cheap kinds (see herdr-dispatch routing defaults). Once the captain has collapsed uncertainty into frozen contracts, leaf work is mechanical.
- **Arbiter and reviewers**: cheap kinds first; only bump up if a round fails.

All-frontier runs cost several times more for roughly the same quality; a second-rate planner that reasons efficiently can beat a pricier one by generating less work.

## Protocol

### 1. Plan the tree

Decompose the goal recursively. Every leaf brief (see [templates/leaf-brief.md](templates/leaf-brief.md)) must carry:

- **Ownership**: the exact directories/files this leaf may create or modify. Ownership sets must be **disjoint** across concurrent leaves. Two leaves deciding the same thing = split brain; the fix is to move the decision to the captain, not to add a second owner.
- **Contract**: the interface this leaf exposes to others (function signatures, file formats, module names), frozen in the brief before any worker starts.
- **Required reading**: paths to `decisions.md` and `.field-guide/` entries relevant to this leaf.

If two leaves would need the same file, either serialize them (second leaf starts after the first merges) or split the file now, not during the merge.

### 2. Open the swarm state

Create once, at the repository root:

- `.herd-swarm/decisions.md` — the shared design record. The captain appends one dated entry per decision. Workers read it; workers never write to it. If a worker needs a decision, it reports the question in its deliverable and stops short of guessing.
- `.field-guide/` (repository root) — stigmergy memory, see [references/field-guide.md](references/field-guide.md).
- `.herd-swarm/tree.md` — the current task tree: leaves, owners, status (`planned` / `working` / `merged` / `failed`).
- `.herd-swarm/runs.md` — only when there is an eval; see [references/benchmarking.md](references/benchmarking.md).

### 3. Dispatch wave by wave

For each ready leaf: build the brief with the template, then use herdr-dispatch `assign --worktree` (async) — never `handoff` for implementation leaves; the captain must stay free to arbitrate. After dispatch, supervise every leaf with bounded `watch` calls. A prompt stall is unconfirmed delivery, not evidence that it is safe to resend. Keep the captain active until collection and integration are handled, unless a real continuation mechanism is armed or the user pauses the task.

### 4. Collect and merge in order

Monitor all leaves together using herdr-dispatch `watch` on a 30–60s cadence. Collect each ready leaf with `collect --name` without waiting on a slower sibling. Then process collected leaves one at a time through the merge queue — see [references/merge-queue.md](references/merge-queue.md). Never merge two leaves concurrently, even if they own disjoint paths: the captain must see each merge result before deciding the next step.

### 5. Review

Default: one reviewer, a different kind from the author, via herdr-dispatch `handoff`, on the merged tree. For high-risk merges (core modules, many conflicts, oversized files touched), stack a second reviewer of a different kind; take the union of findings. See [references/review.md](references/review.md).

### 6. Finish

Update `tree.md`, write the final summary for the human, leave `.herd-swarm/` in place — the decision log and field guide are the point of keeping them. Stop workers only per herdr-dispatch cleanup rules.

## Failure modes to prevent

These are the swarm pathologies, with the protocol's countermeasure for each — details in the references:

| Pathology | Countermeasure |
|---|---|
| Split brain: two leaves build the same concept differently | Disjoint ownership; design decisions made and recorded by the captain only |
| Planner feud: workers re-litigating a shared file | `decisions.md` is the single source of truth; leaves read it before starting |
| Merge war: two workers fighting over one file | Merge queue + neutral arbiter worker |
| Oversized files: everyone appends, nobody trims | Workers report bloat; captain freezes the path and dispatches a splitter |
| Busywork: high commit churn, low progress | Score by benchmark and deliverables, never by activity; suspicious curves get a manual read of the run |

## Benchmarking a swarm

If the task has an evaluable ground truth, hold out the eval suite: never mention it in any brief, grade after each wave, and hand-inspect runs whose score jumps suspiciously. See [references/benchmarking.md](references/benchmarking.md).

## Hard rules

- All dispatch goes through herdr-dispatch verbs. No raw `herdr` commands.
- The captain never implements and never delegates a design decision.
- No two concurrent leaves share writable paths.
- No concurrent merges. No merges without a prior collect.
- Workers never dispatch, never edit `decisions.md`, never resolve their own merge conflicts.
