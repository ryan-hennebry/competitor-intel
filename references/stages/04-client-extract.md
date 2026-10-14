---
model: opus
max_turns: 40
# Graph (tools/run.py). The client's own extractor, in the role lane: it waits for the client-lists
# grep and the MKT1 notes, and runs beside selection and the rival extractors.
node: client-extract
role: extractor
effort: medium
timeout_min: 7
inputs: [reader.json, questions.json, client-lists.tsv, claims.jsonl, captures/jd.json]
outputs: [parts/client.jsonl]
after: [client-lists, questions, mkt1]
gate:
  - python3 tools/claims-check.py --ledger "$BRIEF_ROOT/parts/client.jsonl" --pages "$BRIEF_ROOT/pages"
  - python3 tools/node-check.py shard "$BRIEF_ROOT" client
  - python3 tools/node-check.py blocks "$BRIEF_ROOT" client
lane: role
---

# Extraction, the client

The hiring company's side of every question, as ledger rows, plus the two readings of the client
only it gets: its marketing advantages and its channel fit. The reader seeded what the company says
about itself (`C-001` to `C-099` in `claims.jsonl`); you add what answers the questions.

## Steps

1. Read `reader.json`, `questions.json`, `claims.jsonl`, `references/methodology.md` § "The claims
   ledger" and § "Snapshot Schema", and any `mkt1/*.md` note. The client's pages are under `pages/`
   (`captures/jd.json` lists them); fetch more with `python3 tools/fetch.py <URL>`.
2. Answer each question on the client's own pages and register entries, quoted byte for byte from a
   `.txt`. Write each row to `parts/client.jsonl` as soon as you have it, IDs `C-100` to `C-199`,
   with the fields `references/schemas/claims-row.schema.json` lists, `known` excepted; `stage`
   `client-extract`. A row that repeats a reader row cites that row's ID instead of copying it.
3. Read the lists `client-lists.tsv` points at, with `sed -n`, and record each list's heading and
   count in your comp file; the rival extractors write the join rows against them.
4. If `references/mkt1-digest.md` exists (a licensed MKT1 digest, not published with this repository; skip this step without it), work its § Marketing advantages and § Channel fit off this run's fetched
   evidence and any MKT1 note. Every number either rests on is a row.
5. Write `snapshots/<domain>.json` for the client to the methodology's schema, `captured` today and
   `sources` the pages fetched, then `comp-<slug>.md` (`slug` is the company name lower-cased, each
   run of other characters a hyphen): the Answers table first, `question_id | one-line answer |
   claim IDs`, then the two sections from step 4.

The client's own claims carry a qualifier opening `company-stated`; describe them no more harshly
than a rival's own claim. Blocked is not absent; an absence is read off a closed list you can name.

done = `claims-check --ledger --pages` on `parts/client.jsonl`, `node-check.py shard client` and
`node-check.py blocks client` exit 0
