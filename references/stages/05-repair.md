---
# The repair node's values. While stage 5 is wrapped, tools/run.py reads the node from the `nodes:`
# list in 05-thesis-lock.md, which names this file as its template; keep the two equal.
role: repair
model: opus
effort: high
max_turns: 4
timeout_min: 3
inputs: [candidates.json, "repairs/{item}.reds.json", reader.json, claims.jsonl]
outputs: ["repairs/{item}.json"]
after: [screen]
gate:
  - python3 tools/rank.py repair-check "$BRIEF_ROOT" {item}
schema: references/schemas/candidates.schema.json
lane: spine
critical: false
---

# Stage 5: one repair of candidate {item}

A majority of three screeners marked candidate `{item}` red, and every red quotes a clause of its
prose. This is its one repair before a kill: rewrite exactly the quoted clauses so the card passes
them, and leave everything else as it stands. Three fresh screeners re-screen the result; a second
red kills it.

## Steps

1. Read candidate `{item}` in `candidates.json`, and `repairs/{item}.reds.json`: each red test,
   the clauses the screeners quoted and why.
2. Read the tests those reds name in `quality-bar/founder-card.md`, and the rows the quoted clauses
   rest on in `claims.jsonl`.
3. For each quoted clause, delete it, or replace it with a clause the card passes: a gap the advice
   closes instead of a verdict, a rival's fact instead of the founder's own, the hire's work instead
   of a directive. The seam punctuation beside a clause is yours to fix.
4. Return `candidates.json`'s candidates with `{item}` repaired and every other candidate as it
   was. In `{item}`, every other character stays byte for byte, and every typed field (`evidence`,
   `depends_on`, `duties`, `decision`, `stance`, `case_against`) stays exactly as it was.

Done when the structured output holds the repaired candidate. The gate, `tools/rank.py
repair-check`, refuses any change outside the quoted clauses.
