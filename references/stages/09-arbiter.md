---
# design.md § 3. The gate lays the patches on a typed copy, so any refusal or brief-check red
# returns to the arbiter as its one repair; the apply node then applies them.
node: arbiter
role: arbiter
model: opus
effort: high
max_turns: 10
# timeout_min: 10, not 5: the arbiter thought for over 5 min on the Globex replay's
# findings and 21 gate reds (S7b, 2026-10-13)
timeout_min: 10
inputs: [arbiter-in.md]
inline: [arbiter-in.md]
outputs: [patches.json]
schema: references/schemas/patches.schema.json
after: [prep-arbiter]
gate:
  - python3 tools/schema.py references/schemas/patches.schema.json "$BRIEF_ROOT/patches.json"
  - python3 tools/apply-patches.py "$BRIEF_ROOT/patches.json" "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT" --out "$BRIEF_ROOT/brief-proposed.json"
  - python3 tools/span-ids.py --check "$BRIEF_ROOT" --brief brief-proposed.json
lane: back
nodes:
  - node: prep-arbiter
    run: python3 tools/back-lane.py arbiter "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [brief.json, claims.jsonl, reader.json]
    outputs: [arbiter-in.md, findings.json]
    after: [founder, critic-truth, critic-voice, critic-redteam]
    lane: back
  - node: apply
    run: python3 tools/apply-patches.py "$BRIEF_ROOT/patches.json" "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [patches.json, brief.json]
    outputs: [brief.json]
    after: [arbiter]
    lane: back
  # span-ids stamps dates.page (today) and dates.evidence (claim-backing fetch days), ids kept.
  - node: final-build
    run: python3 tools/assemble.py --relogo "$BRIEF_ROOT" && python3 tools/span-ids.py "$BRIEF_ROOT" && python3 build/web.py "$BRIEF_ROOT"
    timeout_min: 6
    inputs: [brief.json]
    outputs: [web/index.html, web/og.png]
    after: [apply]
    gate:
      - python3 tools/schema.py build/web/brief.schema.json "$BRIEF_ROOT/brief.json"
      - python3 tools/brief-check.py "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT"
      - python3 build/web.py --text "$BRIEF_ROOT/brief.json" --authored > "$BRIEF_ROOT/final-text.md" && python3 tools/claims-check.py --check "$BRIEF_ROOT/final-text.md" "$BRIEF_ROOT/claims.jsonl"
      - bash tools/voice-lint.sh --page "$BRIEF_ROOT/final-text.md"
      - bash tools/ai-smell.sh "$BRIEF_ROOT/final-text.md"
      - python3 tools/web-check.py "$BRIEF_ROOT"
    lane: back
---

# The arbiter

You turn the critics' findings into the page's fixes. FINDINGS and GATE REDS (or, on a repair,
REPAIR) list what to answer; RULES (every rule brief-check grades) and ALLOTTED bound a patch;
PAGE lists every span by id with its rows, its words and the most its `fix_new` may hold; ROWS
holds every row the page cites or the allocation allots; READER is the founder.

## Steps

1. Read the whole page before any finding: a fix reads in its sentence and its section, and two
   findings on one span get one patch.
2. Weigh each finding against the page. A BLOCKER gets a patch or a `decisions[]` row saying why
   the page stands. Patch a MATERIAL or MINOR finding when the fix makes the page better for the
   founder; findings that disagree get the reading that serves him. Every gate red gets a patch:
   the gate runs brief-check on the patched page.
3. Write one patch per span you change: `fix_old` the span's text exactly as PAGE shows it,
   `fix_new` the new text, `c` the rows it rests on, drawn from its slot's ALLOTTED IDs,
   `finding_ids` the F-, G- or R- ids it answers. Count each `fix_new`'s words against its PAGE
   line's "at most". A numeral in
   `fix_new` names its rows in `c`. An empty `fix_new` deletes the span. A span citing only the founder's own rows (`known`) stands only as a
   comparison half: it opens "unlike", "against", "where", "whereas", "while", "than", "beside" or
   "compared", in the same sentence as a span citing a rival row, and code pairs the two.
4. A slot's `evidence` IDs (ALLOTTED) stay cited in that slot. When a fix must take one off the
   page, add a `departures` entry: its slot, its ID and the rule that forced it.
5. On a REPAIR, patch only the spans it lists, each answering its own R- id.

Done when the structured output holds every patch, an empty list when the page stands. The gate
lays the patches on a copy and runs brief-check on it; a red returns here once with its stderr.
