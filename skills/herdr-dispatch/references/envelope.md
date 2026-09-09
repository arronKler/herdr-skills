# Messages

`--message` or `--message-file` is the utterance. No required sections.

`assign` / `handoff` append a short worker note: stay in cwd, do not spawn peers, answer in the final reply, and if the output is long or is a deliverable, write a file and name that path. `send` does not append that note.

The script records a copy under `.herd-dispatch/jobs/<name>/brief.md`. That file is for the captain, not a second protocol.

## Reading the reply

After `handoff`, `send --wait`, or `collect --wait`:

1. Script `ok` means the pane reached `idle` or `done` (or `working` for async assign). It is not a grade.
2. If the JSON has `deliverable`, read that file. That is the worker's answer. The script finds a path the worker named, or a file they wrote under `.herd-dispatch/jobs/<name>/` this turn. Workers do not write a result schema — they write a normal file and name it in the reply.
3. `result_excerpt` is leftover pane chrome. Use it only when there is no `deliverable`.
4. `result` / `result.md` is the TUI dump. Do not treat it as the answer. If the worker's file was itself named `result.md`, the dump is `pane.md` instead.
5. `status: blocked` means an approval or question UI. Show it to the human. Do not approve.

## Mode choice

- Independent modules, no shared files → multiple `assign`, then `collect --wait`.
- Review must see implementation output → `handoff` reviewer after collect.
- Tight loop (fix one test) → `handoff` implementer, then `send --wait` for one correction only.
- Second correction still failing → stop the worker and change the ask. Do not ping-pong.
