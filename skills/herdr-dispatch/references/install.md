# Install

This skill works with agents that load SKILL.md and can run Python 3.9 or newer on macOS or Linux. The dispatcher uses the standard library, including Unix-only `fcntl` file locking.

## Install with the skills CLI

Use the [Vercel skills CLI](https://github.com/vercel-labs/skills) to install directly from GitHub:

```bash
npx skills add arronKler/herdr-skills --skill herdr-dispatch
```

This repository also ships herdr-swarm; omit `--skill` to install both. Choose the captain agent when prompted, or specify one explicitly:

```bash
npx skills add arronKler/herdr-skills --skill herdr-dispatch --agent codex --yes
```

Add `--global` to install for use across projects. Use `--list` to inspect the skill before installing. Skills live under `skills/<name>/`, which the CLI discovers automatically.

## Prerequisites

- Python 3.9 or newer on macOS or Linux
- `herdr` on PATH
- Captain coding agent started **inside** a Herdr pane (`HERDR_ENV=1`)
- Worker CLIs installed and authenticated (`claude`, `codex`, `pi`, `omp`, `grok`, `cursor-agent`, ...)
- Git with an initial commit for `--worktree`; new worktrees start at `HEAD` and do not include uncommitted files
- Recommended integrations for better state:

```bash
herdr integration install claude
herdr integration install codex
herdr integration install pi
herdr integration install omp
herdr integration install grok
herdr integration install cursor
```

Grok Build is Herdr kind `grok` (binary `grok`). Cursor Agent CLI is kind `cursor` (binary `cursor-agent`, not the Cursor IDE `cursor` command).

## Claude Code

Copy or symlink the skill directory to `~/.claude/skills/herdr-dispatch/` or `.claude/skills/herdr-dispatch/`.

Optional PATH shim:

```bash
ln -sf /path/to/herdr-dispatch/scripts/herd-dispatch ~/.local/bin/herd-dispatch
```

## Codex

Place the directory where Codex loads skills, or add a short pointer in `AGENTS.md`:

```markdown
When dispatching peer agents, use the herdr-dispatch skill and `herd-dispatch` script.
Workers must not spawn further agents.
```

## Pi / omp

```bash
pi install /path/to/herdr-dispatch
```

or copy into the project's Pi skill path.

## Coexisting with the Herdr skill

The official `herdr` skill can coexist. Use `herdr` for layout inspection; use `herdr-dispatch` for assign/handoff/send.

## Worker profile

Workers should receive only the message. Do not install this skill into worker sessions. If a worker image already has it, the appended worker note still forbids nested dispatch.
