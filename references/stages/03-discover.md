---
model: opus
max_turns: 25
# Graph (tools/run.py). One instance per segments.json row, discover-1 to discover-5, in parallel.
# At the cap a node degrades with a coverage row; the pool rows it wrote stand.
node: discover
role: discover
effort: medium
timeout_min: 3.5
fanout: {from: segments.json, list: segments, key: id}
inputs: [segments.json, captures/jd.json]
outputs: ["pool/{item}.tsv"]
after: [market-map]
gate:
  - python3 tools/node-check.py pool "$BRIEF_ROOT" "pool/{item}.tsv"
lane: market
critical: false
---

# Discovery, segment {item}

Every company that could take this client's buyer within segment {item} of `segments.json`, each on
a page you fetched. Four other nodes search the other segments at the same time; stay inside yours.

## Steps

1. Read segment {item} in `segments.json`: its shape, market, language, queries and why.
2. Search its queries, then the variants the results suggest, in the segment's language. Search the
   shape, not a category word.
3. For each candidate, fetch its home page: `python3 tools/fetch.py <URL> --json`. Read the name,
   the one-line offer and the buyer off its saved `.txt`. Exit 0 is fetched; 3 is blocked and 4 not
   reached, each a row with that `http_code`.
4. Append its row to `pool/{item}.tsv` as soon as you have it, tab-separated, under the header
   `name url http_code one_line buyer_named_on_own_site markets linkedin_slug`:
   - `name` as the company's own site spells it; `url` the URL you fetched;
   - `buyer_named_on_own_site` the buyer its own page names, quoted, or `none`;
   - `markets` the markets its own pages name; `linkedin_slug` off its own footer link, or empty.

Every row rests on a fetch, so a name you saw only in a list or a search snippet earns a row once
you have fetched its own page. Keep the file current as you go: at the turn cap, the rows already
written are the deliverable.

done = `python3 tools/node-check.py pool "$BRIEF_ROOT" "pool/{item}.tsv"` exits 0
