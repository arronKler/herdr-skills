# Errors and recovery

Precondition failures are JSON on stderr with `"ok": false`. Prompt attempts and watch results return JSON on stdout; always inspect `ok`, `delivery`, and `error`, not just the process exit code.

If `doctor` itself returns `"ok": false`, stop. Show the JSON. Do not run raw `herdr agent start` / `wait` / `prompt` or `hc run` / `send` / `wait` to work around it.

`doctor.runtime` says which backend was selected (`herdr` or `hc`). Set `HERD_DISPATCH_RUNTIME` only when detection picks the wrong one — for example a shell that inherits `HC_TERMINAL_ID` but is meant to be inside Herdr.

| Signal | Meaning | Action |
|---|---|---|
| `herdr is not on PATH` | Binary missing | Tell the human to install Herdr |
| `HERDR_ENV!=1` | Captain is not inside Herdr | Start work with `herdr`, then relaunch the coding agent in a pane |
| `hc is not on PATH` | herdr-core CLI missing | Install herdr-core (`hc`), or force `HERD_DISPATCH_RUNTIME=herdr` if this is a Herdr pane |
| `not inside a herdr-core terminal (HC_TERMINAL_ID unset)` | Captain is not inside an hc terminal | Relaunch the captain from an `hc` terminal, or force `HERD_DISPATCH_RUNTIME=herdr` |
| `cannot resolve captain pane` | `HERDR_PANE_ID` unset | Relocate the captain into a Herdr pane; do not continue |
| `refusing to operate on the captain pane` | Know-thyself trip | Pick another `--name` |
| `unknown kind` | `--kind` not in Herdr's list | Read `kinds` from `doctor`, or `herdr agent start --help`. `grok-build` aliases to `grok`; `cursor-agent` aliases to `cursor` |
| `no known --model mapping` | Kind has no mapped start flag | Use `--args` with that CLI's native flags, or pick grok/cursor/claude/codex/pi/gemini |
| `no model catalog probe` | `models --kind` unsupported | Use the CLI's own help, or `--args` if you already have an id |
| `binary not on PATH` | Worker CLI missing | Install it. Grok Build is `grok`; Cursor Agent is `cursor-agent` |
| `invalid agent name` | Name fails `[a-z][a-z0-9_-]{0,31}` | Lowercase, start with a letter |
| `agent_not_ready` | Worker blocked during boot | `status`, read pane, ask human |
| `agent_blocked` / `status: blocked` | Approval or question UI | Do not approve. Show `result` to the human |
| `status: error` | A live herdr-core agent reported an error, or a finished terminal exited non-zero | Check `state`/`exit_code`; read the reply/dump, then decide before respawning |
| `delivery_unconfirmed` | herdr-core `send` returned no `started` confirmation | `watch`, inspect; do not resend |
| `status_mismatch` | `hc send --if idle` found the worker no longer idle | Nothing was typed. Inspect the current turn; do not blindly resend |
| `prompt_transport_unknown` | `hc send` timed out | Same rule: the prompt may be running |
| `hc error kind=...` | herdr-core rejected the call (`not_found`, `blocked`, `invalid`, `refused`, ...) | Show `message`/`hint`; re-read `hc schema` if a flag was rejected |
| `agent_prompt_stalled` / prompt timeout | Delivery unconfirmed; the prompt may already be running | `watch`, inspect; no automatic send or model fallback |
| `no terminal found for job` | Recorded terminal was removed or never existed | `list`, respawn with a new name |
| `live agent named X already exists` | assign/handoff `--name` is already live | `send --name X`. Do not invent `X-2` |
| `agent_pane_busy` | Worker pane was not a shell yet | Script retries; if it still dies, show the human |
| `tab create returned no tab/root pane` | Herdr layout error | Show the JSON. Do not `pane split --current` on the captain |
| `--worktree requires a git repository` | Isolation requested outside git | Drop `--worktree` or init git |
| pane close refused without `--yes` | Safety | Only stop workers this captain spawned |

## Herdr CLI notes

- `agent start` needs an empty shell pane. The script creates or tiles a captain-owned worker tab (`--no-focus`) and waits for a prompt before start. It never splits the captain pane.
- `agent prompt --wait` settles on `idle`, `done`, or `blocked` unless `--until` is set. Dispatch accepts an observed `working`, `idle`, `done`, or `blocked` transition after submission, including fast completion. Treat `blocked` as failure to finish.
- Alternate-screen TUIs wrap and chrome-dump. Prefer `deliverable`, then `result_excerpt`. `pane.md` is the TUI dump for new collections.
- `idle` vs `done` is a seen-tab distinction. Content-wise both mean "ready for another prompt".
- `collect --wait` waits for evidence of this prompt’s execution. Already-confirmed settled jobs return immediately; boot-idle without evidence remains unconfirmed.
- `watch` checks the selected fleet together; use it instead of serial long waits when other jobs need supervision.

## herdr-core CLI notes

- Workers are terminals, addressed `tN` (or `machine/tN` across machines). The script stores that address as `pane_id` and uses it, not the name, for all later operations.
- Status comes from the agent's OSC 7501 reports. A live terminal with no report yet is `unknown`; a live `error` is a program-reported state; a finished terminal maps `exit_code == 0` to `done`, anything else to `error`. `hc ls --all` keeps finished terminals in fleet snapshots.
- `hc run --bg` returns before the child CLI is ready. The script then polls `hc wait` until a status report or the start timeout, and kills the terminal if the start fails.
- `hc send` reports `started` for the turn it delivered. An idle follow-up also passes `--if idle`, so a concurrent status change rejects it with `status_mismatch` instead of typing into the wrong turn. `started: null` is not proof of non-delivery; treat it as `delivery_unconfirmed`.
- `hc kill` finishes the terminal; `hc rm` deletes it. The script only kills (`stop --yes`).
- Do not run `hc` bare (picker) or `hc server stop`.
- Errors arrive as `{"error":{"kind","message","hint"}}` with a non-zero exit. Show the hint; do not retry with guessed flags.

## What not to do

- Do not poke a stalled composer or resend merely because it is idle. `agent_prompt_stalled` is not proof of non-delivery.
- Do not answer permission prompts.
- Do not `herdr server stop` or `hc server stop`.
- Do not close tabs, workspaces, or terminals you did not create.
- Do not treat script `ok` as acceptance. Read the reply.
