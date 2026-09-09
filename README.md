# Herdr agent skills

Agent skills for coordinating coding agents inside [Herdr](https://github.com/herdrdev/herdr): spawn other coding CLIs as workers, dispatch work, collect results — from one-off jobs to full agent swarms.

This repository holds two skills:

| Skill | What it does |
| --- | --- |
| [herdr-dispatch](skills/herdr-dispatch/) | The primitive layer. A captain agent assigns work to another CLI (Claude, Codex, Pi, Grok Build, Cursor, …), waits for a handoff, collects results, and sends follow-ups through a bundled Python dispatcher. |
| [herdr-swarm](skills/herdr-swarm/) | Small-scale swarms (3–8 workers) built strictly on top of herdr-dispatch: ownership-split task trees, a merge queue with neutral arbitration, shared decision logs, field-guide memory, and hidden-eval benchmarking. |

herdr-swarm requires herdr-dispatch. Dispatch stands alone.

## Install

Install with the [Vercel skills CLI](https://github.com/vercel-labs/skills). Both skills live under `skills/`, which the CLI discovers automatically:

```bash
npx skills add arronKler/herdr-dispatch
```

That installs every skill in the repository. To install only one, pass `--skill`:

```bash
npx skills add arronKler/herdr-dispatch --skill herdr-dispatch
npx skills add arronKler/herdr-dispatch --skill herdr-swarm
```

The installer lets you choose target agents. For the current project without prompts:

```bash
npx skills add arronKler/herdr-dispatch --agent codex claude-code cursor --yes
```

Add `--global` for a global install, or `--list` to inspect before installing.

## Requirements

- macOS or Linux with Python 3.9 or newer. The dispatcher uses only the Python standard library.
- [Herdr](https://github.com/herdrdev/herdr) installed and available as `herdr` on `PATH`.
- The captain coding agent running inside a Herdr pane (`HERDR_ENV=1`, resolvable pane). `doctor` verifies this.
- Each worker CLI installed and authenticated. Kinds depend on the local Herdr installation; examples: `claude`, `codex`, `pi`, `omp`, `grok`, `cursor`.
- Git and a repository with an initial commit when using `--worktree`.

Installing these skills does not install Herdr or worker CLIs. Grok Build uses the `grok` binary; Herdr's `cursor` kind uses `cursor-agent`, not the Cursor IDE. See [herdr-dispatch installation details](skills/herdr-dispatch/references/install.md).

## Use it with your agent

Start your captain agent inside Herdr, then ask it to use a skill:

```text
Use herdr-dispatch to ask Codex to implement the parser change in a separate
worktree. Collect its result, then ask Claude to review that worktree.
```

```text
Use herdr-swarm to implement docs/spec.md: decompose it into a task tree,
fan out the leaves, merge them one by one, and report scores after each wave.
```

Dispatch quick start, protocol details, and error recovery live in [skills/herdr-dispatch](skills/herdr-dispatch/README.md). The swarm protocol — roles, task trees, the merge queue, field-guide memory, reviews, benchmarking — lives in [skills/herdr-swarm](skills/herdr-swarm/README.md).

## Where this came from

herdr-swarm distills Cursor's research blog *Agent swarms and the new model economics* (July 2026) to Herdr scale: scalability comes from context efficiency and coordination discipline rather than raw parallelism, failures like split brain and merge wars need named countermeasures, and memory should live in the environment the agents share. Herdr panes are heavyweight, so this targets minute-scale swarms with single-digit concurrency — the coordination lessons transfer, Cursor's custom infrastructure does not need to.

## Development

From a clone of this repository:

```bash
python3 skills/herdr-dispatch/scripts/test_herd_dispatch.py
python3 skills/herdr-dispatch/scripts/herd-dispatch --help
npx skills add . --list
```

The unit tests use temporary directories and mocked Herdr calls. They cover result collection, lifecycle verdicts, model handling, and worker placement without launching live agents. A live dispatch check additionally requires the runtime setup above.

## License

[MIT](LICENSE).
