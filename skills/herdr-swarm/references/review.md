# Review perspectives

Long multi-agent runs accumulate errors; the swarm needs a correction loop that catches small ones before they become structural.

## Default review

One reviewer per merged leaf (or per merge wave, for small leaves), dispatched with herdr-dispatch `handoff` against the merged main tree:

- Kind different from the author — never the author reviewing itself.
- Input: the leaf's goal and contract from the brief, the merged diff, `decisions.md`. Not the author's transcript.
- Output: a findings list in the deliverable, each finding classified `must-fix` (blocks) or `note` (record, don't block).

`must-fix` items go back to the author with one `send` (herdr-dispatch). If the same finding survives a second round, the captain takes it over — do not ping-pong.

## Stacked review (high risk only)

For high-risk merges, dispatch a **second** reviewer of a different kind, same input, no knowledge of the first reviewer's findings. Stack when any of:

- the merge touched core modules or captain-owned files
- the merge needed arbitration
- an oversized file was involved

No single perspective catches everything; low-correlated perspectives stack. Treat the union of both findings as the blocklist. Two kinds is the ceiling — a third reviewer has never paid for itself at this swarm scale.

## What reviewers are not for

Reviewers do not re-derive design, re-open `decisions.md` entries, or grade benchmark scores. Design disputes go to the captain; scores come from the benchmark run.
