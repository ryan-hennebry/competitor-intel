---
model: opus
max_turns: 10
# Graph (tools/run.py). The market lane's first node: it runs beside the reader, off the job ad and
# the client pages prefetch-client saved, and hands discovery five disjoint spaces.
node: market-map
role: market-map
effort: medium
timeout_min: 2
inputs: [captures/jd.json]
outputs: [segments.json]
schema: references/schemas/segments.schema.json
after: [prefetch-client]
gate:
  - python3 tools/schema.py references/schemas/segments.schema.json "$BRIEF_ROOT/segments.json"
  - python3 tools/node-check.py segments "$BRIEF_ROOT"
lane: market
---

# The market map

Five search spaces, one per discovery node, chosen so that together they hold every company this
client's buyers could pick instead. A rival missed here is invisible to every later node.

## Steps

1. Read `captures/jd.json` and the `.txt` of each page it lists as fetched: the job ad and the
   client's own site. Done when you can say, in the client's own words, who its buyer is, what
   that buyer pays for, and what the contract delivers.
2. Write the client's **shape**: the buyer, what is bought, what is installed or delivered, and what
   the buyer does today instead of buying from anyone. A rival that does the job under another name
   will not answer to the category word; it answers to the shape.
3. Split the alternatives into five **disjoint** spaces. Each differs from the others in query
   family, market or business model, so no two discovery nodes search the same results. Good
   splits: direct rivals in the client's market; the same shape sold under another category name;
   the platforms and agencies the buyer already pays; each market the job ad names, in that market's
   own language; the buyer's default alternative.
4. For each space write `shape`, `market`, its `language` code, at least two `queries` in that
   language, and `why`: the job ad or client page line it rests on, quoted.

Search by shape, in each market's own language: a company that sells in one country describes
itself only in that country's words. Name no company here; the spaces are where discovery looks,
and the picking is selection's.

done = the segments schema and `python3 tools/node-check.py segments "$BRIEF_ROOT"` exit 0
