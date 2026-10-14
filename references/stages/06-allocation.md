---
# design.md § 3 and § 7 (S11): stage 6 is one typed call. prep-shape pastes every input into the
# prompt; the gate writes the answer as 06-shape.json, 06-allocation.md and 06-budget.tsv
# (tools/shape.py write) and screens them in code (budget-check --screened), so a red comes back to
# this node as its one repair. allocate is code: the allocation by question_id (N25).
node: shape
role: shape
model: opus
effort: high
max_turns: 5
timeout_min: 15
inputs: [shape-in.md]
inline: [shape-in.md]
outputs: [shape.json]
schema: references/schemas/shape.schema.json
after: [prep-shape]
gate:
  - python3 tools/schema.py references/schemas/shape.schema.json "$BRIEF_ROOT/shape.json" && python3 tools/shape.py write "$BRIEF_ROOT"
  - python3 tools/budget-check.py --allocation --web "$BRIEF_ROOT"
  - python3 tools/budget-check.py --screened "$BRIEF_ROOT"
lane: back
nodes:
  - node: prep-shape
    run: python3 tools/shape.py prep "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [reader.json, questions.json, 05-thesis.json, names.json, claims.jsonl]
    outputs: [shape-in.md]
    after: [rank]
    lane: back
  - node: allocate
    run: python3 tools/budget-check.py --allocation --by-question "$BRIEF_ROOT" > "$BRIEF_ROOT/allocation.json"
    timeout_min: 1
    inputs: [06-allocation.md, claims.jsonl, questions.json]
    outputs: [allocation.json]
    after: [shape]
    gate:
      - python3 tools/budget-check.py --allocation --web "$BRIEF_ROOT"
    lane: back
---

# Stage 6: the shape

You decide what the page spends itself on before any prose: the map's axes and answers, the
matrix's rows, and each web slot's rows, budget and evidence clause. Code writes your structured
output as the author's files. Your inputs follow: READER, THESIS, QUESTIONS, COHORT, CAPS,
COMPANIES, ROWS. Every ID you cite is a ROWS row with a `url`; a row without one has no source
card to print.

## Steps

1. **Draft the axes.** Each is a yes-or-no question that a company's own pages or a closed list
   answer. Keep the two that best split the cohort on a decision the reader makes, and answer both
   for every company. A `yes` rests on a customer: no cited row's claim says "integration", and at
   least one is no pilot by its claim or qualifier.
2. **Choose the matrix rows**, each a capability a buyer chooses on: one cell per column, the IDs
   it rests on, or `[]` (printed Unknown) where no row answers it.
3. **Name each axis's and row's decision** from its question's `changes`, and the value that
   `flips` it, and which way. Two rows on one decision: keep the stronger. List every cut axis and
   row in `dropped` with the rows that decided it, and restore any the reader would miss.
4. **Fill the six slots.** `claims` are the rows a slot may cite; quick-take carries the thesis's
   IDs, and `icp` its buyer rows. Each evidence clause is the slot's non-cuttable fact, main row
   first, with that row's own figure and qualifier; quick-take's states a judgement about the need.
   recommendations' `source` is the distribution claim's derivation in the hiring company's comp
   file. Budgets stay within CAPS, a ceiling.
5. **Lead with news.** Each evidence clause leads with a row new to him. A `known: true` row, or a
   rival fact his own pages already carry, is his already. Where only such a row can lead, as with
   an open question about his own asset, add a `departures` entry with the reason.
6. **Subtract.** Cut every item, row and ID whose deletion loses the reader nothing.

Done = the gate exits 0: `tools/shape.py write`, then `tools/budget-check.py --allocation --web`
and `--screened`. A red comes back with its stderr as your one repair.
