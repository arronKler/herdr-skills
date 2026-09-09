# Herdr Dispatch

An agent skill for coordinating coding agents inside [Herdr](https://github.com/herdrdev/herdr). A captain agent can assign work to another CLI, wait for a handoff, collect results, and send follow-up messages through a bundled Python dispatcher.

Use it for isolated implementation tasks, parallel investigation, and reviews by another coding agent. Workers run in Herdr panes, so you can inspect their progress directly.

## Install

Install with the [Vercel skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add arronKler/herdr-dispatch --skill herdr-dispatch
```

This repository also ships [herdr-swarm](../herdr-swarm/README.md); omit `--skill` to install both. The installer lets you choose the target agents. To install into the current project for Codex, Claude Code, and Cursor without prompts:

```bash
npx skills add arronKler/herdr-dispatch \
  --skill herdr-dispatch --agent codex claude-code cursor --yes
```

For a global installation, add `--global`. To inspect the repository before installing:

```bash
npx skills add arronKler/herdr-dispatch --list
```

The skills live under `skills/<name>/`, a layout explicitly supported by the [CLI's discovery rules](https://github.com/vercel-labs/skills#skill-discovery). `SKILL.md` supplies the required `name` and `description`; the installer includes the accompanying scripts, references, and assets. No npm package or build step is needed for the skill itself.

## Requirements

- macOS or Linux with Python 3.9 or newer. The dispatcher uses only the Python standard library, including Unix file locking via `fcntl`.
- [Herdr](https://github.com/herdrdev/herdr) installed and available as `herdr` on `PATH`.
- The captain coding agent running inside a Herdr pane with `HERDR_ENV=1` and a resolvable captain pane. The `doctor` command verifies this and the required Herdr commands.
- Each worker CLI installed and authenticated. Available kinds depend on the local Herdr installation; examples include `claude`, `codex`, `pi`, `omp`, `grok`, and `cursor`.
- Git and a repository with an initial commit when using `--worktree`.
- Node.js and npm for the skills installer. Check the [CLI's current Node.js requirement](https://github.com/vercel-labs/skills/blob/main/package.json).

Installing this skill does not install Herdr or worker CLIs. Grok Build uses the `grok` binary; Herdr's `cursor` kind uses `cursor-agent`, not the Cursor IDE's `cursor` command. See [installation details](references/install.md) for integrations and manual installation.

## Use it with your agent

Start your captain agent inside Herdr, then ask it to use the skill:

```text
Use herdr-dispatch to ask Codex to implement the parser change in a separate
worktree. Collect its result, then ask Claude to review that worktree.
```

```text
Use herdr-dispatch to ask Pi for a read-only investigation of the failing test.
Wait for its answer and summarize the evidence.
```

The captain follows [SKILL.md](SKILL.md), checks the environment, and calls the dispatcher. Workers receive the task plus a short note that prohibits nested dispatch.

## Dispatcher quick start

Run commands from the project you want the worker to use. Set `SKILL_DIR` to the installed skill directory; this example uses a project-level Codex installation:

```bash
SKILL_DIR="$PWD/.agents/skills/herdr-dispatch"
python3 "$SKILL_DIR/scripts/herd-dispatch" doctor
```

Continue only when doctor reports `"ok": true`, `"herdr": true`, and `self.pane_id`.

Assign an implementation task in a separate Git worktree:

```bash
python3 "$SKILL_DIR/scripts/herd-dispatch" assign \
  --kind codex --role implementer --name impl-parser --worktree \
  --message "Implement the parser change described in docs/parser-task.md. Run the relevant tests and report the changed files."
```

The worker starts from the repository's `HEAD`; uncommitted changes are not copied into its worktree. Commit any task files it needs first.

Collect the result later, then follow up if needed:

```bash
python3 "$SKILL_DIR/scripts/herd-dispatch" collect \
  --name impl-parser --wait --timeout 900000

python3 "$SKILL_DIR/scripts/herd-dispatch" send \
  --name impl-parser --wait \
  --message "Explain the edge cases covered by the tests."
```

Use `--message-file /path/to/task.md` for longer instructions. Its text is copied into the worker prompt.

| Command | Purpose |
| --- | --- |
| `doctor` | Check the captain environment and required Herdr commands |
| `assign` | Start a worker and return after it enters `working` |
| `handoff` | Start a worker and wait for the conversation to settle |
| `collect` | Read a worker's result; add `--wait` to wait for completion |
| `send` | Send a follow-up to an existing worker; optionally wait |
| `models --kind <kind>` | Probe supported worker CLIs for live model IDs |
| `status --name <name>` | Inspect a worker's current lifecycle state |
| `stop --name <name> --yes` | Close a worker pane you created |

Run `python3 "$SKILL_DIR/scripts/herd-dispatch" <command> --help` for options. Timeouts are in milliseconds. Synchronous commands require a calling tool that can wait for the requested duration; otherwise use `assign` and collect in a later turn.

## Results and workspace behavior

Commands emit JSON. `ok: true` describes the dispatch lifecycle, not the quality or correctness of the worker's work. Read the file named by `deliverable` when present; otherwise inspect `result_excerpt`. The `result` path points to a pane transcript, which can include terminal UI text.

The dispatcher records jobs in `.herd-dispatch/` under the target project. It protects the captain pane and places workers in captain-owned tabs without taking focus. Use separate worktrees for concurrent implementation tasks. A `blocked` worker needs human attention; the skill does not answer approval prompts.

See [the message and result protocol](references/envelope.md), [error recovery](references/errors.md), and [the optional task template](assets/brief-template.md).

## Development

From the repository root:

```bash
python3 skills/herdr-dispatch/scripts/test_herd_dispatch.py
python3 skills/herdr-dispatch/scripts/herd-dispatch --help
npx skills add . --list
```

The unit tests use temporary directories and mocked Herdr calls. They cover result collection, lifecycle verdicts, model handling, and worker placement without launching live agents. A live dispatch check additionally requires the runtime setup described above.

## License

[MIT](LICENSE).
