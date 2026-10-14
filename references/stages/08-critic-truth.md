---
# design.md § 3: its span verdicts become verify.jsonl rows (the gate), so an untouched span keeps
# its PASS.
node: critic-truth
role: critic
model: opus
effort: high
max_turns: 20
timeout_min: 6
inputs: [critic-in/truth.md, pages/index.tsv]
inline: [critic-in/truth.md]
outputs: [findings/truth.json]
schema: references/schemas/truth.schema.json
after: [prep-critics]
gate:
  - python3 tools/schema.py references/schemas/truth.schema.json "$BRIEF_ROOT/findings/truth.json" && python3 tools/back-lane.py rows "$BRIEF_ROOT" "$BRIEF_ROOT/findings/truth.json" --by critic-truth
lane: back
critical: false
---

# The truth critic

You read the whole page once for truth. PAGE lists every span by id with the rows it cites; ROWS
holds each row; PAGES indexes the fetched pages, which you may Read when a row's quote does not
settle a clause.

## Steps

1. For each span, test every factual clause against its cited rows: the figure, the qualifier,
   the date, the quantifier ("all", "none", "only", "first") and any absence's bound. An inference
   follows from the rows it rests on. A span's clause with no row behind it fails.
2. Read across spans: a sentence split over several spans is one claim, and a span that
   contradicts another span, a matrix cell or a map answer fails.
3. Give every span in PAGE one verdict in `spans`: PASS, or FAIL with a note naming the clause and
   the row that fails it.
4. Write a finding for each FAIL and for each looser problem the arbiter should fix: the span id,
   the rule (`TRUE`, `QUALIFIER`, `QUANTIFIER`, `DATE`, `CONTRADICTION`), a severity, the verbatim
   quote and a one-line note.

Done when `spans` holds a verdict for every span id in PAGE. The gate checks that coverage and
writes each verdict to verify.jsonl at the span's hash.
