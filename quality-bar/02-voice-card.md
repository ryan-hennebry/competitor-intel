# Voice card

Register: **Paul Graham writing to a founder, inside Emily Kramer's MKT1 frame.**

Eight pillars. Each carries a definition, a **test** a critic answers yes or no, a Bad→Good pair
from a real run, and a source. No test, no pillar.

## P1. IS useful, NOT merely correct

- **Definition:** Say something true, important and *new to this reader*. True and unsurprising
  is not a finding, it is furniture. True, new and inert is
  decoration: a finding changes what the reader says, what it runs, or what a rep answers,
  whatever the research cost.
- **Test:** Could the reader have written this sentence this morning? If yes, cut it. Which of the
  three does each finding change? None, and it goes.

<!-- illustrative -->
- **Bad:** A claim-header that restates the reader's own business model in the words of the
  reader's own site: who the company sells to, or what it sells them.
- **Good:** "Voltalis' own household contract writes your objection handling." Also good: "Nobody
  in this category has published a control model.", a convention the reader can break.
- **Source:** PG, How to Write Usefully; red-team r1 M1; MKT1 competitive research.

## P2. IS advice to a company, NOT a description of a specimen

- **Definition:** Critical, never mean. The reader's company is advised, not catalogued: say
  plainly where it holds and where it does not, each sourced to its rows. In the client's own row,
  answer the column's question.
- **Test:** Does each section end in something this reader should decide or do, with its cost? Is
  any sentence a jibe at the reader or a rival? Delete each clause beside a disliked finding: does a
  claim change? If not, it is padding. Padding and meanness are both findings, neither excusing the
  other.
- **Bad:** A cell in the client's own row that pays the reader a compliment where the column asked
  a question. Also bad: a rival's row written as a jibe.
- **Good:** "Yes, and it pays the driver without a retailer in between."
- **Source:** 21-voice-audit §4; register check 5; PG, How to Disagree and Persuade xor Discover;
  MKT1, where we lose.

## P3. IS spoken, NOT written

- **Definition:** A long evidence sentence, then a short verdict. Rhythm is the sound; the mean
  sentence length is not. Restraint beats cadence: most paragraphs carry no punchline. A section's
  bold claim-headers are heard together, so two of them making the same kind of statement sound
  like one sentence printed twice, however different their facts.
- **Test:** Read it aloud: would you say it across a table? Does a paragraph run as flat,
  same-length sentences? Line up the bold claim-headers of one section: do two of them make the
  same kind of statement, a company or its site as the subject and a verb of what it says, sells or
  publishes? Quote every header that shares the frame, one finding row each. Does any short
  sentence read bolted-on, a punchline added for rhythm rather than a verdict the paragraph earned?
  Strip the wit from each short sentence and header: a fact or verdict still there, or only
  brilliance and displayed rigour? Is there any semicolon in prose?
- **Bad:** Twelve consecutive Recommendations sentences, none under 11 words. Also bad: three Quick
  Take headers in a row, each a company and a verb of what it publishes.
- **Good:** "…is buried inside that claim instead of being it." / "Answering that costs a page." /
  "G2 blocked us." The exemplar's three Quick Take headers run an absence, a strategic verdict and
  a state of the business: three kinds, so the two that both open "The …" are not a shared frame.
- **Source:** PG, Write Like You Talk and Earnestness note 1; 21-voice-audit §1; MKT1, read aloud.

The rhythm counts `tools/voice-lint.sh` prints are evidence for the critic, never quotas for the
author. A quota pushes the author to bolt short lines on, which is itself the tic.

## P4. IS about the world, NOT about the work

- **Definition:** Every sentence's grammatical subject is a company, a market, a page, a number or
  the reader. Never the brief, the run, the research, the thesis, a fetch or a check. Keep the
  bound, drop the verb.
- **Test:** Underline each subject. Is any of them the document or its method?

<!-- illustrative -->
- **Bad:** "No heat pump on its integrations page or on 22 pages fetched."
- **Good:** "No heat pump on its integrations page. Whether ev.energy supports one is unknown."
- **Source:** 20-voice-standard §E.1; 21-voice-audit S1-S6.

## P5. IS a judgement, NOT a record

- **Definition:** Each section says what its facts mean. The lede is a judgement, not a negated
  fact, unless the negation itself is sourced. The brief resolves rather than enumerates: one named
  primary comparator, one primary segment where several are named, one consequence per rival.
- **Test:** Does each section say what its facts mean? Is the lede a "did not X, it did Y"
  absolute? Which sentence names the primary comparator? Is any company described with no
  consequence: where the reader wins, where it loses? Does any section close on both sides, on "it
  depends", or on a restated tension? The exemplar's ratio, roughly one prose sentence in four a
  verdict, is evidence for the critic and not a quota.

<!-- illustrative -->
- **Bad:** "Voltalis did not bring its French free box to Britain. It brought your model." (false:
  it brought both)
- **Good:** "Voltalis' French free box is not the GB threat. Your model is."
- **Source:** 20-voice-standard §E.5; PG, The Age of the Essay; MKT1 positioning.

## P6. IS exact, NOT rounded

- **Definition:** Every number, absence and quantifier ("none", "only", "all", "seven", "first")
  matches its ledger row, qualifier included: "15,000+", "5 of 7", "intend to … eventually",
  "Beta/Mixed". A table cell carries the caveat its prose carries.
- **Test:** For each quantifier and each negative cell, name the claim ID. Does any other cell or
  sentence about the same company contradict it?

<!-- illustrative -->
- **Bad:** "Enode reaches your seven partners without signing them." Also bad: a cell reading
  "Named maker customers: None" where the prose names three.
- **Good:** "Three, none paying direct."
- **Source:** correctness audit C6-10, C6-13, C7-07.

## P7. IS plain, NOT insider

- **Definition:** Use the reader's words. No coined phrases, schema keys, framework names, or role
  codes the reader would not say aloud. A heading covers every row and names what its columns
  jointly argue.
- **Test:** Would the reader need to ask what any term, heading or column means? Does any row fall
  outside its heading?
- **Bad:** "What Each Company Says Its AI Does" over a table with no AI in it. Also bad: "Who Holds
  the Role", settlement jargon covering 3 of 5 rows.
- **Good:** "What They Say, What They Do."
- **Source:** correctness audit C7-01, C7-06; MKT1 `competitive_research`, battle-card voice rules
  (MCP, 2026-09-18): "Plain English only. No jargon ('brand pull', 'wedge', 'the unlock'). No
  marketing-speak. One clear thought per bullet."

## P8. IS complete on the page, NOT in the ledger

- **Definition:** The page stands alone: each claim's support is printed in words. Where an honest
  reader would take a finding as bigger than it is, the next sentence closes that misreading.
- **Test:** Is each claim's support printed? What is each finding's nearest wrong reading, and does
  its paragraph close it? Does each recommendation rest on a figure, a quoted line or a dated page?
  Does any sentence only fend off a hostile reader?

<!-- illustrative -->
- **Bad:** "Not one of the six says where its agent stops." alone reads as six unbounded agents.
- **Good:** Then "All six sell agents that touch money, and all six bound them."
- **Source:** PG, How to Write Usefully, Putting Ideas into Words; MKT1 `competitive_research`.

## Word discipline (mechanical; enforced in `04-banned-patterns.tsv`)

No em dash, no straight quotes, no ellipsis. One document stamp. "Not X but Y" at most once. Bold
is a full-sentence claim-header in prose, or a 2-5 word noun phrase elsewhere. Table cells are 2-5
word fragments.
