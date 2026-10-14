# quality-bar

Everything that makes a brief good, in one versioned folder. The author writes **from** it; every
critic checks **against** it. Design source: `docs/retro/2026-09-18-northwind/21-quality-bar-system.md`.

## Files

| File | Holds |
|---|---|
| `00-reader-model.md` | template; stage 1 writes the run instance to `<run>/00-reader.md` |
| `01-hiring-rubric.md` | H1-H8, what a hiring manager tests; one reader's essay kept as illustrative |
| `02-voice-card.md` | P1-P8, each with a runnable test and a real Bad→Good pair |
| `03-refusals.md` | RF1-RF12, every one blocking |
| `04-banned-patterns.tsv` | the regex rows `tools/voice-lint.sh` runs |
| `05-exemplars.md` | gold sentences and before→after pairs; the author reads this last |
| `06-critique-rubric.md` | the four critics, the finding row, the blocking list, the pass rule |
| `near-misses.tsv` | run · sentence · rule_id · caught_by · stage · outcome |
| `fixtures/` | the counter-examples every rule here is proved red on |
| `rulings.tsv` | each active ruling, the test it adds and the fixture that proves it red |

The history of this folder, `decisions.md` (append-only, dated; a later entry supersedes) and
`retired.md`, moved to `docs/history/` in S9 of the Globex redesign (D9): no run reads it.

## Load protocol

Stage 0 (`references/stages/00-bar-loader.md`) runs first and alone, reads this folder in full, and
writes `<run>/00-bar.md`, at most 15 lines. Then:

- **every stage agent** reads `00-bar.md` as its first step;
- **the orchestrator** reads those 15 lines and nothing else in this folder;
- **the author** reads `02`, `03`, `05` — loaded last — and `<run>/00-reader.md` in full, plus the
  bar, because it writes to the card and the 15 lines are an index rather than the standard. Its
  three inputs from outside this folder are the allocation, the `claims.jsonl` rows for the
  allocated IDs, and known-traps; `references/runbook.md` stage 7 owns that list in full;
- **each critic** reads the bar, `06`, and the one or two files for its own dimension;
- **the thesis-lock screen** reads the bar, the `00-reader.md` KNOWN table, and H1-H4.

## Illustrative text, and the marker that labels it

The run must come out right for **any** company, so a company, a person, a market sector or a path
into one past run's artefacts may not appear in text a run applies as a rule. It may appear as
**calibration** — what one reader, one brief or one cohort actually said, kept because a generic
criterion carries the test but not how hard the page is graded. The difference is a label, and the
label is mechanical: `bash tools/coupling-check.sh` scans every file in this folder and in
`references/` and fails on an unlabelled instance, naming the file, the line and the term.

Three ways to label, all built on the one word `illustrative`, so `git grep -n illustrative` lists
every one. All three are comments: a heading, a bold lead-in or a word in a sentence labels nothing,
whatever it says, so no edit to a title can exempt a file. A comment quoted inside a fenced block
labels nothing either, so this file can show the grammar without exempting itself.

| Scope | Write | Covers |
|---|---|---|
| File | `<!-- illustrative-file: D-0NN <reason> -->` on a line of its own, or `# illustrative-file: D-0NN <reason>` in a `.tsv` and only there | the whole file; for a file that is an instance end to end |
| Block | `<!-- illustrative-block: D-0NN <reason> -->` on a line of its own | that line down to the next heading of **any** level, a `<!-- /illustrative -->` closer, or 40 lines, whichever comes first |
| Line | `<!-- illustrative -->` | on a line of its own, the paragraph below it, **up to the next blank line**, the next heading or 40 lines; at the end of a line with content, that line only |

Five rules the gate enforces, and one thing it cannot see.

- **A file or block label cites a booked ruling that covers this file.** `D-0NN` names a
  `docs/history/decisions.md` entry, and an id that is absent, unbooked, or carries no reason after it is itself
  a finding that exempts nothing. The ruling also books a **scope** — a `| D-0NN |` row of
  backticked path globs in that file, `*` spanning one path segment and `**` any number — and
  a label citing a ruling whose scope does not reach its own file is a finding too. So
  `git grep -n '^| D-0'` lists every file any ruling can exempt. The line label is spared the
  citation: it reaches one line or one paragraph, and width is what buys the ruling.
- **A label never covers a rule.** A line carrying `must`, `require`, `do not`, `it needs`, or
  opening on an imperative verb is graded whatever labels it, file scope included, and the finding
  names the term. Move the instance into a record, or write the rule in the folder's own words.
- **A block stops at the next heading**, at any level, so the first label in a file reaches the end
  of one passage and never the end of the file.
- **A block or a paragraph over 40 lines is refused** and exempts nothing. A record that long wants
  the file scope and the ruling that comes with it.
- **A marker inside a fenced block is an example**, not a label. Show the grammar freely.
- What the gate cannot see is a missing blank line: a paragraph label runs until one, so put a blank
  line after the labelled text or the label reaches further than you meant — and over 40 lines the
  label is refused rather than granted.

**What this gate does not defend against, ruled 2026-09-19 and booked as D-019.** It defends against
the next agent taking the cheapest path to a green run — the one-character reason, the pasted
ruling id, the renamed title, the label dropped on a rule, the example that exempts its own file.
It is not armour against an author who sets out to defeat it, and two routes are out of scope by
decision: a **homoglyph or zero-width character** inside a name the vocabulary knows (a Cyrillic
capital where a Latin one belongs is forgery, and closing it costs a confusables table the gate
would have to keep current), and a **symlink or an unscanned extension** (the scan is real `.md`
and `.tsv` files; renaming a governing file to `.txt` is not an accident, and which files a run
loads is governed by `AGENTS.md` and `references/runbook.md`). So the claim is: no instance survives
unlabelled in the scanned files, and no label is produced by an edit a hurried author would make.

## Change rules

A rule lands only if it caught, or would have caught, a real defect in a real run. A regex rule
lands only when it is measured **green on `build/briefing.md` and red on a fixture**; a row that
reds the exemplar does not land, and the drop is recorded rather than the pattern widened. Every
add, change and retire gets a dated `docs/history/decisions.md` entry in the form "Supersedes D-nnn because …".
A rule with 0 hits in 5 consecutive runs moves to `docs/history/retired.md`, keeping its fixture test in CI.

A brief run never edits this folder. The compound stage proposes diffs into the run store; an
improvement session or the operator applies them.

## Caps

Pillars ≤8 · refusals ≤12 · regex rows ≤25 · exemplars ≤8 plus ≤6 pairs. Adding at a cap means
retiring or merging in the same decision entry. Calibration history lives in
`docs/history/register-calibration.md`, which no run loads.

**The word cap is on the author's load, not the folder.** `02` plus `03` plus `05`, the three files
the author reads in full, stay under 2,500 words; measured with `wc -w` on 2026-10-08 at 2,499 after
D-026 funded P8, a headroom of 1. The whole folder's top-level markdown measures 13,352 and the
design's 2,500-word whole-folder figure was never reachable: its own drafts in
`21-quality-bar-system.md` §§2-7 run past it before a word is added. `decisions.md` here books the
correction as D-006, and the reason the author's load is the budget that matters is that it is the
only one spent on every run: stage 0 reads the folder once, in its own context, and emits 15 lines.

No check holds this. It is counted by hand until `tools/lint-all.sh` lands.
