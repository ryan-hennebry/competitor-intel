---
stage: 5
name: thesis-lock
model: opus
max_turns: 20
nested_max_turns: 15
writes: $BRIEF_ROOT/05-thesis.md; on a re-lock also $BRIEF_ROOT/findings-ledger.tsv (HELD) or $BRIEF_ROOT/findings-ledger-05.tsv (CHANGED)
sentinel: $BRIEF_ROOT/.done-05
# Graph (tools/run.py): this stage is replaced by the nodes below (design.md section 8, S5).
# The lock reads the reader and questions nodes' typed files (S6) and the merged ledger; lock,
# screen, repair and rank are S4's, called as tools/rank.py exposes them. prep-screen and
# prep-rescreen write each candidate's screening page, which the runner inlines (`inline:`), so a
# screener spends its turns on the verdict.
nodes:
  - node: lock
    role: lock
    model: opus
    effort: high
    max_turns: 20
    timeout_min: 10
    template: references/stages/05-lock.md
    inputs: [reader.json, questions.json, claims.jsonl]
    outputs: [candidates.json]
    schema: references/schemas/candidates.schema.json
    after: [merge, questions]
    gate:
      - python3 tools/schema.py references/schemas/candidates.schema.json "$BRIEF_ROOT/candidates.json"
      - python3 tools/rank.py lock-check "$BRIEF_ROOT"
    lane: spine
    critical: true
  - node: prep-screen
    run: python3 tools/screen-input.py screen "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [candidates.json, reader.json, questions.json, claims.jsonl]
    outputs: [screen-in]
    after: [lock]
    lane: spine
  - node: screen
    role: screener
    model: opus
    effort: high
    max_turns: 3
    timeout_min: 5
    fanout: {from: candidates.json, list: candidates, key: id, copies: [a, b, c]}
    prompt: You are screener {copy}. Screen the one thesis candidate in ITEM against CARD, reading READER, CHANGES and ROWS below, and return its verdict with `item` set to ITEM's `id`, {item}.
    inline: ["screen-in/{item}.md"]
    outputs: ["screens/{item}-{copy}.json"]
    schema: references/schemas/verdict.schema.json
    after: [prep-screen]
    gate:
      - python3 tools/schema.py references/schemas/verdict.schema.json "$BRIEF_ROOT/screens/{item}-{copy}.json"
      - python3 tools/screen-input.py verdict-check "$BRIEF_ROOT/screens/{item}-{copy}.json" {item}
    lane: spine
    critical: false
  - node: repair
    role: repair
    model: opus
    effort: high
    max_turns: 4
    timeout_min: 3
    fanout: {from: candidates.json, list: candidates, key: id}
    when: python3 tools/rank.py needs-repair "$BRIEF_ROOT" {item}
    template: references/stages/05-repair.md
    inputs: [candidates.json, "repairs/{item}.reds.json", reader.json, claims.jsonl]
    outputs: ["repairs/{item}.json"]
    schema: references/schemas/candidates.schema.json
    after: [screen]
    gate:
      - python3 tools/rank.py repair-check "$BRIEF_ROOT" {item}
    lane: spine
    critical: false
  - node: prep-rescreen
    run: python3 tools/screen-input.py rescreen "$BRIEF_ROOT"
    timeout_min: 1
    inputs: [candidates.json]
    after: [repair]
    lane: spine
  - node: rescreen
    role: screener
    model: opus
    effort: high
    max_turns: 3
    timeout_min: 5
    fanout: {from: candidates.json, list: candidates, key: id, copies: [a, b, c]}
    when: test -s "$BRIEF_ROOT/rescreen-in/{item}.md"
    prompt: You are screener {copy}. Screen the one repaired thesis candidate in ITEM against CARD, reading READER, CHANGES and ROWS below, and return its verdict with `item` set to ITEM's `id`, {item}.
    inline: ["rescreen-in/{item}.md"]
    outputs: ["rescreens/{item}-{copy}.json"]
    schema: references/schemas/verdict.schema.json
    after: [prep-rescreen]
    gate:
      - python3 tools/schema.py references/schemas/verdict.schema.json "$BRIEF_ROOT/rescreens/{item}-{copy}.json"
      - python3 tools/screen-input.py verdict-check "$BRIEF_ROOT/rescreens/{item}-{copy}.json" {item}
    lane: spine
    critical: false
  - node: rank
    run: python3 tools/rank.py rank "$BRIEF_ROOT"
    timeout_min: 2
    outputs: [05-thesis.json, 05-thesis.md, checkin.md]
    after: [rescreen]
    regen: {exit: 3, node: lock, effort: xhigh}
    notify: "Competitor Intel: check-in ready"
    lane: spine
---

# Stage 5 — thesis-lock

The nodes above are stage 5: `lock` (`05-lock.md`), three card screeners per candidate,
`repair` (`05-repair.md`), the re-screen, and `rank` (`tools/rank.py`), which writes
`05-thesis.json`, `05-thesis.md` and `checkin.md`. The card is `quality-bar/founder-card.md`.

No node reads the body below: stage 6's screen is code since S11 (`tools/budget-check.py
--screened`), and its judgement half is `06-allocation.md`'s steps.

## The screener

A fresh context. Its input is:

- `$BRIEF_ROOT/00-bar.md`
- `$BRIEF_ROOT/00-reader.md` — the KNOWN table is what it grades against
- `$BRIEF_ROOT/02-questions.md` — read its `Changes:` lines only, the decisions DECISION-CHANGING
  may cite
- `$BRIEF_ROOT/claims.jsonl` — **never read whole**, per **Cost** below. Two reads per candidate:
  its cited rows by grep, and the **client-owned row** the client's side is decided on, resolved by
  `claims-check.py --client-row`
- the candidates, one sentence each with its subject company, that company's own URL, its claim
  IDs and the text of those rows, pasted in by this stage
- **one fetch per candidate**, made by the screener itself, per the section below

It scores every candidate on three tests and returns a verdict line per candidate: `KNOWN`,
`UNSUPPORTED`, `NO-DECISION` or `PASS`, with one sentence of reason. The file it writes is held to
the terse shape under **Cost**.

- **NEW.** The main clause is news to this reader. **KNOWN is bidirectional: either company naming
  the other makes the rival already known**, and both sides fire automatically, no argument
  required.
  - **The client's side.** Two sources, both read off files this stage already holds, neither a
    fresh fetch.
    - **The client-owned rows.** Stage 4 writes one per cohort company, recording whether a page or
      register the client controls names that company. Resolve the candidate's by its `subject`
      field, which is the field the row is found by:
      `python3 tools/claims-check.py --client-row "<subject company>" "$BRIEF_ROOT/claims.jsonl"`
      The company's name is the one `$BRIEF_ROOT/03-selection.md` records, passed whole and in that
      spelling. Exit 0 prints the one row: a `named` row is KNOWN, and the verdict line cites its
      claim ID; a `not named` row leaves this side empty and the candidate is graded on TRUE like
      any other. **Exit 1 is no row, and no row is not `not named`.** Nobody asked the question: the
      side is unknown, the verdict line says which, and silence is never read as an answer. Exit 2
      is a ledger the tool could not read — carry that into the verdict line too, and decide
      nothing from it.
      A note on stderr means the ledger holds more than one row for that company: the printed row
      is the one the tie-break in `references/methodology.md` § "Resolving a row by subject" names,
      and the verdict line reports that the ledger carries a second.
    - **The candidate's own evidence URLs.** Every one of them client-owned — the company's own
      site, registers, filings, press, job board, T&Cs, and its comparison, partner and integration
      pages. A fact assembled entirely from the reader's own pages is a fact the reader has.
  - **The rival's side.** The fetch below finds the subject company naming **the client itself** as
    a customer, partner or integration. The same fact from the other end: a company that lists the
    client in its own partner directory or brand registry has already told the client's team.

  **The client's own name is the whole trigger.** A page that names the client's partners, brands,
  resellers or channel is `not named`: the client's side decides that candidate, and the verdict
  line says so. There is no route from a page's contents to KNOWN other than the client's name on
  it — a screener that argues one hop out reaches KNOWN on a page the reader may never have seen.

  A `blocked` or `unknown` fetch decides nothing. Screen that candidate on the client's side alone
  and carry the fetch state into its verdict line.
- **TRUE.** Ledger IDs support the sentence, counterexample rows included. A row that narrows it
  narrows the sentence.
- **DECISION-CHANGING.** It changes a decision this reader makes this quarter. Name the decision,
  cited `file:line`: a line of `00-reader.md`, or a `Changes:` line of `02-questions.md`. A
  decision the screener supplies counts as none.

## The fetch: one page per candidate, before the screen

For each candidate the screener fetches the **subject company's own site** at the URL it was handed
— the partner, integration or customer page where `$BRIEF_ROOT/03-selection.md` records one,
otherwise the homepage — and searches the returned text for the client's name. Fetch and search in
one command, so what enters this context is the matching line and the HTTP code, not the page.

A candidate whose subject is the client itself skips the fetch and is screened on the client's side
alone: a company naming itself on its own pages is the client's side by another name.

Three states, and the third is the one that matters:

| State | What it means | What the screen does |
|---|---|---|
| `named` | the fetched page carries the client's own name as a customer, partner or integration | KNOWN, automatically |
| `not named` | the page was fetched and the client's own name is not on it, including a page that names the client's partners, brands or channel | the client's side decides |
| `blocked` / `unknown` | the fetch refused, or the company's partner directory is a page this run never opened | the client's side decides, and the verdict line says which |

A URL the screener was not handed is not fetched and never constructed. `blocked` carries the HTTP
code; `unknown` carries the paths tried. A 200 that returns no readable body — a page whose text
renders in the browser — is `unknown` too: it was reached and not read. An unopened directory is
not an absence of the client's name, and reading it as one manufactures NEW verdicts out of pages
nobody read.

**Cost: <$2, and the fetches are not the risk.** The first screen with fetches inside it measured
**$2.99**; its nine fetches cost about **$0.03**. The bill is this context and this return, so two
bounds hold it. Both were measured on that screen, not estimated.

- **Read the ledger a row at a time, never whole.** `claims.jsonl` grows every run — 197 rows to
  325 in one replay, 188 KB, about the whole of that screen's 51,015 cached-input tokens, carried
  to grade four sentences. Take each candidate's cited rows from the dispatch, then read the ledger
  twice — `grep` for the subject company's name with the sentence's key nouns, and
  `claims-check.py --client-row` for that company's client-owned row — and read only what comes
  back. Both commands put one or two rows in this context and never the file: the resolver reads
  the ledger itself and prints a single line. A `grep -c` returning 0 is the evidence for
  UNSUPPORTED, and it is firmer than a skim of 325 rows. Reading the file whole makes the bill
  scale with a ledger nobody caps.
- **Return the terse form.** `$BRIEF_ROOT/05-screen.md` is a verdict table, then per candidate one
  line per test and one fetch-state line: at most eight lines per candidate, no counterfactual
  section, no restating of the candidate sentence. The $2.99 screen wrote 145 lines and 19,062
  output tokens — $1.43 of the bill, against a template asking for one sentence of reason.

Report your own input, output and cache token counts with the verdicts, in the same units, so the
next run measures this bound rather than inheriting it.
