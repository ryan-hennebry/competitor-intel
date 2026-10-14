# Reader model (template)

Stage 1 fills this from the job description (the board's posting API), every sibling posting, and
the reader's own public writing, then writes it to `<run>/00-reader.md`. Body ≤300 words plus the
KNOWN table. Every downstream agent reads the instance.

Everything in angle brackets is a slot. A slot with no evidence behind it stays empty and gets a
coverage row; it is never guessed.

---

```markdown
# Reader: <name>, <title> at <COMPANY>

## Purpose
A work sample attached to <candidate>'s application for <ROLE>. In the seconds page 1 gets, it has
to show this reader that the writer understands the problem their company has; the rest has to
answer whether this person would help, on evidence of judgement rather than effort. The criteria
under "How this reader judges work" are what it is graded against. It is analysis, never a pitch.

## What the role will own (JD verbatim → the company uncertainty it implies)
- "<topic 1>" → <uncertainty>
- "<topic 2>" → <uncertainty>
- "<topic 3>" → <uncertainty>
Parallel hiring signal: <what the other N postings say the company is worried about>.

## How this reader judges work (quoted from their own writing; URL each)
- "<quote>" → test: <what the brief must do>
(If no public writing: use quality-bar/01-hiring-rubric.md unmodified and say so.)

## Already KNOWN to this reader (never news; on the page only as a comparison half)
| Fact class | Examples for this company | Source | Claim IDs |
|---|---|---|---|
| Own registrations, licences, filings | | | |
| Own funding, headcount, hiring | | | |
| Own customers, partners, case studies | | | |
| Own site copy, positioning lines, T&Cs | | | |
| Obvious rivals and what they claim | <the 3-5 names they track weekly> | | |

## Likely NEW to this reader (hypotheses to test, not claims)
- Rival moves in markets the role will enter, in the local language
- Rival contracts or terms that change the reader's addressable market
- Registers and filings about rivals the reader does not read
- Buyer-side facts, from the buyer's own pages and contracts

## Vocabulary
Uses: <their words, from their site and JD>. Avoid: schema keys, coined phrases, framework names,
regulatory role codes they would not use in a sentence.

## Fail modes for this reader (filed with the rest if…)
<from the rubric and the reader's own writing>
```

---

The KNOWN table is the one part with no word cap. It is what H2 and RF1 are graded against, so a
thin table is what lets an own-company fact reach the lede. Fill every row that has a source.

It carries KNOWN's client-owned half. A rival that names this company as a customer, partner or
integration on its own site is known to this reader too, and the stage-5 screener fetches for that
rather than this table; `references/stages/05-thesis-lock.md` § "The screener" owns the rule.

Every filled cell is also a row stage 1 seeds into `$BRIEF_ROOT/claims.jsonl`, under a
company-stated qualifier, and the Claim IDs column is where those ids land — the table is what the
screener reads, and the id is what the author cites. `references/stages/01-reader-frame.md` §
"Both places" owns the rule.

## Illustrative, not portable — one reader's wording for Purpose

<!-- illustrative-block: D-011 the wording below is one reader's own, recorded as calibration and never the default -->

One hiring manager's own words for the Purpose paragraph, recorded here 2026-09-18 as calibration
of how fast and how hard a page is graded:

> make the reader think "this person already knows what our problem is" within two seconds of page
> 1, and answer "will this person help us succeed?" with evidence of judgement

`quality-bar/01-hiring-rubric.md` § "Illustrative, not portable" holds its source and its
`[Unknown]` URL. It is an instance of the paragraph above, never the default: carry a phrase of it
into `00-reader.md` only where this reader states it themselves, with the word illustrative beside
it. Otherwise write Purpose in this reader's own terms, from the criteria section.
