# Errors and recovery

All script failures are JSON on stderr with `"ok": false`.

If `doctor` itself returns `"ok": false`, stop. Show the JSON. Do not run raw `herdr agent start` / `wait` / `prompt` to work around it.

| Signal | Meaning | Action |
|---|---|---|
| `herdr is not on PATH` | Binary missing | Tell the human to install Herdr |
| `HERDR_ENV!=1` | Captain is not inside Herdr | Start work with `herdr`, then relaunch the coding agent in a pane |
| `cannot resolve captain pane` | `HERDR_PANE_ID` unset | Relocate the captain into a Herdr pane; do not continue |
| `refusing to operate on the captain pane` | Know-thyself trip | Pick another `--name` |
| `unknown kind` | `--kind` not in Herdr's list | Read `kinds` from `doctor`, or `herdr agent start --help`. `grok-build` aliases to `grok`; `cursor-agent` aliases to `cursor` |
| `no known --model mapping` | Kind has no mapped start flag | Use `--args` with that CLI's native flags, or pick grok/cursor/claude/codex/pi/gemini |
| `no model catalog probe` | `models --kind` unsupported | Use the CLI's own help, or `--args` if you already have an id |
| `binary not on PATH` | Worker CLI missing | Install it. Grok Build is `grok`; Cursor Agent is `cursor-agent` |
| `invalid agent name` | Name fails `[a-z][a-z0-9_-]{0,31}` | Lowercase, start with a letter |
| `agent_not_ready` | Worker blocked during boot | `status`, read pane, ask human |
| `agent_blocked` / `status: blocked` | Approval or question UI | Do not approve. Show `result` to the human |
| `agent_prompt_stalled` | Still idle/done; prompt likely never started | One `send` retry. Then inspect |
| `no live agent named` | Worker exited or never started | `list`, respawn with a new name |
| `live agent named X already exists` | assign/handoff `--name` is already live | `send --name X`. Do not invent `X-2` |
| `agent_pane_busy` | Worker pane was not a shell yet | Script retries; if it still dies, show the human |
| `tab create returned no tab/root pane` | Herdr layout error | Show the JSON. Do not `pane split --current` on the captain |
| `--worktree requires a git repository` | Isolation requested outside git | Drop `--worktree` or init git |
| pane close refused without `--yes` | Safety | Only stop workers this captain spawned |

## Herdr CLI notes

- `agent start` needs an empty shell pane. The script creates or tiles a captain-owned worker tab (`--no-focus`) and waits for a prompt before start. It never splits the captain pane.
- `agent prompt --wait` settles on `idle`, `done`, or `blocked` unless `--until` is set. Assign waits until `working` or `blocked`. Treat `blocked` as failure to finish.
- Alternate-screen TUIs wrap and chrome-dump. Prefer `deliverable`, then `result_excerpt`. `result.md` is the TUI dump.
- `idle` vs `done` is a seen-tab distinction. Content-wise both mean "ready for another prompt".
- `collect --wait` on a splash-screen `idle` waits for `working`, then for `idle`/`done`.

## What not to do

- Do not `herdr pane send-keys enter` to poke a stuck composer unless `status` shows idle and the last prompt clearly never submitted. Prefer `send`.
- Do not answer permission prompts.
- Do not `herdr server stop`.
- Do not close tabs or workspaces you did not create.
- Do not treat script `ok` as acceptance. Read the reply.
