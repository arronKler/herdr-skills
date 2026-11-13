# Herdr agent skills

Agent skills for coordinating coding agents inside [Herdr](https://github.com/herdrdev/herdr) or herdr-core (`hc`): spawn other coding CLIs as workers, dispatch work, collect results — from one-off jobs to full agent swarms.

This repository holds two skills:

| Skill | What it does |
| --- | --- |
| [herdr-dispatch](skills/herdr-dispatch/) | The primitive layer. A captain agent assigns work to another CLI (Claude, Codex, Pi, Grok Build, Cursor, …), monitors the fleet, waits for a handoff, collects results, and sends follow-ups through a bundled Python dispatcher. |
| [herdr-swarm](skills/herdr-swarm/) | Small-scale swarms (3–8 workers) built strictly on top of herdr-dispatch: ownership-split task trees, a merge queue with neutral arbitration, shared decision logs, field-guide memory, and hidden-eval benchmarking. |

herdr-swarm requires herdr-dispatch. Dispatch stands alone.

## Install

Install with the [Vercel skills CLI](https://github.com/vercel-labs/skills). Both skills live under `skills/`, which the CLI discovers automatically:

```bash
npx skills add arronKler/herdr-skills
```

That installs every skill in the repository. To install only one, pass `--skill`:

```bash
npx skills add arronKler/herdr-skills --skill herdr-dispatch
npx skills add arronKler/herdr-skills --skill herdr-swarm
```

The installer lets you choose target agents. For the current project without prompts:

```bash
npx skills add arronKler/herdr-skills --agent codex claude-code cursor --yes
```

Add `--global` for a global install, or `--list` to inspect before installing.

## Requirements

- macOS or Linux with Python 3.9 or newer. The dispatcher uses only the Python standard library.
- A dispatch runtime, either:
  - [Herdr](https://github.com/herdrdev/herdr) available as `herdr` on `PATH`, with the captain running inside a Herdr pane (`HERDR_ENV=1`, resolvable pane), or
  - herdr-core available as `hc` on `PATH` (0.1.21 or newer), with the captain running inside an hc terminal (`HC_TERMINAL_ID` set).

  `doctor` reports the selected runtime as `runtime` (`herdr` or `hc`) and verifies it. Detection prefers herdr when both environments are present; set `HERD_DISPATCH_RUNTIME=herdr|hc` to force one.
- Each worker CLI installed and authenticated. Kinds depend on the local runtime; examples: `claude`, `codex`, `pi`, `omp`, `grok`, `cursor`, `letta`, `muse`.
- Git and a repository with an initial commit when using `--worktree`.

Installing these skills does not install Herdr, herdr-core, or worker CLIs. Grok Build uses the `grok` binary; the `cursor` kind uses `cursor-agent`, not the Cursor IDE. See [herdr-dispatch installation details](skills/herdr-dispatch/references/install.md).

## Use it with your agent

Start your captain agent inside Herdr or an hc terminal, then ask it to use a skill:

```text
Use herdr-dispatch to ask Codex to implement the parser change in a separate
worktree. Collect its result, then ask Claude to review that worktree.
```

```text
Use herdr-swarm to implement docs/spec.md: decompose it into a task tree,
fan out the leaves, merge them one by one, and report scores after each wave.
```

Dispatch protocol details, error recovery, and installation variants live in [herdr-dispatch references](skills/herdr-dispatch/references/): [envelope.md](skills/herdr-dispatch/references/envelope.md), [errors.md](skills/herdr-dispatch/references/errors.md), [install.md](skills/herdr-dispatch/references/install.md). The swarm protocol — roles, task trees, the merge queue, field-guide memory, reviews, benchmarking — lives in [herdr-swarm references](skills/herdr-swarm/references/).

## Dispatcher quick start

The bundled Python dispatcher is the primitive behind herdr-dispatch. Run commands from the project the worker should use; set `SKILL_DIR` to the installed skill directory:

```bash
SKILL_DIR="$PWD/.agents/skills/herdr-dispatch"
python3 "$SKILL_DIR/scripts/herd-dispatch" doctor
```

Continue only when doctor reports `"ok": true`, `self.pane_id`, and a `runtime` you expect. Assign an implementation task in a separate Git worktree, collect the result, then follow up:

```bash
python3 "$SKILL_DIR/scripts/herd-dispatch" assign \
  --kind codex --role implementer --name impl-parser --worktree \
  --message "Implement the parser change described in docs/parser-task.md. Run the relevant tests and report the changed files."

python3 "$SKILL_DIR/scripts/herd-dispatch" watch \
  --name impl-parser --timeout 30000

# Repeat watch while action is wait. Once action is collect:
python3 "$SKILL_DIR/scripts/herd-dispatch" collect --name impl-parser

python3 "$SKILL_DIR/scripts/herd-dispatch" send \
  --name impl-parser --wait \
  --message "Explain the edge cases covered by the tests."
```

The worker starts from the repository's `HEAD`; uncommitted changes are not copied into its worktree. Use `--message-file /path/to/task.md` for longer instructions. `ok: true` describes the dispatch lifecycle, not the quality of the worker's work — read the file named by `deliverable` when present, otherwise inspect `result_excerpt`. Jobs are recorded in `.herd-dispatch/` under the target project; use separate worktrees for concurrent implementation tasks.

| Command | Purpose |
| --- | --- |
| `doctor` | Check the captain environment, selected runtime, and required commands |
| `assign` | Start a worker; confirm delivery or return a recoverable unconfirmed result |
| `handoff` | Start a worker and wait for the conversation to settle |
| `watch` | Monitor a whole wave; return changed jobs and collect/inspect/wait actions |
| `collect` | Read a worker's result; add `--wait` for a single outstanding job |
| `send` | Send a follow-up to an existing worker; optionally wait |
| `models --kind <kind>` | Probe supported worker CLIs for live model IDs |
| `status --name <name>` | Inspect a worker's current lifecycle state |
| `stop --name <name> --yes` | Close a worker pane (herdr) or kill a worker terminal (hc) you created |

Run `python3 "$SKILL_DIR/scripts/herd-dispatch" <command> --help` for options. Timeouts are in milliseconds. `watch` defaults to 30 seconds (maximum 60); continue reading any background handle returned by the calling tool. Prompt stalls/timeouts are unconfirmed delivery, not permission to resend. Collect the current turn before `send`; it refuses working workers and unconfirmed prior prompts. See the [message and result protocol](skills/herdr-dispatch/references/envelope.md), [error recovery](skills/herdr-dispatch/references/errors.md), and the [task brief template](skills/herdr-dispatch/assets/brief-template.md).

## Where this came from

herdr-swarm distills Cursor's research blog *Agent swarms and the new model economics* (July 2026) to Herdr scale: scalability comes from context efficiency and coordination discipline rather than raw parallelism, failures like split brain and merge wars need named countermeasures, and memory should live in the environment the agents share. Herdr panes and hc terminals are heavyweight, so this targets minute-scale swarms with single-digit concurrency — the coordination lessons transfer, Cursor's custom infrastructure does not need to.

## Development

From a clone of this repository:

```bash
python3 -m unittest discover -s skills/herdr-dispatch/scripts -p 'test_*.py'
python3 skills/herdr-dispatch/scripts/herd-dispatch --help
npx skills add . --list
```

The unit tests use temporary directories and mocked runtime calls (both herdr and `hc`). They cover result collection, lifecycle verdicts, model handling, worker placement, and the herdr-core backend without launching live agents. A live dispatch check additionally requires the runtime setup above.

## License

[MIT](LICENSE).
