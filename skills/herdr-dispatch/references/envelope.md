# Messages

`--message` or `--message-file` is the utterance. No required sections.

`assign` / `handoff` append a short worker note: stay in cwd, do not spawn peers, answer in the final reply, and if the output is long or is a deliverable, write a file and name that path. `send` does not append that note.

The script records a copy under `.herd-dispatch/jobs/<name>/brief.md`. That file is for the captain, not a second protocol.

## Reading the reply

After `handoff`, `send --wait`, or `collect --wait`:

1. Dispatch/collect `ok` requires confirmed delivery and the appropriate lifecycle: `idle`/`done` for sync, or also `working` for async. It is not a grade. An unconfirmed prompt may already have arrived; do not replay it.
2. If the JSON has `deliverable`, read that file. That is the worker's answer. The script finds a path the worker named, or a file they wrote under `.herd-dispatch/jobs/<name>/` this turn. Workers do not write a result schema — they write a normal file and name it in the reply.
3. `result_excerpt` is leftover pane/terminal chrome. Use it only when there is no `deliverable`.
4. `result` points to the TUI dump (`pane.md` for new collections; old jobs may use `result.md`). Do not treat it as the answer. Worker `result.md` files are preserved. In herdr-core this is `hc read` output for the job terminal.
5. `status: blocked` means an approval or question UI. Show it to the human. Do not approve.
6. `status: error` (herdr-core only) means a live agent reported an error, or the terminal exited non-zero. Check `state`, `exit_code`, and `reason`, then read the dump before deciding whether the work failed or the CLI ended after a valid reply.

## Mode choice

- Independent modules, no shared files → multiple `assign`, fleet `watch`, then `collect --name` for each ready job.
- Review must see implementation output → `handoff` reviewer after collect.
- Tight loop (fix one test) → `handoff` implementer, then `send --wait` for one correction only.
- Second correction still failing → stop the worker and change the ask. Do not ping-pong.

## Prompt bookkeeping

The dispatcher stores cwd, pane/terminal, kind, model and captain identity before sending input. `send` starts a new generation while preserving that identity, clearing previous reply/error/collection state. Collection searches the recorded worktree as well as the captain job directory and rejects older report files. No worker result schema is required.

`send` refuses a working worker (queued prompts cannot be attributed to turns by herdr, and herdr-core `send` only reports the current turn) and an unconfirmed previous prompt. For an idle herdr-core worker the script also passes `--if idle`, so a worker that starts working between the check and the paste rejects the send with `status_mismatch`; nothing was typed and the job records `delivery: rejected`. `done`/`error` follow-ups have no equivalent `--if` value in hc, so there the pre-send check is best-effort; if `hc send` reports that the worker was already working, the script records `delivery_unconfirmed` instead of claiming the new turn. `watch` can reconcile a late state transition without submitting anything. A successful lifecycle observation is not evidence of correct implementation or passing tests.
