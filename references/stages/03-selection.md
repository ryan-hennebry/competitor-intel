---
model: opus
max_turns: 30
# Graph (tools/run.py). The lanes join here: the market lane's pool and register lookups meet the
# role lane's questions. register is code (tools/register.py): every pool candidate looked up.
node: select
role: select
effort: high
timeout_min: 8
inputs: [questions.json, reader.json, segments.json, pool/registers.tsv]
outputs: [names.json, 03-selection.md]
after: [questions, register]
gate:
  - bash tools/score-check.sh --check "$BRIEF_ROOT/03-selection.md"
  - python3 tools/schema.py references/schemas/names.schema.json "$BRIEF_ROOT/names.json"
  - python3 tools/node-check.py names "$BRIEF_ROOT"
lane: join
nodes:
  - node: register
    run: python3 tools/register.py "$BRIEF_ROOT"
    timeout_min: 2
    outputs: [pool/registers.tsv]
    after: [discover, reader]
    lane: market
---

# Selection

The rivals the page is about, at most six. Every later node spends its budget on what you keep,
and a company scored out here is invisible to every gate after you.

## Steps

1. Read `questions.json` (its `axes[]` are the scoring axes), `reader.json`, every `pool/*.tsv` and
   `pool/registers.tsv`. One candidate per company: merge the rows that name it twice.
2. Score every candidate on every axis, 1 to 5, from the evidence its row and its saved pages
   carry. A register row reads as its `state` says: `matched` confirms, `no-match` is an answer,
   `blocked` is unknown and confirms nothing either way.
3. Before cutting a candidate for selling to the wrong buyer, fetch its own buyer-facing pages
   (`partner`, `enterprise`, `agencies`, in its language) with `python3 tools/fetch.py <URL>` and put
   the URL in the cut's reason; no such page found is itself the proof, written as the paths tried.
4. Pick at most six rivals: the highest totals, with a lower-scoring pick allowed when it covers a
   business shape no higher pick does, and the reason written.
5. Write `03-selection.md` in exactly this shape; `score-check.sh --check` owns it, so do not read
   the script. Every field sits wholly on one line at column 0. Blocks run in rank order; `axes:`
   carries one score per header axis, in order, and `total:` is their sum. `outcome:` opens with
   `selected.` or `cut.` and gives the reason. `hold:` opens with `none.` or names the held company
   and the registry consulted. `incumbent:` opens with `filled`, `absent`, `blocked`, `not-opened`
   or `unknown`; `absent` must carry the scores that decided it. The incumbent is the buyer's
   default alternative, often no company at all. The tags take a full stop and a space after them.

   ```
   captured: <YYYY-MM-DD>
   pool: <candidates considered>
   scored: <candidates scored>
   selected: <picks, at most 6>
   axes: <axis-1> <axis-2> <axis-3>
   scale: 1-5
   <free prose: what each scale point means, the pool's sources, the register read, the buyer-page proof>
   ---
   ### <Name>
   axes: 5 3 5
   total: 13
   outcome: selected. <reason, with the URL that proves it>
   ### Shell hold
   hold: none. <why no candidate waits on evidence>
   ### Incumbent slot
   incumbent: absent. <the default alternative>, scored 2 1 2 = 5, <why it is not in the final N>
   ```
6. Write `names.json`, one row per pick in page order: `slug`, `domain`, `page_id` the fetch stem of
   a saved page on the company's own domain, and `name` the brand exactly as one segment of that
   page's `<title>` spells it. Where the home page's title carries no brand, fetch the company page
   whose title does.

A cut rests on the company's own pages, with the URL in the reason. Follower counts and MKT1 tools
come later, and only where a question asks for them.

done = `score-check.sh --check`, the names schema and `python3 tools/node-check.py names
"$BRIEF_ROOT"` exit 0
