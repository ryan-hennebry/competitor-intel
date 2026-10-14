---
# The lock node's values. While stage 5 is wrapped, tools/run.py reads the node from the `nodes:`
# list in 05-thesis-lock.md, which names this file as its template; keep the two equal.
role: lock
model: opus
effort: high
# rank.py exit 3 (no eligible candidate) re-runs this node once, at xhigh, with rank's output (D12).
regen: {from: rank, exit: 3, effort: xhigh}
max_turns: 20
timeout_min: 10
inputs: [reader.json, questions.json, claims.jsonl]
outputs: [candidates.json]
after: [merge, questions]
gate:
  - python3 tools/schema.py references/schemas/candidates.schema.json "$BRIEF_ROOT/candidates.json"
  - python3 tools/rank.py lock-check "$BRIEF_ROOT"
schema: references/schemas/candidates.schema.json
lane: spine
critical: true
---

# Stage 5: the lock

You write the run's thesis candidates: 3 or 4 typed answers to "what should this founder hear
first from the person he is hiring". Three fresh screeners then grade each one on the founder-reader
card, and code ranks the survivors. Your work is the candidates; the verdict and the rank are not
yours to make.

## Steps

1. Read `quality-bar/founder-card.md` whole. Every field you write is graded by the test the card
   names for it, so write each field to pass its test.
2. Read `reader.json` whole: the role's weighted `duties`, the founder's own `positioning`, the
   `constraints` he cannot lift alone, and `known_summary`, what he already holds. Read
   `questions.json`: each question's `changes` rule, and every entry of `seeds[]`.
3. Read `claims.jsonl` for the rows each candidate rests on. Every claim ID you cite is a row you
   read.
4. Write 3 or 4 candidates. At least two have a rival as the grammatical subject. For each:
   - `headline` (14 words at most) and `thesis` (one sentence, 45 words at most): news to the
     founder, in plain words, no tags and no IDs. Rival evidence reads as a threat the advice
     answers, never as a grade on the founder's company.
   - `evidence[]` in the order the sentence uses it. The lead row, `evidence[0]`, is a `use: main`
     rival row; the founder's own rows appear only as `use: contrast`. Copy each row's `known`.
   - `advice`: the hire's own work under named duty lines, with its `first_instance`. Where it rests
     on a `constraints[]` entry or an `[Unknown]`, list it in `depends_on` and name a `fallback`
     that works without it.
   - `decision`: the question whose `changes` rule the evidence meets. `holds`: one place the
     company stands ahead or level, from `use: holds` rows, or null. `case_against`: the honest
     case, tagged.
5. Cover every seed: a candidate that answers it, or a `decisions[]` row naming why it is not one.
6. On a `REGEN` block, every candidate of the last lock went red. Read each quoted red and write new
   candidates that answer the same evidence without the clauses the screeners quoted.

Done when the structured output holds the candidates. The runner's gate then checks the candidate
schema and `tools/rank.py lock-check` (a lead row or every main row on the founder's own hosts is
red), and gives you one repair with its stderr on a red.
