---
name: herdr-dispatch
description: Dispatch peer coding agents through Herdr using assign, handoff, and send_message. Use when inside a Herdr pane and the user wants Claude, Codex, Pi, omp, Grok Build, Cursor, or another CLI worker spawned, tasked, collected, or followed up. Triggers include herd-dispatch, assign a worker, handoff to Codex, send_message to a pane, fan-out agents, peer review across CLIs, grok-build worker, cursor-agent model.
license: MIT
metadata:
  version: "1.7"
  runtime: herdr
---

# Herdr Dispatch

Captain protocol for running other coding CLIs as workers inside Herdr. Call the bundled script. Do not improvise raw `herdr agent start` / `wait` / `prompt` sequences.

## Preconditions

1. Run `scripts/herd-dispatch doctor` first. It must report `"ok": true`, `"herdr": true`, and `self.pane_id`.
2. If doctor prints `"ok": false` for any reason (including `HERDR_ENV!=1`, missing verbs, or unresolved captain pane), stop. Show the JSON to the human. Do not debug by running raw `herdr agent` commands.
3. Never target the captain pane. The script refuses self-operations; do not bypass it.
4. Never run bare `herdr` (that attaches the TUI and hangs). Do not run bare `herdr agent` either; kinds come from doctor JSON or `herdr agent start --help`.
5. Workers must not dispatch further workers. Only the captain uses this skill.

## Tools

All verbs print JSON. Read `ok`, `name`, `status`, `deliverable`, `result_excerpt`, `error`.

`status` is the Herdr lifecycle: `idle`, `done`, `working`, `blocked`, or `unknown`. It is never `settled`.

`ok` means this turn of conversation settled, not that the work is good:

- `assign` / async `send`: `status` is `working`
- `handoff` / `collect --wait` / `send --wait`: `status` is `idle` or `done`

If `deliverable` is set, that file is the answer. `result_excerpt` is leftover pane chrome; `result.md` is the TUI dump. See [references/envelope.md](references/envelope.md).

`ok: true` with `status: unknown` is a script bug. Treat it as failure.

If `status` is `blocked` or `ok` is false, do not invent an approval. Show `result_excerpt` to the human.

| Verb | CAO equivalent | Blocks? | Use |
|---|---|---|---|
| `assign` | assign | until `working` | Fan-out independent work |
| `handoff` | handoff | until `idle`/`done`/`blocked` | Next step needs the worker output |
| `send` | send_message | optional | Follow up an existing worker |
| `collect` | inbox harvest | optional | Pull assign results later |
| `models` | — | no | List live model ids for one `--kind` |

Script path (resolve relative to this skill): `scripts/herd-dispatch`.

```bash
python3 "$SKILL_DIR/scripts/herd-dispatch" doctor
```

Replace `$SKILL_DIR` with this skill directory. A `herd-dispatch` on PATH is also fine.

## Assign (async)

```bash
python3 scripts/herd-dispatch assign \
  --kind codex \
  --role implementer \
  --name impl-auth \
  --worktree \
  --message-file .herd-dispatch/jobs/impl-auth/input.md
```

Returns once the worker is `working` (not when the task is finished). Then end the captain turn and harvest later.

```bash
python3 scripts/herd-dispatch collect --name impl-auth --wait --timeout 900000
```

`collect --wait` is the same kind of wait as handoff — only blocking if this captain's command tool can sit that long (see Handoff).

Parallel assign is allowed only when tasks do not share a writable tree. Use `--worktree` for any implementation.

If assign returns `idle`/`done`, the prompt never started. One `send` retry, then stop.

## Handoff (sync)

```bash
python3 scripts/herd-dispatch handoff \
  --kind claude \
  --role reviewer \
  --name rev-auth \
  --message-file .herd-dispatch/jobs/rev-auth/input.md
```

The script waits until `idle`, `done`, or `blocked`. That wait is real only when this captain's command tool timeout is ≥ `--timeout`. Grok Build (and any captain whose shell calls background around two minutes) must not treat handoff as synchronous: `assign`, end the turn, `collect` later.

Read `deliverable` if set, else `result_excerpt`. Pane `result.md` is a TUI dump.

## Send message

```bash
python3 scripts/herd-dispatch send \
  --name impl-auth \
  --wait \
  --message "Address only the reviewer items listed below. Do not expand scope."
```

`--wait` makes it a synchronous follow-up: just the message, then the reply. Same tool-timeout rule as Handoff. Without `--wait`, fire and `collect` later. If the worker is already `blocked`, the script refuses unless the human explicitly asked you to `--force`.

## Surprise memory (field guide)

`.field-guide/` at the repository root accumulates what workers learn the hard way: model weights are frozen, so only **surprises** earn an entry — environment quirks, non-obvious invariants, approaches that looked right and failed.

- Point every job brief at the guide files relevant to that job, plus any new or recently corrected entries.
- Ask workers to report surprises in their deliverable. At collect time, transcribe the lasting ones into the guide yourself: short dated entries citing paths or error strings, no opinions. Workers never edit the guide.
- Append only; stale entries get a dated one-line correction, never a rewrite.

The guide belongs to the repository and outlives any job. It needs no protocol to be useful — an unmentioned guide still helps workers that look.

## Model

`--model` is a spawn-time flag on `assign` / `handoff`. The script maps it to that kind's native start argument (`grok --model`, `cursor-agent --model`, and the same for claude/codex/pi/gemini). `send` cannot change the model of an already-started worker.

Grok Build is kind `grok` (aliases: `grok-build`, `grok build`). Cursor Agent CLI is kind `cursor` (alias: `cursor-agent`). The Cursor IDE binary `cursor` is not the worker.

When the human names a model, or you need to choose one, list ids first. Do not invent ids. Probe only the kind you are about to spawn:

```bash
python3 scripts/herd-dispatch models --kind grok
python3 scripts/herd-dispatch models --kind cursor
```

Read `models[].id` and `default`. Then pass that id on spawn:

```bash
python3 scripts/herd-dispatch assign --kind grok --model <id> --name impl-auth --message-file ...
python3 scripts/herd-dispatch assign --kind cursor --model <id> --name impl-cursor --message-file ...
```

`doctor.model_kinds` is the set of kinds this probe supports. If `ok` is false, show the JSON; do not guess. If the kind has no mapping, pass native flags with `--args` instead of `--model`. Do not pass both. Cursor catalogs can be hundreds of ids — pick one (or the `default`) instead of pasting the whole list.

## Talking

This is a conversation with another pane. Say what you want in `--message` or `--message-file`. There is no required schema.

`assign` / `handoff` send that text plus a short worker note (do not spawn peers; answer in the reply). `send` is only the follow-up message.

After `handoff`, `send --wait`, or `collect`, read `deliverable` if set, else `result_excerpt`. Do not paste a multi-thousand-line dump into `--message`; point at paths.

## Routing defaults

| Work | Kind default | Mode |
|---|---|---|
| Implementation, tests, mechanical refactors | `codex` or `pi` | assign if independent, else handoff |
| Architecture, merge decisions, spec | captain (this session) | do not dispatch |
| Review of captain or Codex output | `codex`, `pi`, or `cursor` — not the author | handoff, or assign then collect |
| Read-only exploration | cheaper kind available on PATH | assign |
| Trivial local commands (`git status`, one-file reads) | captain | do not dispatch unless the human is testing dispatch |

Override `--kind` when the user names a CLI. `grok` and `cursor` are first-class when they appear in `doctor`'s `kinds` array. Inspect that array; do not assume every machine has every CLI.

Do not default `--kind grok` for a worker. Grok's first prompt often never starts (`idle` / `unknown`, `agent_prompt_stalled`). Spawn grok only when the human named that CLI. Grok as this captain is fine.

## Status handling

- `working` after assign — normal. Do not busy-poll more than once per collect.
- `idle` / `done` — read `deliverable` if set, else `result_excerpt`. Script `ok` only means they finished talking.
- `blocked` — human gate. Never send y or enter to dismiss approvals.
- Start or prompt failure (`ok` false, still idle) — `status --name`, then one `send` retry. If still dead, `stop --name --yes` only for workers this captain created, and pick a different kind from the routing defaults instead of respawning the same one.

## Cleanup

Leave workers up when the human may inspect panes. Stop only workers you spawned:

```bash
python3 scripts/herd-dispatch stop --name impl-auth --yes
```

Never `herdr server stop`. Never close the captain pane.

## Placement

`assign` / `handoff` never split the captain pane.

- If `--name` is already a live agent, the script refuses. Use `send --name` instead of spawning a second pane.
- The first worker in this cwd for this captain gets `tab create --workspace <captain workspace> --cwd <work> --label herd --no-focus`. The agent starts on `.result.root_pane.pane_id`.
- Later workers tile on that owned tab with `pane split <id> --no-focus` (explicit pane id, never `--current`). Overflow is geometric: if a split would leave a child below 40×12, or the tab already has 4 panes, the script creates `herd-2` (then `herd-3`, …).
- Ownership is the tab id stored under `.herd-dispatch/index.json` `layouts` keyed by `workspace_id:captain_pane_id`. Do not discover tabs by label — humans rename them, and another captain may also have a tab called `herd`.
- A stale pointer (tab closed, or no panes left) degrades to a new `tab create`. The script does not fall back to splitting the captain.
- Always `--no-focus`. `pane rename` to the job name is best-effort. Failed starts close only the pane created for that attempt. Idle workers and their tabs stay up.
- Do not steal empty shells from other captains. Reuse only panes recorded in this captain's layout entry.

## Efficiency

- Dispatch every independent assign first, then end the turn, then collect.
- One worker per deliverable. Do not stack nested captains.
- Prefer `--message-file` plus `--worktree` over huge pasted context.
- Cap live workers. If more than ten are `working`, collect or stop before spawning.
- After collect, summarize from `deliverable` if set, else `result_excerpt`.
- If this captain cannot wait (see Handoff), every long job is assign then later collect.
- Judge jobs by deliverables and verification results, not by activity; busywork is not progress.

## References

- What the worker sees, and how to read the reply — [references/envelope.md](references/envelope.md)
- Errors and recovery — [references/errors.md](references/errors.md)
- Install onto Claude / Codex / Pi / Grok / Cursor — [references/install.md](references/install.md)
