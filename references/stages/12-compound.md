---
stage: 12
name: compound
model: opus
max_turns: 15
writes: <run_store>/12-compound.md, <run_store>/quality-bar.diff, <run_store>/governing-diffs.md, <run_store>/run-cost.txt
sentinel: <run_store>/.done-12
# Graph (tools/run.py): runs in the runner's finally, failures included; outputs go to compound/.
node: compound
role: compound
effort: medium
timeout_min: 6
inputs: [00-bar.md, findings.json, 11-delivery.md]
outputs: [12-compound.md, quality-bar.diff, governing-diffs.md]
final: true
---

# Stage 12 — compound

The run's lessons, written as proposals for the next run. This brief has shipped and nothing here
changes it. `quality-bar/` and the governing set stay read-only: an improvement session or the operator
applies what you propose (`quality-bar/README.md`).

The dispatch hands you `run_store`, the run's `BRIEF_ROOT`, and
`transcript`, the run's parent session transcript. Every file you read and write is in
`run_store`.

## Steps

1. Create `<run_store>/12-compound.md` with `Status: IN PROGRESS` as your first action.
2. Read `<run_store>/00-bar.md`, then `findings.json`, the `correctness-*.md` files and
   `11-delivery.md`.
3. Write `<run_store>/quality-bar.diff`: unified diffs against files in `quality-bar/`.
   - Every BLOCKER or MATERIAL row, and every row logged as a candidate rule, gets a proposal or a
     one-line reason it needs none. Each names its ledger row `id`.
   - A proposal is the rule that would have caught the defect **before** the critique wave, with
     the stage it would fire in.
   - Every defect that reached the author's text becomes one proposed row appended to
     `quality-bar/near-misses.tsv`, in that file's columns.
4. Write `<run_store>/governing-diffs.md`: proposed edits to `AGENTS.md` and `references/`, one per
   process lesson: a stage re-run, a refusal, a cap hit, a verdict that failed. Each cites the file
   and line in `run_store` that shows it.
5. Run `bash tools/run-cost.sh --by-model "<transcript>" > "<run_store>/run-cost.txt"`. A non-zero
   exit is recorded in `12-compound.md` with its message; the cost line is evidence, never a gate.
6. Confirm the run edited no governing file: `git status --porcelain -- quality-bar references
   AGENTS.md CLAUDE.md` prints nothing. Anything it prints is reported, never reverted by you.
7. Write `Status: DONE`, touch the sentinel, and return the 60-word line: counts of proposals by
   file, rows accounted for, and the `run-cost.txt` exit code.

Done when every BLOCKER, MATERIAL and candidate-rule row of the ledger is accounted for in
`quality-bar.diff`, and `governing-diffs.md` and `run-cost.txt` exist.

## Refusals for this stage

- Propose, never apply. The diff files are the output; the checkout stays as step 6 finds it.
- Root each proposal in a row or a file line. A lesson with no evidence in `run_store` is a
  preference, and it stays out.
- Write proposals that hold for any company. A lesson true only of this client, its market or its
  rivals stays in `12-compound.md`, where stage 1 of the next run against this company reads it.
