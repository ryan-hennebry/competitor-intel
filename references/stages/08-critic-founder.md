---
# design.md § 3: three screeners on every authored line; node founder takes the majority.
model: opus
max_turns: 3
nodes:
  - node: prep-critics
    run: python3 tools/back-lane.py critics "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [brief.json, reader.json, claims.jsonl, pages/index.tsv]
    outputs: [critic-in/founder.md, critic-in/truth.md, critic-in/voice.md, critic-in/redteam.md, brief-author.json]
    after: [author]
    lane: back
  - node: critic-founder-a
    role: screener
    model: opus
    effort: high
    max_turns: 3
    timeout_min: 6
    template: references/stages/08-critic-founder.md
    inputs: [critic-in/founder.md]
    inline: [critic-in/founder.md]
    outputs: [findings/founder-a.json]
    schema: references/schemas/line-verdicts.schema.json
    after: [prep-critics]
    gate:
      - python3 tools/schema.py references/schemas/line-verdicts.schema.json "$BRIEF_ROOT/findings/founder-a.json"
    lane: back
    critical: false
  - node: critic-founder-b
    role: screener
    model: opus
    effort: high
    max_turns: 3
    timeout_min: 6
    template: references/stages/08-critic-founder.md
    inputs: [critic-in/founder.md]
    inline: [critic-in/founder.md]
    outputs: [findings/founder-b.json]
    schema: references/schemas/line-verdicts.schema.json
    after: [prep-critics]
    gate:
      - python3 tools/schema.py references/schemas/line-verdicts.schema.json "$BRIEF_ROOT/findings/founder-b.json"
    lane: back
    critical: false
  - node: critic-founder-c
    role: screener
    model: opus
    effort: high
    max_turns: 3
    timeout_min: 6
    template: references/stages/08-critic-founder.md
    inputs: [critic-in/founder.md]
    inline: [critic-in/founder.md]
    outputs: [findings/founder-c.json]
    schema: references/schemas/line-verdicts.schema.json
    after: [prep-critics]
    gate:
      - python3 tools/schema.py references/schemas/line-verdicts.schema.json "$BRIEF_ROOT/findings/founder-c.json"
    lane: back
    critical: false
  - node: founder
    run: python3 tools/back-lane.py founder "$BRIEF_ROOT"
    timeout_min: 1
    outputs: [findings/founder.json]
    after: [critic-founder-a, critic-founder-b, critic-founder-c]
    gate:
      - python3 tools/schema.py references/schemas/findings.schema.json "$BRIEF_ROOT/findings/founder.json"
    lane: back
    critical: false
---

# A founder critic

You are one of three founder critics. Each of you grades every authored line of the page alone,
and code counts a test red on a line when two of you say no. The batch below is the whole task:
CARD, READER, ROWS, PAGE and ITEMS, with the instruction that opens it.

Grade every item in ITEMS, in order, on the tests the card marks **L**. A red quotes the clause
that earned it verbatim, so the arbiter can rewrite exactly that clause.

Done when the structured output holds one verdict per item, each test carrying `pass`, a verbatim
`quote` and a `why`.
