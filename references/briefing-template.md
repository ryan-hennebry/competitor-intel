# Brief structure

The brief is a web page with variant T's anatomy, `references/brief-contract.md` Part 2, which
`build/web.py` renders from `$BRIEF_ROOT/brief.json`. The template draws the banner, bar, title
block, contents rail, Also built by Ryan, print Sources and footer. The run authors the five
sections below, in this order, and every page carries all five. Every cap on a section is
`build/web/brief.schema.json`'s and is not restated here.

Coverage Notes is no longer a section. Each caveat on the evidence sits in the matrix legend or
beside the cell it limits, because a caveat at the claim reads as rigour and one at the end reads
as hedging (`T:research/24-content-audit.md:230-258`). Where a rule below names Coverage Notes, or
a slot the page does not carry, as the place a fact lands, it lands in the matrix legend or beside
its cell.

1. **Quick take**, fixed heading, `quick_take`: the thesis, then the ICP, each paragraph a bold
   lede and its body. The thesis names the single most important thing and what to do about it;
   one sentence states who the client's buyer is, citing the three or more pages that ICP was
   inferred from (R16). Every referent named, every claim supported by the evidence below it. The
   ICP is a paragraph in this section and never a section of its own.
   The **map** follows, drawn from `map`: two yes-or-no questions, each serving a locked question
   in `02-questions.md`, and one answer per company per question, each with its claim. No heading
   prints over it.
2. **Recommendations**, fixed heading, `recommendations`: at most three, ordered by leverage. Each
   opens with a bolded full-sentence claim (`test`), then why, then the next step. At least one of the three is the distribution claim: it names where
   to reach the buyer, or what it costs not to be findable, and every number in it is a row of this
   run's `$BRIEF_ROOT/claims.jsonl`. Its source is `references/mkt1-digest.md` § Channel fit,
   applied to this run's fetched evidence (`references/stages/04-research.md` step 9). It reaches
   the page with its derivation: the Channel fit reasoning and the rows it rests on, not only the
   conclusion. A rival finding drawn from `references/mkt1-digest.md` § Competitive extraction
   reaches the page the same way, with the fetched evidence it rests on. A conclusion that arrives
   without its derivation gains it in the brief's own register; the finding stays. Register checks
   10 and 11 (`docs/history/review/08-register.md`) are worked examples of these rules, not their
   enforcers.

   <!-- illustrative -->
   How a delivered brief filled that shape, as calibration of depth and never as content to
   reuse. It made its second recommendation the distribution claim, on a client blog stalled since
   10 April 2026 at 4,781 LinkedIn followers against a named rival's 8,394 (`build/briefing.md:24`).

3. **Moves**, authored heading `moves_heading`, `moves`: one row per rival with a move or a silence
   worth naming. The hiring company's own moves are facts it knows, so they stay off this table.
   Dated moves observed in this run. Columns: Company,
   Change or silence, What it means and action, each row tagged Act or Watch.
4. **Matrix**, authored heading `matrix.heading`, `matrix`: capability comparison, one column per
   company. The matrix argues the brief’s thesis in rows instead of asserting it in prose.
   - There is no second thesis to satisfy. “Thesis” already names the opening sentence of Quick
     take and names nothing else: `docs/history/pipeline.md` Phase 4 authors it, `tools/thesis-check.sh`
     enforces it and the run's own thesis sidecar retains it. The matrix argues that thesis, so rows
     are chosen so a reader sees where the hiring company wins and where it does not.
   - Up to six rows, the schema's cap. Each row separates a win from a gap; a row that separates
     nothing is padding, and fewer rows say so in the legend.
   - Every row is a capability a buyer chooses on. Client count, office location, headcount,
     founding year and funding are firmographics and are never rows; one that carries a finding is
     a cited sentence in Quick take or a recommendation. The measured failure is “Clients: 1 /
     Offices: London” (same file, §2).
   - Cells are fragments within the schema's word cap: “No product found”, “File pass-through”,
     “Yes, fee by tier”. A cell the evidence cannot fill is marked `unknown`, never left blank.
   - The legend carries the caveats Coverage Notes held.
5. **Open questions**, fixed heading, `open_questions`: the questions the research could not
   close, phrased so the reader can act. The brief's last section.

## The slot catalogue

`references/headings.json` is the slot catalogue as data, and the list below is the same catalogue
in prose: `build/build.py` and `tools/headings-check.sh` reconcile the two line for line and raise
where they disagree. The list's order and its `spine` and `menu` words are the retired format's,
kept until W23 removes it; the page's order is the one above. The retired slots' rules are at
`git show a7669ec:references/briefing-template.md`.

1. `quick-take`, spine, default heading `## Quick Take`: section 1 above.
2. `recommendations`, spine, default heading `## Recommendations`: section 2.
3. `what-changed`, menu, default heading `## Where each rival is moving`: section 3, Moves.
4. `threat-landscape`, menu, default heading `## Threat Landscape`: retired format only.
5. `open-questions`, spine, default heading `## Open Questions`: section 5.
6. `say-do`, menu, default heading `## What They Say, What They Do`: retired format only.
7. `matrix`, menu, default heading `## Competitive Matrix`: section 4.
8. `stage-reach`, menu, default heading `## Stage and Reach`: retired format only.
9. `coverage-notes`, spine, default heading `## Coverage Notes`: retired format only; its caveats
   sit in the matrix legend and cells.
10. `sources`, spine, default heading `## Sources`: retired format only; the page generates its
    print Sources list from every cited URL.
11. `map`, menu, default heading `## The map`: the map in section 1, under no heading.

## The heading a run writes

The slot ID is for the run and never appears on the page; the heading is the words a founder reads.
Stage 7 writes the two authored headings into `brief.json`, as `moves_heading` and
`matrix.heading`. `tools/brief-check.py` grades their word cap, the contents rail's character cap
and their sentence case (H1), and `tools/web-check.py` `layout.rail` grades the rendered rail.

The five spine headings are the literals above and a run does not rewrite them. They are the
furniture a reader reaches for, and a brief that renames Sources has moved it.

A menu heading is the run's to write, under four tests:

- It covers every row beneath it. A label wider than its rows promises a table the reader does not
  get; a label narrower than them hides rows under a name that does not reach them. That is P7 in
  `quality-bar/02-voice-card.md`, and a heading is a label like any other.
- It names what the columns jointly argue, not the topic they happen to share. A heading naming a
  topic survives a table that no longer carries it, which is how a heading and its rows come apart.
- It is in the reader's words, the vocabulary the role uses for the thing, and never a tool, a phase
  or a file name, which `quality-bar/03-refusals.md` refuses on the page outright.
- It stands alone in the scan layer, the rule `bash tools/scan-layer.sh --check` holds as S2: a
  heading opening on a connective or on a pronoun parses only from the prose above it, and a reader
  who scans never reads that prose.

On the page the run writes two headings, `moves_heading` and `matrix.heading`, each under these four
tests and the schema's word cap, and the job description decides both (the operator, 2026-10-09).

The catalogue default ships where the run has nothing better to say, and it is a default rather than
a ceiling. The `say-do` default names no axis, so a run whose `posture_axis` is the decisive
question of the market writes that axis into the heading and leaves the default behind.

## What the brief looks for

Five finding types the run seeks by name, and two rules of wording that ride with them. They sit
here rather than in `quality-bar/02-voice-card.md` because each governs who is in the set and which
facts are gathered, and a voice critic reading the finished page cannot test any of them.
**Measured 2026-09-18, the exemplar carries none of the five**, which is why they are template
rules and not card rules: a card may not carry a rule that reds the exemplar, and a template is the
thing the exemplar is asked to improve on. Each carries its own escape, so a market that offers
none of a type is written up as an absence and never blocks a run.

- **A convention the whole set shares.** One sentence naming something all or most of the set do
  the same way: the same claim, the same page type, the same channel. Say what breaking it would
  look like, because a shared convention is the place the client can differ. The exemplar's own
  lede is this shape, which is how the type is calibrated.
- **An alternative that is not a direct rival.** At least one thing the buyer might choose instead
  that is not a venture-backed competitor: an incumbent, a spreadsheet, a service, doing nothing.
  Where the market offers none, Coverage Notes says the search found none.
- **A complement.** At least one company with the same audience that could accelerate the client
  rather than beat it, framed as a partner and not as a threat, or Coverage Notes says none.
- **Who names whom.** Which companies name the client on their own pages, and whether the client
  names them back. A rival positioned against the client is a different fact from a rival that has
  never heard of it. Where nobody names anybody, `## Threat Landscape` says so.
- **A shared customer.** Any logo on two companies' sites in the set, which is direct competitive
  contact, or the plain statement that no customer is shared.

Every company in the set is also answered on three questions: who it is for, what it is, and why it
claims to be better. The `say-do` and `threat-landscape` slots carry them
between them. Where the company's own pages do not say, the brief writes "Not stated" rather than
dropping the question, because a missing answer is a finding and a missing row is an oversight.

Two rules of wording:

- An audience statement names both a kind of company and a role inside it. A role alone is a
  persona and a company alone is a segment, and neither tells a rep who to call. Write the role in
  the words the reader uses for it and never as a code, which is `02-voice-card.md` P7.
- A competitor claim carries the day its source gives it, and the document stamp dates the rest.
  The strict form, every competitor claim carrying its own date, is measured red on the exemplar's
  `## Competitive Matrix`, which carries none, so it does not land. `## How the brief stamps time`
  below owns granularity and is what anchors an undated cell.

## Word discipline

The brief's length is the schema's caps. Every word, item and row bound in
`build/web/brief.schema.json` is live T's maximum, and `tools/brief-check.py` reds a `brief.json`
past any of them. A cap is a ceiling and never a target: density, not length, is the standard, and
a section with less to say writes less.

- There is no per-competitor word floor and no per-competitor detail section. A competitor earns space
  by carrying a finding, not by existing.
- There is no separate comparison-table appendix. The map, the moves table and the matrix are the
  comparison, and three tables is the ceiling.
- Bolding is one scan-anchor per context. In prose sections a bold run is a full-sentence claim-header;
  elsewhere it is a 2 to 5 word noun phrase at the head of its unit.
- No em dashes, no straight quotes. Line measure runs 60 to 69 characters.
- The first two words of every table row and every bold claim-header are a specific noun phrase, so a
  reader scanning a column or scanning the bold lands on a subject and not on a label. Prose
  sentences are released from it, because it is a scanning aid and was never a register: it bans And,
  But, So, Not, a subordinate clause and a one-word fragment, which is most of the rhythm the voice
  runs on. The exemplar breaks it in its own first line, `build/briefing.md:14`, “Not one of the six
  says where its agent stops.”, and again in both Open Questions at `:51-52`. It is not an enduring
  contract: `docs/PLAN.md` section 3 does not carry it and `audit()` does not assert it. Do not
  re-tighten it over prose on the assumption the narrowing was an oversight.
- At most one semicolon per prose section; the exemplar’s count across all four is zero. Reach for a
  full stop instead, because two sentences carry a judgement that one clause-chain buries. This is
  not licence to bring the em dash back: it stays banned and gate-enforced at `build/build.py:473`,
  and the semicolon became the default connector only because the em dash left and nothing named it.
- Every prose section carries at least one sentence saying what the facts mean or what to do, not
  only what is true. The exemplar calibrates it: “Answering that costs a page”, and “a
  control-model page is the post that restarts it”. The concision pass removes padding, never
  stance, and never a recommendation's `next_step`, which the schema requires.

## The register

The brief is written as Paul Graham writing to a founder, inside Emily Kramer’s MKT1 frame. That
target was stated once, in one run’s evidence at `output/research/initech-run/31-brief-tone-audit.md:4`, <!-- illustrative -->
and in no file a run reads: a grep of `AGENTS.md`, `CLAUDE.md`, `docs/`, `references/` and `build/`
for Paul Graham returned zero hits, measured 2026-09-07 before this section landed. Half the
register is a lint: `bash tools/ai-smell.sh` greps six machine-authorship rules and a non-zero exit
blocks the build, set out at `### The two voice lints` below.

Until 2026-09-18 this paragraph said of the other half, the rules about judgement and what a
sentence has to earn, that no gate greps for it and a draft that ignores it renders green and reads
wrong. That is no longer true, and the sentence is replaced rather than left standing. `bash
tools/voice-lint.sh` greps `quality-bar/04-banned-patterns.tsv`, whose rows carry the half that used
to be authoring standard alone: a sentence whose subject is the run, a count of pages read as
grammatical subject, an agentless passive whose implied agent is the document, a tag on the page, a
relative date. What is still judgement and still ungraded is narrower than the old sentence claimed:
whether a claim is NEW to this reader, whether a section says what its facts mean, whether a label
covers its children. Those four go to the critique wave of `quality-bar/06-critique-rubric.md`, and
`21-voice-audit.md` is the evidence that a judgement pass alone does not hold them.

The source is `output/research/round-run/21-pg-style-rulebook.md`, 585 lines drawn from fourteen <!-- illustrative -->
essays read in full. It is cited evidence and not a governing file. Its convention line, quoted
verbatim, is the marking reproduced below:

> **Convention used throughout.** `PG:` = what Paul Graham actually says (verbatim quotes, essay named). `→` = my extrapolation to this document. Do not confuse the two. PG never wrote about competitive briefings; every application is inference.

`docs/PLAN.md` section 2 puts the shipped brief above the rulebook: where the rulebook and
`build/briefing.md` disagree the brief wins, which is how fifteen of its twenty operational rules
failed to land.

### Where the calibration went

The workings, the rules that survived scoring and the fifteen that did not, and every SD and count
behind them, are in `docs/history/register-calibration.md`, which no run loads. The live standard is
`quality-bar/`: the pillars and their tests in `02-voice-card.md`, the refusals in `03-refusals.md`,
the regex rows in `04-banned-patterns.tsv`, and `quality-bar/decisions.md` for why a row is worded
the way it is.

### Coverage Notes is written to the reader

**Coverage Notes states the limit of the evidence, never the disagreement between two internal
artefacts, and never an artefact the reader cannot see.** The rule is register check 5,
`docs/history/review/08-register.md:146-148`, whose two sentences are the source and are reproduced
here verbatim:

> Coverage Notes is written to the reader about the coverage, never about the process that produced it. State the limit of the evidence, not the disagreement between two internal artefacts.

Until this slice it lived only there, in a pass that reads the draft after the words exist, and a
pass read after the words exist cannot stop a run writing them. That is why the standard is carried
here as well, in the file a run has open while it authors.

**The measurement that forced it is a reallocation and not a length.** Measured at
`docs/PLAN.md:1244`, the shakedown’s Coverage Notes ran 147 words against the exemplar’s 93,
**+58%**, and 147 against its own Quick Take’s 143, the only meta section in that brief longer than
the thesis. Every section that shrank on that run was a content section and every one that grew was
a meta section, so the brief did not get longer, it moved words from what the reader came for to
what the pipeline wanted to explain. The offending lines are
`output/research/initech-shakedown/artefacts/briefing-initech-shakedown.md:93`, which opens with the <!-- illustrative -->
claim-header “Two rivals are graded below their own files.”, telling the reader that a grade
disagrees with a file he cannot open, and `:97`, which says “both tools”. The register review
booked it MUST-FIX twice, at `output/research/initech-shakedown/working/12-register-review.md:149` <!-- illustrative -->
and `:386`, both against the earlier sentence at that line, and the rewrite they ordered landed
only in part: the booked sentence went, and the `:93` quoted above shipped the same shape in new
words.

**Two of these rules are mechanical, and `bash tools/coverage-notes.sh` holds them**, run as the
fifth lint of Phase 5 and as a pair of `tools/ci-gates.sh` rows; a non-zero exit blocks the build.

- C1, the process-noun blocklist, scoped to `## Coverage Notes` and to nothing else: `their own
  files`, `both tools`, `graded below`, `downgraded from`. It counts the offending LINE and never
  the term-hit, because “graded below their own files” matches two terms in one span and a per-hit
  count would score that one sentence twice. Exemplar **0** lines, shipped shakedown **2** lines.
- C2, the length budget: Coverage Notes prose is strictly shorter than Quick Take prose. Exemplar
  **93** against **166**, a 73-word margin; shipped shakedown **147** against **143**, red by four.

**Dropped from C1 before it shipped (one): `the research`.** It measured zero lines in both briefs,
so it was never calibrated red, and it collides with a rule this file already mandates: item 9 of
the section list above requires Coverage Notes to name “research this run gathered and did not use,
named with what it measured”, so a run obeying that sentence would red C1 for obeying it.

The pattern list in `tools/coverage-notes.sh` is authoritative and is what the build runs; the two
rules above name them and illustrate them rather than enumerating every trigger, so a draft that
satisfies every example printed here can still red.

**The honest limit, unsoftened.** The blocklist is a word list and the defect is a judgement, so it
catches the two phrasings measured here and not the next one. C2’s catch on the shakedown is four
words wide, so a draft that trims four words clears the budget with the same paragraph still
narrating the pipeline. The residue stays with register check 5,
`docs/history/review/08-register.md:138-154`, which grades the phrasing no word list can see. C2
bounds the authored prose and not the mandated content. `docs/history/pipeline.md:441-443` puts every
divergence defence in this section verbatim and immune to compression, so on a run with several
divergences the words C2 counts are largely words no pass may cut. The legal fix is to reword a
defence to its minimum length, editing the run's own `divergence.json` and the Coverage Notes
sentence together so the two stay byte-identical, at any point before the first build: the immunity
at `docs/history/pipeline.md:442-443` binds a compression pass and not the author, and the assert at
`docs/history/pipeline.md:447-464` grades string equality and not length, so a shortened pair passes
both. **Abandoning a divergence to reach the budget is not a legal fix**, and neither is trimming a
defence after the build; the ledger is the record of a judgement this run made about a threat
level, and a word count may not overturn it. When every defence is at its minimum, the prose around
them is what a run compresses, and C2 is met there or not at all.

**Refused: “Coverage Notes may not exceed the exemplar’s section share.”** `docs/PLAN.md:1269`,
inside V32’s block at `:1244`, offers the budget in that form as well, and that form did not land.
PLAN names no denominator, and the denominator is the whole rule. Under the counting method
`tools/coverage-notes.sh` pins, which drops table rows outright, the exemplar’s whole-brief prose
is 640 words and a tables-included figure is not computable at all; admitting tables changes the
share by roughly a factor of two, and neither method is stated anywhere in the governing set. A
threshold whose value moves with an unstated method is not a threshold. The ratio against the same
brief’s own Quick Take needs no denominator, and it is what V32’s *the operator opens* line states.

### The two voice lints

Two scripts grade voice before the build, and a non-zero exit from either blocks it.
`bash tools/voice-lint.sh` runs `quality-bar/04-banned-patterns.tsv`, which is the standard the
author writes from; `bash tools/ai-smell.sh` runs the six machine-authorship rules below. They
overlap on six patterns, deliberately: `quality-bar/` is the single source the author reads, so a
rule the author cannot see in the card is a rule the author cannot follow.

Run `bash tools/ai-smell.sh` on `build/briefing.md` before the build. It grades the author’s voice and never a quotation, because quoted spans and URLs are blanked
out of the copy it reads before any rule runs. The six rules, each shown with examples that are
among its triggers and not all of them; the complete pattern table is in `tools/ai-smell.sh`, which
is what the build runs:

- A1 over-signposting: “in this section”, “let’s dive in”, “the key takeaway”, “it is worth noting”.
- A2 stock LLM vocabulary: delve, tapestry, pivotal, multifaceted, robust, seamless, “realm of”.
- A3 a sentence-opening adverb with a comma: “Crucially,”, “Notably,”, “Moreover,”.
- A4 a hedged superlative: “one of the largest”, “among the leading”, “arguably the”.
- A5 the “not X but Y” antithesis, capped at one per brief, so the finding is the second occurrence.
- A6 a bold run-in followed by a colon. The house claim-header, a bold full sentence with a terminal
  period, is not a finding.

Five tells are deliberately outside it: tricolons, which are red on the exemplar and measured in
`docs/history/register-calibration.md`; a mechanical end-of-section summary, because the per-section judgement sentence is mandatory
here; em dashes, already gate-enforced in `build/build.py`; symmetrical constructions, which no
detection separates from the parallel evidence rows this brief is built from; and rhetorical
questions, because the `?` detection cannot tell one from `## Open Questions`, a mandatory section.
The reasoning for each sits in the header comment of `tools/ai-smell.sh` and is not repeated here.

## How the brief stamps time

Two kinds of date live in the brief and they are governed in opposite directions.

A **document stamp** is what the brief says about *itself*: the date of the sweep that produced it.
It carries month and year and never a day. The exemplar has exactly one, `build/briefing.md:124`,
`<span class="meta">All pages accessed September 2026.</span>`. The instruction is the operator’s, at
`output/research/agent-v2/A1-transcript-learnings.md:934`: “also remove the actual day everything <!-- illustrative -->
and only have september instead as otherwise it will become outdated quickly, I’m not sending it
today”. The brief is sent days after it is built, and the stamp is the one line that dates it on
sight.

On the page, the one document stamp a reader sees is the title block's run line: the fetch day and
month with no year, which `build/web.py` writes from `run_date` and reds if a year reaches the page
(`references/brief-contract.md` Part 2, item 3). Live T sets it so and wins over the month-year form
above, which is the retired format's. A run authors no date stamp of its own.

An **event date** is what the brief says about *the world*: a dated move, a raise, a post. It keeps
the day where the source gives one, because the day is the argument. A month-only event date is
what an undated source yields and is not a violation. Measured 2026-09-07, the exemplar runs 12
day-exact event dates at `build/briefing.md:14,24,32,33,35,36,37` against 4 month-only ones at
`:26,33,34,82`, so a run that read the rule as a ban on days would rewrite most of `## What
Changed` and lose the evidence with it.

**Machine-read dates are exempt and stay day-exact `YYYY-MM-DD`.** There are four: `captured` in
each `$BRIEF_ROOT/snapshots/*.json` (`references/methodology.md:119`), the single `captured:` line
at the head of the run's thesis sidecar (`docs/history/pipeline.md:541`), `BRIEF_RUN_DATE`
(`build/build.py:285`) and `EXEMPLAR_RUN_DATE` (`tools/ci-gates.sh:61`). Code reads them, not a
founder: `build/build.py:276-286` selects the snapshot cohort by exact string compare on `captured`,
and `tools/thesis-check.sh:99` rejects any shape but `YYYY-MM-DD`. A month-granular `captured`
therefore selects no cohort at all and the brief is graded against nothing.

`AGENTS.md` Provenance says “Use today’s date everywhere”, and this section is read against it as
follows: `AGENTS.md` fixes *which* date, this run’s and never a stale or invented one, and is silent
on granularity; this section fixes the granularity of the document stamp alone. Nothing here amends
`AGENTS.md`, which outranks this file, so if that sentence is ever read as fixing granularity too,
`AGENTS.md` wins and this rule goes.

That reading is measured rather than convenient, which matters because `AGENTS.md` requires a real
conflict to be reported rather than interpreted. Two things measure it. First, this repository
already uses the identical phrase of a machine-read field: `references/methodology.md:119` reads
“Set `"captured"` to today’s date in every snapshot you write”, and that field is `YYYY-MM-DD` by
contract, so there the phrase answers *which* date and is silent on how precise. Second,
`docs/PLAN.md` section 2 makes the shipped brief authoritative over every sentence of prose in this
repository whatever was written first, so a reading of a governing sentence that reds the accepted
brief is the reading that is wrong, and the accepted brief stamps `September 2026` at
`build/briefing.md:124`. An unattended run has nobody to ask, so the reading is settled here, in a
file the run opens, rather than left to deadlock every future run on `AGENTS.md`’s conflict clause.

**Refused: “prose spells the month, tables abbreviate.”** The same evidence proposes it at
`output/research/agent-v2/A1-transcript-learnings.md:199-202`. <!-- illustrative -->
The exemplar breaks it inside its own thesis paragraph: `build/briefing.md:14` reads “in a New York post dated 11 Aug 2026”, prose and
abbreviated, against `:24` “went quiet on 10 April 2026”, prose and spelled. `docs/PLAN.md` section
2 puts the shipped brief above its sources, so the brief wins. It does not land as a rule and is not
to be smuggled back in as a preference.

Half of this is a lint and half is not, the same split `## The register` above carries. Not linted:
the unanchored present-tense claim. `build/briefing.md:26` reads “right now”, `:32` reads “nothing
published since”, “now shows” and “still cites”, and `:36` reads “in twelve months”. Those are what
actually ages, and they cannot be banned because the exemplar uses all five, so they stay an
authoring standard that no gate greps for. The connection is the reason the stamp exists and is
month-granular: a reader opening the brief a week later reads “still cites” as “as of September
2026” only because the stamp says so. Write a claim that cannot survive being read against the
stamp, and the draft renders green and reads stale.

### The date-stamp lint

Run `bash tools/date-stamp.sh` on `build/briefing.md` before the build; a non-zero exit blocks the
build. Where it sits in the run order is `docs/history/pipeline.md`’s to say, and its DATE STAMP block
says it. The three checks, each shown with the shape it catches and not with every trigger; those in
`tools/date-stamp.sh` are authoritative and are what the build runs:

- Exactly one document stamp exists. Zero leaves every present-tense claim unanchored; two disagree.
- That stamp carries no day. “All pages accessed 7 September 2026” is a finding, “All pages accessed
  September 2026” is not. The check reads digits, so a day spelled out, “the second of September
  2026”, is invisible to it.
- The masthead carries no date. The check requires a date shape, a month next to a number or a fully
  numeric date, so a bare `2026`, a year-less `07/09` and a bare month word are invisible to it.

Event dates are outside all three, which is what keeps the 12 day-exact dates measured above green.
Its red artefact is `tools/fixtures/aged-brief.md`, which `bash tools/date-stamp.sh --selftest`
grades and which is never rendered and never sent. The green reference is the exemplar. A clean run
prints `DATE-STAMP-OK`.

## The scan layer

The **scan layer** is the brief’s headings and bold runs, extracted from the source markdown in
document order and read alone: what a founder gets in sixty seconds. The brief is authored so that
the layer, with every sentence of prose removed from between its units, still states the top threat
and the recommended action. The rule is rule 1 of
`output/research/round-run/22-scannability-rulebook.md:748`. <!-- illustrative -->
Whether a draft meets it is judgement, so the cold reader is handed the extraction before the
rendered page and answers it.

Two of the layer’s rules are mechanical, and `bash tools/scan-layer.sh --check` holds them; a
non-zero exit blocks the build. Where it sits in the run order is `docs/history/pipeline.md`’s to say,
and its SCAN LAYER block says it.

- Sibling row labels and list items never open with the same word. The check grades what the run
  authors, never what it records: list items at one indent depth in one list, and a table’s first
  column only where that column’s header is an authored-label header, today exactly one,
  `Capability`, the Competitive Matrix’s row labels. Any other header is ungraded. That first column
  is an entity roster in four of the exemplar’s five tables, `Company` and `Competitor`, and
  `AGENTS.md` Provenance requires company names verbatim from the company’s own site, so a market
  handing a run two rivals that share a first word would red a blocking lint the run has no legal
  way to clear and nobody to ask about. The allowlist fails green rather than open: an unrecognised
  header is skipped, so a new table shape can never halt a run. Value columns sit outside the rule
  for a separate and older reason, measured 2026-09-07: grading all columns reds the exemplar 12
  times across four of its five tables, and in 10 of those the repeated word is a closed-vocabulary
  answer, WATCH four times, rising three, steady twice, Yes five, No in five separate columns and
  Not twice, whose repetition is the information the table carries.
- No unit of the layer opens with a connective or with a pronoun that has no antecedent when the
  layer is read alone: “this”, “they”, “however”, “therefore” and the rest. A unit that only parses
  from the sentence above it is invisible to a reader who scans. The check matches a fixed list of
  openers, so a demonstrative outside that list, “Such”, “Both”, “Each”, is invisible to it.

The checks in `tools/scan-layer.sh` are authoritative and are what the build runs; the two rules
above name and illustrate them rather than enumerating every trigger, so a draft that matches every
example printed here can still red. Its red artefact is `tools/fixtures/scan-blind-brief.md`, which
`bash tools/scan-layer.sh --selftest` grades and which is never rendered and never sent. The green
reference is the exemplar. A clean run prints `SCAN-LAYER-OK`.

## Build and deliver

Build with `python3 build/web.py`, the only sanctioned renderer, then grade the page with
`tools/web-check.py`. The deliverable is the page `web.py` writes to `$BRIEF_ROOT/web/`, staged at
`~/competitor-intel-pages/<slug>/` for `https://ryanhennebry.xyz/<slug>`. Keep every intermediate in
the run directory.
