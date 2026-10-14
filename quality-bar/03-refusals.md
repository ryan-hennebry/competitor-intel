# Refusals

Content rules. Every one is blocking: a brief carrying any of them does not ship, whatever else
scores well.

| ID | Refusal | Why | Caught at |
|---|---|---|---|
| RF1 | Never tell the reader its own facts. A hiring-company fact appears only as one half of a comparison with a rival's (`cmp`, D13). | H2. It lost two ledes and $119. | brief-check KR-H, founder card |
| RF2 | Never sneer at anyone: the reader, a rival or a source. Where the client holds, say so plainly, sourced. | An insult ends the read. | voice, red-team |
| RF3 | Never pitch the candidate in authored prose. T's masthead, banner and Also built by Ryan are the template's (D5). | Pure analysis, never a pitch. | voice |
| RF4 | Never print a claim without a ledger ID, and never print a persona's knowledge as fact. | An unsourced "OEM 18-36 months" was imported from a red-team persona. | truth |
| RF5 | Never state an absence without its bound, and never write "not registered" for an unfetchable register. | Blocked is not absent. | truth |
| RF6 | Never let a recommendation stand that its own Open Question inverts. Make it conditional or sequenced. | red-team r1 B2. | truth |
| RF7 | Never name a tool, phase, file, fetch or check in authored prose. T's run line is the template's (D5). | P4. | voice-lint, voice |
| RF8 | Never print verification tags on the page. Keep the caveat in words. | Prose caveats persuade; tags audit. A delivered brief still printed one in a recommendation. | voice-lint |
| RF9 | Never use relative dates. Use absolute dates. | They decay the moment the brief is read. | voice-lint |
| RF10 | Never drop a cohort member silently. It goes in a row, or in a coverage row of the ledger with the reason. | A rival dropped between selection and the matrix. | truth |
| RF11 | Never declare a gap more than once. | PG failure mode 9. | voice |
| RF12 | Never use a label that does not cover all its children. | correctness audit C7-01. | labels |

## The tags, and where they do belong

`[VERIFIED]`, `[COMPANY CLAIM]`, `[Unknown]`, `[INFERRED]` and `[company-stated]` are ledger
fields. They live in `claims.jsonl` and in the snapshots, and RF8 keeps them off the page. The
caveat itself is never dropped: it is written in words the reader reads aloud, which is what
"self-reported and undated" does and what "[COMPANY CLAIM]" does not.
