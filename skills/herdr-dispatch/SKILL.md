---
name: herdr-dispatch
description: Dispatch peer coding agents through Herdr or herdr-core (hc) using assign, handoff, and send_message. Use when inside a Herdr pane or an hc terminal and the user wants Claude, Codex, Pi, omp, Grok Build, Cursor, or another CLI worker spawned, tasked, collected, or followed up. Triggers include herd-dispatch, assign a worker, handoff to Codex, send_message to a pane, hc run, fan-out agents, peer review across CLIs, grok-build worker, cursor-agent model.
license: MIT
metadata:
  version: "1.9"
  runtime: herdr | herdr-core
---

# Herdr Dispatch

Captain protocol for running other coding CLIs as workers inside Herdr or herdr-core (`hc`). Call the bundled script. Do not improvise raw `herdr agent start` / `wait` / `prompt` or `hc run` / `send` / `wait` sequences.

## Preconditions

1. Run `scripts/herd-dispatch doctor` first. It must report `"ok": true`, `self.pane_id`, and `runtime` (`herdr` or `hc`).
2. The runtime is detected from the environment: `HERDR_ENV=1` selects herdr, `HC_TERMINAL_ID` selects herdr-core. Set `HERD_DISPATCH_RUNTIME=herdr|hc` to force one.
3. herdr needs the captain in a Herdr pane; herdr-core needs the captain in an `hc` terminal (`HC_TERMINAL_ID` set). If doctor prints `"ok": false` for any reason, stop. Show the JSON to the human. Do not debug by running raw `herdr agent` or `hc` commands.
4. Never target the captain pane or terminal. The script refuses self-operations; do not bypass it.
5. Never run bare `herdr` (that attaches the TUI and hangs) or bare `hc` (that opens the picker). Never run `herdr server stop` or `hc server stop`.
6. Workers must not dispatch further workers. Only the captain uses this skill.

## Tools

All verbs print JSON. Read `ok`, `runtime`, `name`, `status`, `delivery`, `deliverable`, `result_excerpt`, `error`.

`status` is the lifecycle word: `idle`, `done`, `working`, `blocked`, or `unknown`; herdr-core can also report `error`. It is never `settled`.

For dispatch/collect, `ok` describes lifecycle, not work quality:

- `assign` / async `send`: delivery is confirmed and status is `working` (or `idle`/`done` if it already finished).
- `handoff` / `collect` / `send --wait`: delivery is confirmed and status is `idle` or `done`.
- `delivery: unconfirmed`: the prompt may already have arrived. Use `watch` or inspect; do not resend or replace the worker merely because of this result.
- `delivery: rejected`: the runtime explicitly rejected the prompt before input was sent (`agent_blocked` in herdr, `blocked` in herdr-core). Inspect the gate.

`watch.ok` means the fleet snapshot succeeded. Check each job's `action`, `status`, and `delivery`; it does not mean the jobs succeeded.

If `deliverable` is set, that file is the answer. `result_excerpt` is leftover pane chrome; `pane.md` is the TUI dump (older jobs may use `result.md`). See [references/envelope.md](references/envelope.md).

`ok: true` with `status: unknown` is a script bug. Treat it as failure.

If `status` is `blocked`, inspect the approval/question and show it to the human. For other failures, follow the recovery instructions below; an unconfirmed delivery is not an approval request.

| Verb | CAO equivalent | Blocks? | Use |
|---|---|---|---|
| `assign` | assign | up to 30s to confirm prompt | Fan-out independent work |
| `handoff` | handoff | until `idle`/`done`/`blocked` | Next step needs the worker output |
| `send` | send_message | optional | Follow up an existing worker |
| `collect` | inbox harvest | optional | Pull assign results later |
| `watch` | fleet monitor | up to 30s by default | Check all jobs with one snapshot per cycle |
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

Returns once prompt delivery is confirmed or the bounded confirmation window expires. Dispatch the other independent jobs, then supervise the whole wave with `watch`; collect each settled job. Continue the authorized task rather than ending the turn with only a promise to collect later.

```bash
python3 scripts/herd-dispatch watch --name impl-auth --timeout 30000
# Repeat watch while action is wait; when action is collect:
python3 scripts/herd-dispatch collect --name impl-auth
```

Reserve `collect --wait` for a single outstanding worker. With several workers, watch all of them together so a slow job does not hide a sibling's completion or failure.

Parallel assign is allowed only when tasks do not share a writable tree. Use `--worktree` for any implementation.

`idle`/`done` alone does not prove whether input was delivered. Read `delivery`. The script persists the job before sending and reconciles late state changes without resubmitting. A fast completed job can return `ok: true` with `idle`/`done`.

## Handoff (sync)

```bash
python3 scripts/herd-dispatch handoff \
  --kind claude \
  --role reviewer \
  --name rev-auth \
  --message-file .herd-dispatch/jobs/rev-auth/input.md
```

The script waits until `idle`, `done`, or `blocked`. Use it when only one worker is outstanding and the calling tool can keep collecting its process output. If the tool returns a background/session handle, continue reading that handle; it is not job completion. For multiple workers, use `assign` plus `watch` so one slow job cannot hide another job's failure.

Read `deliverable` if set, else `result_excerpt`. `pane.md` is the TUI dump; older jobs may use `result.md`.

## Send message

```bash
python3 scripts/herd-dispatch send \
  --name impl-auth \
  --wait \
  --message "Address only the reviewer items listed below. Do not expand scope."
```

`--wait` makes it a synchronous follow-up: just the message, then the reply. Same tool-timeout rule as Handoff. Without `--wait`, supervise with `watch`. `send` refuses a still-working worker or an unconfirmed previous prompt: neither runtime tracks queued turns reliably, so collect the current turn before following up. `--force` does not bypass these checks. If the worker is already `blocked`, the script refuses unless the human explicitly asked you to `--force`.

## Supervise the whole wave

```bash
python3 "$SKILL_DIR/scripts/herd-dispatch" watch \
  --name impl-auth --name impl-ui --name rev-api --timeout 30000
```

One read-only fleet snapshot checks every selected job each cycle. The command returns on a lifecycle/delivery change, a settled/blocked/missing worker, or the time budget. Read every row:

- `action: collect`: run `collect --name <name>` without a long wait, then read the deliverable.
- `action: inspect`: inspect `result --name <name> --refresh` and the error; handle missing workers or approval gates without replaying the task.
- `action: wait`: keep monitoring. `delivery: unconfirmed` may still become confirmed; elapsed time alone never authorizes a resend.

Omit `--name` to monitor jobs recorded for this captain in this cwd; use explicit names for the current wave or legacy jobs without captain ownership metadata. Remove handled jobs from the next watch call. `watch` does not harvest reports, merge code, send input, or approve anything. It reports runtime lifecycle, not provider error classification or evidence of productive work; inspect a settled worker's reply even when no files changed.

Keep fleet supervision on a 30–60s cadence while doing independent work. Pi can run bounded watch calls; Codex/Cursor should keep reading any background process handle returned by their command tool. Only end a turn with pending jobs when a real continuation mechanism is armed or the user asked to pause. Do not assume a future user message will restart collection. Merge serially; monitor all workers together.

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

- `working` after assign — normal. Use bounded fleet `watch`, not repeated per-worker polling.
- `idle` / `done` — read `deliverable` if set, else `result_excerpt`. Script `ok` only means they finished talking.
- `error` (herdr-core) — a live agent reported an error, or a finished terminal exited non-zero. Check `state`, `exit_code`, and `reason` before deciding; do not resubmit the task blindly.
- `blocked` — human gate. Never send y or enter to dismiss approvals.
- Prompt stall/timeout — read `delivery` and `prompt_error`. `unconfirmed` means watch/inspect, never an automatic retry or model fallback. Replace a worker only after concrete failure evidence and inspection of its existing output; use the user’s allowed models. The original task may already be executing.

## Cleanup

Leave workers up when the human may inspect panes or terminals. Stop only workers you spawned:

```bash
python3 scripts/herd-dispatch stop --name impl-auth --yes
```

herdr closes the pane; herdr-core sends `hc kill` and leaves the finished terminal in the list. Never `herdr server stop` or `hc server stop`. Never close the captain pane or terminal.

## Placement

herdr: `assign` / `handoff` never split the captain pane.

- If `--name` is already a live agent, the script refuses. Use `send --name` instead of spawning a second pane.
- The first worker in this cwd for this captain gets `tab create --workspace <captain workspace> --cwd <work> --label herd --no-focus`. The agent starts on `.result.root_pane.pane_id`.
- Later workers tile on that owned tab with `pane split <id> --no-focus` (explicit pane id, never `--current`). Overflow is geometric: if a split would leave a child below 40×12, or the tab already has 4 panes, the script creates `herd-2` (then `herd-3`, …).
- Ownership is the tab id stored under `.herd-dispatch/index.json` `layouts` keyed by `workspace_id:captain_pane_id`. Do not discover tabs by label — humans rename them, and another captain may also have a tab called `herd`.
- A stale pointer (tab closed, or no panes left) degrades to a new `tab create`. The script does not fall back to splitting the captain.
- Always `--no-focus`. `pane rename` to the job name is best-effort. Failed starts close only the pane created for that attempt. Idle workers and their tabs stay up.
- Do not steal empty shells from other captains. Reuse only panes recorded in this captain's layout entry.

herdr-core: `assign` / `handoff` create a child terminal of the captain with `hc run --bg --name <job> --cwd <work>`.

- There are no tabs or panes to place; herdr-core owns layout. The job address (`tN` or `machine/tN`) is stored as `pane_id` and used for every later verb (`get`, `read`, `send`, `wait`, `kill`), so a name reused by another terminal cannot redirect an existing job.
- `--kind` names a worker CLI binary, not an `hc` template. The script resolves the binary to an absolute path before `hc run`, so native flags such as `--model` stay the program's arguments instead of becoming a template's first task.
- If `--name` is already a live terminal, the script refuses; use `send --name`. Finished names are reusable: a new assign starts a new generation and binds the new address, while the old job keeps its old address.
- Fleet observation uses `hc ls --all`, so a worker that exits remains observable as `done`/`error`; it does not disappear from the snapshot.
- A failed start kills the terminal created for that attempt, so it does not leave an orphan. The script reports the error JSON instead of retrying with a different command shape.
- `stop` sends `hc kill`; finished terminals stay listed under `hc ls --all`. `hc rm` is not run automatically.


## Efficiency

- Dispatch the independent wave, then watch the whole wave and collect ready jobs promptly.
- One worker per deliverable. Do not stack nested captains.
- Prefer `--message-file` plus `--worktree` over huge pasted context.
- Cap live workers. If more than ten are `working`, collect or stop before spawning.
- After collect, summarize from `deliverable` if set, else `result_excerpt`.
- If a long shell call backgrounds, retain its handle and keep reading output; prefer short fleet watch calls for supervision.
- Judge jobs by deliverables and verification results, not by activity; busywork is not progress.

## References

- What the worker sees, and how to read the reply — [references/envelope.md](references/envelope.md)
- Errors and recovery — [references/errors.md](references/errors.md)
- Install onto Claude / Codex / Pi / Grok / Cursor — [references/install.md](references/install.md)
