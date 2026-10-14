# Critique rubric

One wave, four critics, in parallel, in fresh contexts, on the **final built text**. The input is
the page's text plus its screenshots for H7, never a draft and never the orchestrator's
summary. No critic sees the author's reasoning or a "what changed" block.

| Critic | Reads | Checks |
|---|---|---|
| **Truth** | brief, `claims.jsonl`, research files by line | every claim has an ID and matches it with its qualifier; `claims-check` output; page-1 claims against every table cell; quantifier counterexamples; negative cells carrying the qualifier; every figure ending in round zeros against the source string in its own ledger row, because a rounded figure the source did not round is the commonest invented number; each recommendation against its own Open Question; threat level against its action verb; cohort coverage; the distribution claim and each rival finding carrying their derivation, per `references/briefing-template.md` section 2, with a conclusion that arrives without its reasoning and rows booked under H6 |
| **Labels** | the `label-fit.py` dump | every h2, column header, row label and bold claim-header covers all its children and names what they share, in the reader's vocabulary |
| **Hiring-manager red-team** | brief and screenshots, `<run>/00-reader.md`, `01-hiring-rubric.md` | H1-H8 in the reader's persona, 90 seconds; the three strongest objections; the one line that lands; the three most machine-sounding sentences |
| **Voice** | brief, `02-voice-card.md`, `05-exemplars.md`, `voice-lint` output | P1-P8 by sentence, then P3 again across each section's bold claim-headers read together; the verdict question first, "does this sound like a person with a view talking to you?"; rhythm signals as evidence; quote any short sentence that reads bolted-on, and every claim-header that shares a frame with another in its section |

## The finding row

Each critic appends tab-separated rows to `<run>/findings-ledger.tsv`:

```
id  critic  rule_id  severity  quote  location  fix_old  fix_new  claim_ids  status
```

- **No quote, no deduction.** `tools/critique-check.py` drops any row whose `quote` is not a
  verbatim substring of the page text the critics read, `08-text.md`, and counts the drops against
  the critic. A quote holds 8 or more letters or digits, or is a whole line of that text: a short
  cell, label or heading is quoted with its whole line. An absence finding quotes the row where the missing thing belongs.
- **The rule is named.** `rule_id` exists in `quality-bar/`: a pillar (P4), a refusal (RF1), a
  rubric line (H2), or a regex id (`process_subject`). A finding with no rule is logged as a
  *candidate rule* for the compound step, at severity MINOR.
- **Fixes are machine-applicable,** as `fix_old` → `fix_new`. Any new claim in `fix_new` carries
  claim IDs or the row is rejected.
- **Severity is the maximum across every rule the finding matches.** This closes the silent
  downgrade: a finding that check 5 made a MUST-FIX was booked under check 3 as a
  SHOULD-CONSIDER, and it shipped.
- **No manufacturing.** If you find nothing blocking or material, say so plainly. Each critic still
  quotes the **three weakest sentences** as MINOR. That counters sycophancy without inventing
  defects.
- **Critics do not write the brief.** A critic's proposed lede goes into the thesis-lock candidate
  pool, never into the text. Domain claims from the red-team persona are hypotheses (RF4).

Severities: BLOCKER, MATERIAL, MINOR.

## Blocking outright, whatever else scores well

- any refusal RF1-RF12
- any voice-lint pattern hit (the rhythm signals are advisory)
- any claims-check miss
- any label that does not cover its children
- any contradiction between page 1 and a cell
- H1, H2, H4, H5 or H7 failing
- clipped or broken text, a matrix that scrolls at 1440 px, or a broken link

## Pass rule

No averaged score. Each dimension reports PASS or FAIL with counts. **Pass = 0 BLOCKER and ≤2
MATERIAL across all critics.**

**Routing, by thesis quote.** A row is **thesis-level** when its quote is verbatim in the locked
thesis: the `## Locked thesis` section of `<run>/05-thesis.md`. A thesis-level row goes back to
**thesis-lock**, as `routed@5`. Every other row goes to **one fixer**, whatever its rule, RF1 and
H2 included, which applies every open row in one allocation-neutral pass.
`tools/critique-check.py` drops a `routed@5` row whose quote the section lacks, under `route`. A **diff-scoped re-check**, truth and voice
on the changed sentences and on every sentence naming the same entity, then closes each row as
`fixed@<sha>`.

**Final verifier.** A fresh Opus agent runs on the post-fixer sha256 and writes
`correctness-<sha256>.md`. Any later edit invalidates that file.

**Delivery.** `tools/deliver.sh` requires that file, with PASS, for the exact bytes and page. That
PASS carries the open-row rule (`10-final-verifier.md` step 4); `deliver.sh` counts no rows.
