# Competitive Analysis Methodology

## Goal

Generate an intelligence briefing that answers: **How do competitors position relative to me, and what changed?**

## Research Depth

As deep as it takes. There is no fast mode and no configured depth setting.

- Every competitor gets its own extraction, fanned out across parallel subagents, so depth costs
  wall-clock time rather than quality.
- Sources are the competitor's own pages plus third-party press, funding data, news and community
  sentiment.
- Discover the candidate pool wide, homepage-validate every candidate before scoring, then cut to the
  N with the tightest ICP and positioning overlap. A past run scored 39 candidates; that is a floor,
  not a target.
- The ICP claim rests on at least three independent signals, and the brief names the pages each was
  inferred from. One signal is not an ICP.

## Discovery Phase

Figure out which pages matter for each company:
- What pages reveal positioning, pricing, customers, hiring, strategy?
- Check sitemap.xml and robots.txt
- Follow strategic links, skip noise
- Track which pages you attempted and which failed

## Third-Party Intelligence

Find external sources that validate or extend website findings: funding, metrics, sentiment, rankings, recent news.

Use WebSearch. Stop at 3-5 quality sources per competitor or after 5 searches yield nothing new.

## Extraction: the core, plus the questions

Two lists, and no third. The **core** is the same six dimensions on every run, because the brief's
spine cannot be built without them. The **questions** are this run's, from
`$BRIEF_ROOT/02-questions.md`, and they are where the brief's argument comes from.

<!-- illustrative -->
A fixed sixteen-dimension list was the previous rule. On the Northwind run it cost $106, about 14% of
the run, and roughly half of what it produced never reached the page — one whole extraction, at
$11.49, was discarded unread. Research that is cut down afterwards is research bought twice.

Report a status for every dimension in both lists:

- **[Extracted]** — found, with its quote and URL
- **[Blocked - <code>, tried <paths>]** — the page refused to serve
- **[Not found - checked X pages]** — the pages answered and did not carry it
- **[Not applicable]** — does not apply to this company, with the reason

### The core (six, every run)

1. **Positioning** — hero headline, tagline, and the bet the company is making, in its own words.
2. **Buyer and ICP** — who it sells to, named on its own pages, primary and secondary; and the
   overlap with the client, with the pages each signal was read from.
3. **Product and pricing shape** — what is actually bought, the revenue model, published tiers and
   currency, and the enterprise signals (custom pricing, "contact sales", compliance pages).
4. **Proof** — named customers and partners, each with its evidence grade: case study > logo plus
   quote > logo > press mention. Metrics only as the source states them.
5. **Stage and reach** — funding stage and total raised with its source, headcount proxy, and the
   markets it serves.
6. **Posture** — its claim on this run's decisive axis, and what is shipped against that claim.
   The axis itself comes from `$BRIEF_ROOT/02-questions.md`; see `posture_axis` in the schema below.

### The questions (this run's)

Every locked question in `$BRIEF_ROOT/02-questions.md` carries an answer shape: the single most important
dimension, a verbatim quote, and a URL. Extract exactly those fields.

The competitor file `comp-<slug>.md` stays **12 KB or less** and opens with an Answers table, one
row per question: `question_id | one-line answer | URL`. The table is what downstream stages read.

An MKT1 tool is called only where the tool maps to a locked question.

## The claims ledger

Facts leave research as rows, never as prose. One JSON object per line in
`$BRIEF_ROOT/claims.jsonl`:

```json
{"id":"C-014","subject":"","claim":"","qualifier":"","scope":"5 of 7","metric":"<entity>:<counted thing>","quote":"","url":"","source":"comp-enode.md:88","state":"verified","exclusive":false,"lang":"en"}
```

| Field | Holds |
|---|---|
| `id` | `C-nnn`, unique in the ledger, and the only form in which this fact travels |
| `subject` | the one company this row is about, spelled as `$BRIEF_ROOT/03-selection.md` records it — the company's own spelling, never a slug or a shortened form. Required on every row, blank on none; the client's own rows carry the client |
| `claim` | one sentence, narrowed until the evidence carries it |
| `qualifier` | the word that makes it true: `further`, `publicly`, `as of <date>`, `GB only` |
| `scope` | the bound: `5 of 7`, `all 12 listed`, `1 market of 3` |
| `metric` | `<entity>:<counted thing>`, keyed on what the number counts and not on the row's `subject`: one list counted from two companies' rows is one metric. Both halves are required wherever `claim` holds a numeral or `scope` counts the subject. A scope count of the evidence read, such as `1 page read` or `1 press release`, owes no metric, unless the metric's counted thing names that unit (`client:job posts`). The scope's count is its first subject count in digits, never a date, and in `k of N` that count is N, the population: `7 of 8 partners` counts 8. Two rows on one metric with different counts contradict each other, and the lint reds both IDs; reconcile to one count |
| `quote` | the source's own words, verbatim |
| `url` | a page actually fetched, never constructed. An `unfound` row read across several pages, with no one page to name, has an empty `url`: it is ledger evidence only and is never cited on the page, and `budget-check.py --allocation --web` reds a slot or shape that cites it. Where the absence was read off a closed list, the row takes that list's URL and can be cited |
| `source` | `file:line` in this run's own files |
| `state` | `verified`, `unfound`, `blocked`, `named` or `not named`. The last two are a client-owned row's: a page the client controls names this company, or it does not |
| `exclusive` | true only where a closed list was read and the absence is itself the finding. A `not named` row is that case and carries `true`; the lint reds one that does not, and reds one whose `source` or `scope` is empty — the register the list was read off, and the bound it carries |
| `lang` | the ISO 639-1 code of the `quote`'s language: `en`, `fr`, `de`. Required on every row; a value that is not two lower-case letters reds as no ISO 639-1 code (L16) |
| `gloss` | required where `lang` is not `en` on a `verified` or `named` row: an English rewording of the `quote` that holds no quote mark (`Its page says it works with Électricité Réseau`). The page prints a lead naming the language, from `lang` (`Paraphrased from French:`), so the gloss never names it. The `quote` stays in the original as proof; the brief prints the gloss unquoted, and quotes only an `en` row's words, verbatim. A gloss is page text, printed on a card, so it meets the page's voice rules: no semicolon, and the world as its subject, never the research (no "pages read"). The lint reds a missing gloss or one holding a quote mark (L16), a gloss the page's own lint fails (L18), and a curly-quoted passage in the brief that is in no `en` row's `quote` (B4). Two more rows carry a gloss, because the page shows one where it cannot show the quote: an `unfound` row, printed after `Searched, not found:`, and an `en` row whose `quote` is empty or a page fragment (it holds a `|`, a `{`, an `[img`, a straight `"` or a Markdown link's `](`, the list `build/web.py` `QUOTE_FRAGMENTS` holds), or does not on its own say what the claim says, such as a heading, a list item or a date standing for a count or a finding, printed after `Paraphrased:`. A heading that states the claim stays a quote. |

**One name, one spelling (L17).** Every row spells a name the way its owner does, as that company's
snapshot shows it. The page prints a name as a logo label and a matrix column, so a variant shows
twice. Across `subject`, `claim`, `qualifier`, `scope`, `metric` and `gloss`, the lint reds two
names that match once case, spaces and hyphens are dropped but are spelled differently: `Volt
Wise`, `Voltwise` and `VoltWise` are one name. A changed first letter (sentence or title case) is
not a variant. `quote` stays verbatim and is not graded. The lint reads a run of capitalised words
as one name, so a variant inside a longer run (`Voltwise Jun`) goes unseen. Respell those by hand.

### Resolving a row by subject

A row is found by its `subject` field and never by a substring search over the line. Free text
carries other companies' names — a `quote` names the company beside the one the row is about, and
one company's name is a strict prefix of another's — so a substring match resolves the wrong row,
silently, in whichever direction the reader happened to see first.

`python3 tools/claims-check.py --client-row "<company>" <claims.jsonl>` prints the one client-owned
row — `named` or `not named` — whose `subject` is that company, and nothing else. Exit 0 is that row
on stdout. Exit 1 is no such row: nobody asked the question, and silence is never read as an answer.
Exit 2 is a ledger it could not read.

**One client-owned row per subject**, written by stage 4 and graded by the lint: a second row for
the same company is a finding, not a choice. Where a ledger carries more than one anyway, the
tie-break is fixed, so two readers resolve the same row — a `named` row outranks a `not named` one,
because a page that names the company is evidence and a closed list that does not is an absence, and
among rows in the same state the lowest `id` wins. The ids that lost go to stderr, never unreported.

**A ledger carrying no client-owned row at all is a finding too**, under `--require-client-rows`.
A run whose client-owned pages name no cohort company records that as a `not named` row off the
closed list it read, carrying `exclusive` true, the register in `source` and that list's bound in
`scope`: the absence arrives with its evidence, and an empty ledger is what leaves the client's side
of KNOWN unasked. An absence row missing either field is the same silence one line longer, and the
lint reds it whether or not the flag was passed.

A prompt carries claim IDs and paths, never a restated fact. That is what stops a qualifier falling
off between hops: there is no hop at which the sentence is retyped.

<!-- illustrative -->
On the Northwind run "signing anything *further*" became "signs nothing" across four hops and was
delivered.

`python3 tools/claims-check.py --ledger <claims.jsonl>` grades the ledger's own shape; research
adds `--require-client-rows`, which reds a ledger holding no client-owned row.
`python3 tools/claims-check.py --check <text.md> <claims.jsonl>` grades every numeral and every
quantifier in the page's authored text (`build/web.py --text --authored`) against it.

The ledger opens with the **client's own claims**, seeded by stage 1 from the `00-reader.md` KNOWN
table under a company-stated qualifier, before any competitor row exists. Research is written about
the cohort, so without that seed the one evidence class that proves a reader already knows
something is the class the ledger never carries. `references/stages/01-reader-frame.md` § "Both
places" owns the rule and the qualifier's wording.

## Logos and source labels

The page shows a logo per company and a label per source. Stage 4's lead writes both after the
ledger is merged (`references/stages/04-research.md` § Page inputs), and `build/web.py` reads them
as written.

### Logos: `$BRIEF_ROOT/logos/`

`tools/fetch-logos.py` writes one record per cohort company, the client included, to
`logos/logos.json`, and keeps each logo verbatim as `logos/<slug>.<ext>`, SVG or PNG. A logo comes
from that company's own saved page under `pages/`: an `<img>` source or an inline `<svg>` read off
the page, never found by a search or typed.

| Field | Holds |
|---|---|
| `company` | the name, verbatim from the company's snapshot |
| `slug` | the key `brief.json` names the logo by |
| `kind` | `img`, `svg` or `wordmark`; a wordmark carries `reason` |
| `page_file`, `page_sha256` | the saved page, and the hash its `pages/index.tsv` row carries |
| `href` | the `src` exactly as the page writes it; null for an inline `<svg>` |
| `resolved_url`, `status` | where `href` resolved, and the fetch's status; null for an inline `<svg>` |
| `file`, `sha256` | the logo file and its hash; `file` is null on a wordmark |

**The gate** is `logo_gate` in `tools/brief-check.py`, written once and imported: `href` is a
substring of the page's bytes (for an inline `<svg>`, the logo's own bytes are), and `page_sha256`
matches the page's index row. `fetch-logos.py` reds a record that fails it. A company with no
gated logo gets a wordmark record instead: no saved page carries a logo, the fetch failed, or the
file is neither SVG nor PNG. The page then sets that company's name in type.

### Source labels: `$BRIEF_ROOT/sources.tsv`

Two tab-separated columns, `url` then `label`, under that header row: one row per distinct `url`
the ledger cites. A label names the page, never a fact on it: the owner's name as its snapshot
spells it, then the page's kind (`<Company> pricing page`, `<Company> and <partner> release`). At
most 31 characters. The page prints it in the print source list and beside each card's evidence.

## Snapshot Workflow

For EACH competitor, AFTER extraction:
1. Write current state to `$BRIEF_ROOT/snapshots/{domain}.json`. A run sets `BRIEF_ROOT`, and
   `build/build.py` then reads its cohort from there and never from `output/snapshots/`.
2. There is no previous snapshot of this company to diff against. The clone does ship
   earlier clients' snapshots (13 tracked entries under `output/snapshots/`, measured
   2026-09-03), and they are not this run's evidence: nothing in the brief may rest on
   them. Set `"captured"` to today's date in every snapshot you write, because that
   field is how the gate separates this run's evidence from the clone's.
3. "What Changed" therefore reports dated moves observed in this run, not a diff.
4. **`sources` is generated from the fetch log, not written from memory.** The agent that fetched
   a page records it — URL, type and date — as it fetches, and the snapshot's `sources` is that
   list. A `sources` block assembled afterwards is how a URL nobody fetched reaches the brief, and
   every URL in the brief must appear verbatim in one of these files.

### Snapshot Schema

```json
{
  "domain": "competitor.com",
  "name": "Competitor",
  "captured": "2026-01-16",
  "research_depth": "deep",
  "positioning": { "headline": "", "tagline": "", "value_proposition": "" },
  "target_audience": { "primary": "", "secondary": "" },
  "differentiators": [],
  "where_company_is_stronger": [],
  "pricing": "",
  "customers": { "named": [], "evidence": "" },
  "business_model": { "revenue_model": "", "gtm_motion": "", "monetization_signals": [] },
  "company_stage": { "employee_count": "", "funding_stage": "", "total_raised": "", "market_maturity": "" },
  "integrations": { "named": [], "gaps": [] },
  "posture_axis": "the run's decisive axis, from 02-questions.md",
  "posture": { "claim": "", "shipped": [], "unshipped": [] },
  "content_types": { "blog": {}, "video": {}, "podcast": "", "documentation": {}, "social": {}, "community": {}, "gated_content": false, "events": {} },
  "growth_engines": { "primary": [], "signals": {} },
  "hiring": { "open_roles": [], "departments": [], "growth_signals": "" },
  "recent_moves": [],
  "third_party": { "analyst_coverage": {}, "sentiment": {}, "metrics": {} },
  "threat_assessment": { "level": "HIGH|WATCH|LOW", "trend": "", "key_gap": "", "evidence": [] },
  "coverage": { "extracted": [], "blocked": [], "absent": [] },
  "sources": [{ "url": "", "type": "primary|research|news|data|sentiment", "date": "" }]
}
```

A snapshot written before 2026-09-18 carries `ai_posture` where this schema now says `posture` and
`posture_axis`, and `connectivity: {banks, erp}` where it says `integrations`. Nothing migrates or
flags one, and nothing needs to: no code reads either field — measured, `grep -rn
'ai_posture\|connectivity' build/ tools/` returns nothing. Read an old snapshot's content under the
new names and say so in a coverage row.

`name` is how the gate matches a briefed competitor to its evidence: check 5 in
`build/build.py` slugs the name in the brief's Threat Landscape row and looks for a
snapshot whose `name` slugs the same, falling back to the filename stem, so a snapshot
written without `name` is matched only by luck. `captured` is how check 4 picks the run
cohort: the newest `captured` date present wins, so evidence left behind by an earlier
run for a different market cannot back a claim in this brief.

The company's LinkedIn page is recorded in `sources`, not in a field of its own: the
schema already carries it, and every snapshot in the exemplar cohort already writes it
that way. The rule is where that URL comes from. It is the
`linkedin.com/company/...` href read off the company's own site footer
during extraction, never a URL built from the company's name, and recording it is what
makes the page attributable later: an artefact that needs the company's followers reads
the href the snapshot kept and resolves the company through the identity key
`python3 build/build.py --slug "NAME"` prints, constructing nothing. A snapshot whose
`sources` carries no `linkedin.com/company/...` entry has not recorded where the page
came from, so the footer must be read again at the time of the call.

<!-- illustrative -->
The exemplar cohort writes the entry as `{"url":
"https://www.linkedin.com/company/atlarhq/", "type": "data", "date": "2026-09-02"}` in
`output/snapshots/atlar.com.json`.

## Self-Monitoring

Also monitor the user's own company:
- Logo/partner changes
- Messaging shifts
- Feature announcements
- Customer additions/removals
- Pricing changes

Its moves may be reported under the company's own name, verbatim. A hiring-company row may appear
in a table, What Changed included, and it never carries the section's main point.

## Coverage

Track, per competitor, which dimensions were extracted, from which pages, and at what confidence.

Report what failed and why. A 404, a 403, a page that does not exist and a page never attempted are
four different findings, and the brief must say which. Never report a dimension as absent when it was
blocked.

Coverage reaches the reader as the matrix legend and cells, each caveat beside the claim it limits
(`references/brief-contract.md` Part 2). Conflicts between sources go to Open Questions.
