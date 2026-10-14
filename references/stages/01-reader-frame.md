---
model: opus
max_turns: 30
# Graph (tools/run.py). prefetch-client fetches the job ad and the client's site in code, and stops
# the run on a job ad that is unreachable or names no company (AGENTS.md's hard stop). The reader
# returns reader.json typed and writes the rest itself.
node: reader
role: reader
effort: high
timeout_min: 8
inputs: [00-bar.md, captures/jd.json]
outputs: [reader.json, 00-jd.md, 00-reader.md, claims.jsonl]
schema: references/schemas/reader.schema.json
after: [bar, prefetch-client]
gate:
  - python3 tools/schema.py references/schemas/reader.schema.json "$BRIEF_ROOT/reader.json"
  - python3 tools/claims-check.py --ledger "$BRIEF_ROOT/claims.jsonl" --pages "$BRIEF_ROOT/pages"
  - python3 tools/node-check.py reader "$BRIEF_ROOT"
  - python3 tools/node-check.py blocks "$BRIEF_ROOT" reader
lane: role
nodes:
  - node: prefetch-client
    run: python3 tools/prefetch.py client "$BRIEF_ROOT"
    timeout_min: 2
    outputs: [captures/jd.json]
---

# The reader frame

Every later node aims at one person and grades a line by what that person already holds. You name
the person, the seat, and what the company already says about itself.

## Steps

1. Read `00-bar.md`, then `captures/jd.json`: the company code found, the job ad's saved pages and
   the client's home page, each fetch with its state. Every page it lists is already under `pages/`
   with a `.txt`; grep those, and fetch anything new with `python3 tools/fetch.py <URL>`. When
   `home_url` is null, find the company's own site from the ad or a search, then fetch its home
   page, `llms.txt`, and its pricing, customer, product, terms and rival-naming pages.
2. Write `00-jd.md`: title, team, location, pay, publication date, the full posting text, each with
   the URL it came from. Read the sibling postings on the same board and summarise what the company
   hires for in parallel in one line of `00-reader.md`.
3. Type the seat: `duties[]` are the ad's own lines, verbatim, `line` the `L<n>` of `grep -n` on the
   ad's `.txt`, weighted 3 for a duty bullet, 2 for the role framing, 1 for a requirement.
4. Resolve the recipient: the first source that names a person, in this order: the ad and its
   board fields, the company's team or about page, its home page and blog. `confidence` is `high`
   when a client-owned page and an independent row agree, `medium` on client-owned rows alone,
   `low` on third-party rows alone, `unresolved` with no name. Search their own public writing;
   `writing[]` cites rows quoting the criteria they state for judging work, and an empty list
   makes `taste_model` `generic`.
5. Seed `claims.jsonl` with what the company says about itself, IDs `C-001` to `C-099`, each
   qualifier opening `company-stated` and each quote read byte for byte off a `.txt`. Copy every
   positioning line on the home page hero, the board's company paragraph and `llms.txt`, verbatim,
   into a row and into `positioning[]`.
6. Write `00-reader.md`: who reads, the sibling-hiring line, and the KNOWN table, each cell citing
   its claim IDs. `known_summary` is that table in one paragraph.
7. `constraints[]` copies each `quality-bar/rulings.tsv` row of class `constraint` (its id as
   `ruling`), plus any limit this company's own rows state (`ruling` null).

A page that refuses to serve is `blocked`, with what you tried; a page that answers without the
value is an empty cell. A name no page carries is a fabrication, so an unfound reader stays
`unresolved`. Rival research belongs to the extractors.

done = the reader schema, `claims-check --ledger --pages` and `node-check.py reader` and `blocks
reader` all exit 0
