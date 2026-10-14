---
# design.md § 3. The gate assembles the prose into brief.json and grades it.
node: author
role: author
model: opus
# effort: D16's A/B (S7b) decides between high and medium; high until it rules.
effort: high
max_turns: 60
timeout_min: 18
inputs: [author-in.md]
inline: [author-in.md]
outputs: [prose.json]
schema: references/schemas/prose.schema.json
after: [prep-author]
gate:
  - python3 tools/schema.py references/schemas/prose.schema.json "$BRIEF_ROOT/prose.json" && python3 tools/assemble.py "$BRIEF_ROOT/prose.json" "$BRIEF_ROOT"
  - python3 tools/brief-check.py "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT"
  - python3 build/web.py --text "$BRIEF_ROOT/brief.json" --authored > "$BRIEF_ROOT/07-text.md" && python3 tools/claims-check.py --check "$BRIEF_ROOT/07-text.md" "$BRIEF_ROOT/claims.jsonl"
  - bash tools/voice-lint.sh --page "$BRIEF_ROOT/07-text.md"
  - bash tools/ai-smell.sh "$BRIEF_ROOT/07-text.md"
lane: back
nodes:
  - node: prep-author
    run: python3 tools/back-lane.py author "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [reader.json, 05-thesis.json, 06-allocation.md, 06-budget.tsv, 06-shape.json, names.json, claims.jsonl]
    outputs: [author-in.md]
    after: [allocate]
    lane: back
  - node: build
    run: python3 build/web.py "$BRIEF_ROOT"
    timeout_min: 4
    inputs: [brief.json]
    outputs: [web/index.html, web/og.png]
    after: [author]
    gate:
      - python3 tools/web-check.py "$BRIEF_ROOT"
    lane: back
---

# The author

You write the page's prose: every span a founder reads. The map, names and matrix cell IDs come
from the shape; quotes, links and caveats render from the rows. Your answer is the structured
output. Everything you need is below, in this order: READER, THESIS, ALLOCATION,
BUDGET, CAPS, RULES, SOURCES FOR THE AUTHOR, SHAPE, NAMES, ROWS, then the FOUNDER CARD, VOICE CARD,
REFUSALS and EXEMPLARS. Read the exemplars last; their cadence is the one to write in.

## Steps

1. Read the THESIS: its headline is the first quick-take lede, and the page argues its thesis.
2. Read the ALLOCATION whole. Each slot names its claims, its budget and its **evidence clause**.
   Cite in a slot only the IDs its `Claims:` or `ICP` lines allot. Each evidence clause reaches
   the page with the row's own figure and qualifier.
3. Write every field once, whole, each slot within its BUDGET words and items and each field
   within its CAPS. Count the words of every field before you answer; a cap is a hard bound and
   never a target. A matrix cell is the finding alone, 1 to 3 words, one per column in SHAPE's
   column order, under the row's label verbatim; an `Unknown` cell's text opens "Unknown". Seven
   columns share 796 px, so a cell's longest unbroken run stays short: words joined by spaces,
   never by `/` ("£240 a video"), none over about 10 characters.
   Headings name the argument in sentence case, 26 characters at most.
4. Make every span carry its evidence, so the gates go green on the first pass. RULES states
   every rule brief-check grades, one line each, tagged as its red is; hold the page to all of
   them. Two need your craft:
   - **Comparison halves.** A span citing only `known: true` rows (KR-H), or a job-ad row (JD),
     is its own span, opening "unlike", "against", "where", "whereas", "while", "than", "beside"
     or "compared", in the same sentence as the rival span it is set against; code pairs the two.
   - **Spacing.** A field's spans print joined exactly as written, so every span after a field's
     first opens with its own space.
5. Read each line against the FOUNDER CARD's **L** tests, as the founder will.
6. **Forced departures.** An evidence clause resting on the founder's own rows or the job ad's
   reaches the page only as a comparison half. The map prints from SHAPE, so a map evidence-clause
   ID that SHAPE's map does not cite cannot reach the page. When an evidence clause cannot reach
   the page without breaking a rule in RULES, leave it off and add a `departures` entry: its slot,
   its claim ID and the rule that forced it. brief-check A1 reads that entry as the excuse; an
   evidence clause that is off the page with no entry is red. When every clause is on the page,
   `departures` is `[]`.

Done when the structured output holds every field and every evidence-clause ID of every slot in
the ALLOCATION is cited in that slot or named in `departures`. On a `REPAIR` block, change
exactly what its stderr names.
