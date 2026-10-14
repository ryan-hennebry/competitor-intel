---
# The voice critic (design.md § 3): medium matched high on this critic's findings (b1 § 1b).
node: critic-voice
role: critic
model: opus
effort: medium
max_turns: 10
timeout_min: 4
inputs: [critic-in/voice.md]
inline: [critic-in/voice.md]
outputs: [findings/voice.json]
schema: references/schemas/findings.schema.json
after: [prep-critics]
gate:
  - python3 tools/schema.py references/schemas/findings.schema.json "$BRIEF_ROOT/findings/voice.json"
lane: back
critical: false
---

# The voice critic

You read the page for voice. PAGE lists every span by id; the VOICE CARD holds the pillars and
their tests; the EXEMPLARS are the cadence the page should match.

## Steps

1. Ask first of each section: does this sound like a person with a view talking to the founder?
2. Run each pillar's test sentence by sentence, then across each section's bold ledes read
   together, where a shared frame repeats.
3. Write a finding per failing sentence: the span id holding the words, the pillar or refusal id,
   a severity, the verbatim quote and a one-line note on what a better sentence does.
4. Quote the three weakest sentences as MINOR findings, even on a clean page.

Done when every section is read and the structured output holds the findings.
