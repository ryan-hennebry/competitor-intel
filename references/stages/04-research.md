---
model: opus
max_turns: 40
# Graph (tools/run.py). One extractor per names.json rival, extract-<slug>, in parallel, each on
# pages prefetch-rivals saved and in its own claim ID block. client-lists greps the client's own
# lists in code; merge joins the shards in code (merge.py, then fetch-logos --auto) and runs the
# whole-ledger gate. An extractor at its cap degrades with a coverage row.
node: extract
role: extractor
effort: medium
timeout_min: 5
fanout: {from: names.json, key: slug}
inputs: [names.json, questions.json, reader.json, client-lists.tsv, id-blocks.json, captures/rivals.json]
outputs: ["parts/{item}.jsonl", "comp-{item}.md"]
after: [prefetch-rivals, client-lists, questions]
gate:
  - python3 tools/claims-check.py --ledger "$BRIEF_ROOT/parts/{item}.jsonl" --pages "$BRIEF_ROOT/pages"
  - python3 tools/node-check.py shard "$BRIEF_ROOT" {item}
  - python3 tools/node-check.py blocks "$BRIEF_ROOT" {item}
lane: join
critical: false
nodes:
  - node: client-lists
    run: python3 tools/client-lists.py "$BRIEF_ROOT"
    timeout_min: 1
    outputs: [client-lists.tsv]
    after: [reader]
    lane: role
  - node: prefetch-rivals
    run: python3 tools/prefetch.py rivals "$BRIEF_ROOT"
    timeout_min: 1.5
    outputs: [id-blocks.json, captures/rivals.json]
    after: [select]
    lane: join
  - node: merge
    run: python3 tools/merge.py "$BRIEF_ROOT" && python3 tools/fetch-logos.py --auto "$BRIEF_ROOT"
    timeout_min: 2
    outputs: [claims.jsonl, sources.tsv, logos/logos.json]
    after: [extract, client-extract]
    gate:
      - python3 tools/claims-check.py --ledger "$BRIEF_ROOT/claims.jsonl" --require-client-rows --pages "$BRIEF_ROOT/pages"
    lane: join
---

# Extraction, {item}

One rival's evidence, as ledger rows: the questions answered on its own pages, where the client
holds against it, and whether the client's own lists name it. Facts leave this node as rows with
IDs; every later node cites the IDs and never retells the fact.

## Steps

1. Read the `{item}` row of `names.json`, `questions.json`, `references/methodology.md` § "The
   claims ledger" and § "Snapshot Schema", and your block in `id-blocks.json`: every row ID you
   write sits inside it. `captures/rivals.json` lists the pages already saved under `pages/`; read
   their `.txt` and fetch more with `python3 tools/fetch.py <URL>`.
2. Answer each question on this company's own pages, its own words quoted byte for byte from a
   `.txt`. Write each row to `parts/{item}.jsonl` as soon as you have it, with the fields
   `references/schemas/claims-row.schema.json` lists, `known` excepted: `question_id` the question
   it answers, `page_id` the fetch stem, `stage` `extract-{item}`.
3. Where the client holds against this rival (a capability the client's rows show and this
   rival's own pages lack or limit), write the rival-side row that shows it.
4. Read the client's lists at the paths and lines `client-lists.tsv` gives, with `sed -n`, and
   write exactly one join row for this company: `named` with the list's URL and quote, or
   `not named`, `exclusive` true and `scope` the list's count in digits.
5. Falsify every gap you keep: try to break it from the company's own pages first. Narrow each
   claim until its evidence carries it.
6. Write `snapshots/<domain>.json` to the methodology's schema, `captured` today and `sources` the
   pages you fetched from `pages/index.tsv`, then `comp-{item}.md`, 12 KB or less, an Answers table
   first: `question_id | one-line answer | claim IDs`.

A 403, 401, 429 or login wall is `blocked`, with what you tried; only a 404 on a canonical path is
absent. An absence is a claim about a closed list you can name. A row with a numeral carries
`metric`, and a `k of N` scope writes both in digits.

done = `claims-check --ledger --pages` on `parts/{item}.jsonl`, `node-check.py shard` and `node-check.py
blocks` exit 0
