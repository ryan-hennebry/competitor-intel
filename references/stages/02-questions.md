---
model: opus
max_turns: 12
# max_turns is unmeasured: a placeholder until a replay runs this node, then 1.5x its count.
# Graph (tools/run.py)
node: questions
role: questions
effort: high
timeout_min: 4
inputs: [reader.json, 00-reader.md, 00-jd.md]
outputs: [questions.json, 02-questions.md]
schema: references/schemas/questions.schema.json
after: [reader]
gate:
  - python3 tools/schema.py references/schemas/questions.schema.json "$BRIEF_ROOT/questions.json"
  - python3 tools/node-check.py questions "$BRIEF_ROOT"
lane: role
---

# The questions

Three to five questions the research answers, chosen before any rival is named. Selection scores
on their axes and every extractor answers them, so a generic question buys a generic page at full
price.

## Steps

1. Read `reader.json`, `00-reader.md` and `00-jd.md`.
2. Draft six to ten candidates as the cross product of the seat's duties and what the company
   cannot yet see outside itself: for each duty, what about the market would this founder want
   answered before the hire starts?
3. Screen each candidate on both tests:
   - **NOT KNOWN.** The answer is absent from the KNOWN table and from the company's own pages.
   - **DECISION-CHANGING.** Name the decision this reader makes this quarter that a different
     answer would move, and which way each answer sends it.
4. Keep the three to five strongest as `questions[]`, in priority order. Every other candidate is a
   **seed**: `seeds[]` holds its text and why it was parked. The lock reads every seed and covers it
   or says why not, so a question parked here can still become the page's angle.
5. Type each question: `topic` one slug (`buyer` when it asks who buys; that routes an MKT1 call),
   `serves` the `L<n>` duty lines and `P<n>` positioning ids it answers to, `changes` the decision,
   `closed_list` the register, index or enumerated source an absence can be read off, or null.
6. Derive `axes[]`: three to five properties a company must have for its answer to matter.
   Selection scores the pool on these.
7. Write `02-questions.md`: one `### Q<n>. <question>` block per question in the same order, its
   fields beneath, then `## Axes` and `## Seeds`.

Ask each question neutrally: one that names its expected answer gets that answer handed back. A
question with no closed list can find a presence, never a proven absence. The axes name properties,
never companies; choosing the cohort is selection's.

done = the questions schema and `python3 tools/node-check.py questions "$BRIEF_ROOT"` exit 0
