---
model: opus
max_turns: 15
# Graph (tools/run.py). The bar is cached on its inputs (tools/bar-cache.py): bar-cache copies a hit
# into place; on a miss this file's body runs as bar-gen; bar stores what bar-gen wrote and is the
# node later stages wait on. `tools/rule.py add` re-warms the cache off the run.
node: bar-gen
role: bar
effort: high
timeout_min: 3
when: test ! -s "$BRIEF_ROOT/00-bar.md"
outputs: [00-bar.md]
after: [bar-cache]
gate:
  - bash tools/bar-check.sh "$BRIEF_ROOT/00-bar.md"
nodes:
  - node: bar-cache
    run: python3 tools/bar-cache.py get "$BRIEF_ROOT"
    timeout_min: 1
  - node: bar
    run: python3 tools/bar-cache.py put "$BRIEF_ROOT"
    timeout_min: 1
    outputs: [00-bar.md]
    after: [bar-gen]
    gate:
      - bash tools/bar-check.sh "$BRIEF_ROOT/00-bar.md"
---

# The bar

Fifteen lines that index `quality-bar/` for the nodes after you. They are an **index**, never the
standard: the author still reads the voice card, the refusals and the exemplars in full, and each
critic reads its own source file. The bar is the same for every job ad, so it is generated once per
quality bar and cached; you run only when the cache missed.

## Steps

1. Read every file in `quality-bar/` in full, `fixtures/` excepted. Done when you can name, for
   each line of the format below, the file and heading it comes from.
2. Count `quality-bar/near-misses.tsv` by `rule_id` and take the three with the most rows.
3. Write `00-bar.md` in the format below: at most 15 lines, the `BAR v` stamp first, no heading, no
   commentary. Each line says what its source file says, in that file's words, cut to the shortest
   form that keeps the rule. Where the material does not fit, drop the least load-bearing line.

## Format

```
BAR v<first 7 hex of `python3 tools/bar-cache.py key`>  (<today, YYYY-MM-DD>)
READER  <who reads the page>; <what 01-hiring-rubric.md's gate asks of a page, shortest form>; judgement is the currency, effort is not.
GATE    <founder-card.md's tests a line must pass, shortest form>
TRUTH   Every number, absence and quantifier = a claim ID with its qualifier; tables carry the prose's caveat; blocked is not absent.
P1 <pillar> · P2 <pillar> · P3 <pillar>
P4 <pillar> · P5 <pillar>
P6 <pillar> · P7 <pillar>
P8 <pillar>
REFUSE  <the active refusals of 03-refusals.md, shortest form, separated by ·>
BLOCKING  <06-critique-rubric.md's blocking list, shortest form, with its pass threshold>
TOP RECURRING: <step 2's three rule_ids, each in the reader's words>
EXEMPLAR  <three gold sentences from 05-exemplars.md, quoted>
```

The pillars are `02-voice-card.md`'s P1-P8, each as the card states it. The BLOCKING line names the
checks that block, `voice-lint` and `claims-check` among them: a node that cannot see which check
blocks cannot clear it.

Every line traces to a file you read today. A line that summarises a rule you skipped is the one
defect this node exists to prevent, because every later node then works from your summary.

done = `bash tools/bar-check.sh "$BRIEF_ROOT/00-bar.md"` exits 0
