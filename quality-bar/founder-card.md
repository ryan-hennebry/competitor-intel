# Founder-reader card

The reader is the founder hiring for the role. The speaker is a candidate for that role, writing the
first memo of a teammate he wants to become. Every test is a yes/no question about one typed field.
A **red** is a "no", and it must quote the clause or field value that earned it, verbatim: code
rewrites exactly the quoted clause and nothing else, so an unquoted red cannot be repaired.

Two kinds of item meet this card. A thesis candidate (`kind: thesis`, at the lock) runs every
test but CONSEQUENCE. A page line (`kind: line`, the line-screen over every authored line of
`brief.json`) runs the six marked **L**. Any test an item does not run is `null`.

| ID | Reads | Question (yes = green) | Blocking |
|---|---|---|---|
| NEW **L** | `thesis` / `text`; `evidence[].known`, `evidence[].use` | Is the main clause news to this founder: something not on his own site, posting, filings or `known_summary`? | yes |
| TRUE **L** | `thesis` / `text`; pasted `rows`; `inference[].from` | Does every factual clause match a pasted row, does every inference follow from its `from` rows, and does no pasted row contradict either? A clause with no row is UNSUPPORTED unless dropping it leaves the main clause. | yes |
| DECISION | `decision.cite`, `decision.text`; the cited question's `changes` | Does the evidence meet the condition of the cited `changes` rule? Score `strength`: 3 met outright, 2 met with a narrowing, 1 half-met or "few", 0 none or a decision the candidate supplied. Red at 0. | yes |
| ROLE **L** | `advice`, `implication`; reader `duties[]` | (a) For each duty line: is acting on `advice` this duty's own work in the hire's first 90 days? (b) **Seat**: does the text leave that work worth hiring for? Red when (a) confirms no weight-3 line, or (b) is no. On a line, only (b) runs. | yes |
| STANCE **L** | `thesis`/`headline` or `text`; `stance`; reader `positioning[]` | Against the founder's own positioning, does the text **build on** it, stay **neutral**, or read rival evidence as a **threat** the advice answers? `negates` is red: it says or implies the positioning is false, not an edge, level with rivals, or no different, or its advice sets buyers a **yardstick** his positioning does not claim (reading rules). Record the value and the `positioning` id. | yes |
| SPEAKER **L** | `headline`, `thesis`, `advice.text` or `text` | Is every clause one this candidate would send to the founder he most respects? Red on any of: a **verdict** grading the founder's product, positioning, standing or role as a whole; a **recital** of the founder's own facts, posting or site back to him as reasoning; a **directive** on running his company outside the role's duties, or one that puts a condition, test or delay in front of a duty he has already set. Record the kind. | yes |
| FEASIBILITY | `advice.depends_on[]`, `advice.fallback`; `case_against[].advice_depends`; reader `constraints[]` | Can the founder act on `advice` with what he controls? Check every `READER.constraints[]` entry the advice touches, and every `[Unknown]` it rests on: where the advice needs one granted, does `advice.fallback` name a path that works without it? | yes |
| HOLDS | `holds.text`, `holds.from[]` | Does `holds` name one place the company stands ahead or level, sourced to its rows, said plainly without praise? This is the page's slot for it. | no: ranks, never kills |
| CONSEQUENCE **L** | `text`; `PAGE`, every authored line of the page | When the line states a rival fact, does some line of `PAGE` act on it: a recommendation, a move's meaning or the quick take drawing advice from it, answering it, or weighing it? The line itself counts when it does. Red when the fact sits on the page and nothing acts on it. `null` when the line states no rival fact, or no `PAGE` is given. | yes, on a line |

## Reading rules

- **Verdict vs gap.** A clause naming one specific, observable, fixable gap that the advice closes
  (for a freight firm: "two rivals print on-time rates per lane; Acme's case pages give none yet")
  is a gap, and stays green. A clause grading the whole (Acme's "routing engine is commodity", "this
  puts Acme behind", "speed no longer distinguishes Acme") is a verdict, and is red whatever its
  grammatical subject.
- **Recital vs comparison.** The founder's own fact may stand as the cited comparison to a rival's
  news. It is red when it is the reason offered to him ("as your homepage's Tesco logo shows", "the
  two tasks your job ad assigns").
- **Advice sets the buyers' yardstick.** Name the measure a line asks buyers to compare the
  company on: unit price, speed, results, reach. Read it against his positioning lines. When one
  of them claims that measure, the advice builds on it. When they claim a different measure, or
  set him apart from the rivals who sell on this one, the advice moves his positioning onto their
  ground, and STANCE is `negates` however useful the page would be. For a freight firm sold on
  reliability, "publish a price-per-pallet page beside the two discounters' rates" negates; "print
  on-time rates per lane" builds on.
- **Advice that moves the positioning is graded strict.** Advice to drop, demote or rewrite the
  founder's own line ("'next-day everywhere' cannot lead Acme's copy") scores a point against him,
  so STANCE is `negates` even when the advice is sound. A threat names the rival move and lets the
  advice answer it; the founder decides what his line says.
- **Directive vs the hire's work.** A duty line records a decision the founder has made: this work
  gets done. Advice is the hire's work when it does that work as the line words it. Telling the
  founder how to run the rest of his company is a directive, and so is advice that puts a
  condition, test or delay in front of a duty he set ("time the dispatchers on one depot before
  automating dispatch", when automating dispatch is the duty): it re-opens his decision, so
  SPEAKER is red, kind `directive`, even though a duty line names the same work.
- **The decision belongs to someone.** A decision the founder makes alone counts toward DECISION;
  only the hire's duty lines count toward ROLE.
- **The clause rule settles the narrowed-or-unsupported boundary.** Test each clause alone. A
  clause no row backs is red on TRUE; it stays green only when deleting it leaves the main clause
  standing, and then the red quotes it as the clause to delete.

## What code does with the verdicts

No model ranks, kills or forgives; `tools/rank.py` and `tools/line-screen.py` do, from the
verdicts and the typed fields.

- **Three screeners, majority per test.** Three fresh screeners grade each item. A test is red
  when 2 of 3 say no; a `null` is not graded.
- **Code tests the model is blind to.** NEW(code): red when no row has `use: main`, or every main
  row is known to the founder (`known` is set by code from the row's host against
  `reader.json` `known_hosts`). LEAD(code): red when the lead row, `evidence[0]`, is not a main row
  or is known; on a line, when its first cited span cites only known rows.
- **Repair before kill.** A candidate red only on card tests whose quotes sit in its prose gets one
  rewrite of exactly those clauses, then a fresh three-screener re-screen. A second red kills it.
  Code refuses a rewrite that touches an unquoted clause or a typed field.
- **Rank.** Eligible means every blocking test green, model and code. Eligible candidates sort by
  role weight (the summed duty weights a majority confirmed under ROLE), then DECISION strength,
  then fewer unresolved `advice.depends_on`, then HOLDS green. Rank 1 locks.
- **The check-in does not stop the run.** Ranks 2-3, the case against rank 1, the duty map and the
  decisions go into `checkin.md`, which the operator may veto. A rank 1 with role weight under 6 is flagged
  there, never stopped.
- **No eligible candidate is the one stop.** The lock regenerates once at xhigh with the verdicts;
  a second empty rank notifies the operator and waits.
