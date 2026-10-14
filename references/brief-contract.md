# Brief contract

This file owns the page a run ships: the `brief.json` the run writes, the anatomy `build/web.py`
renders it into, the tokens and frozen decisions that page keeps, and its head metadata. It
outranks `references/briefing-template.md`, and the markup of `build/web/template.html` on anatomy
and head metadata; token values defer to that file's `:root` (Part 3). Live variant T,
`https://ryanhennebry.xyz/competitor-intel-agent/`, is the gold standard: where this file and T
disagree, T wins and this file is the defect. The contract this replaced is
`docs/history/brief-contract-pdf.md`, kept as history and carrying no authority.

## Part 1. `brief.json`

Stage 7 writes `$BRIEF_ROOT/brief.json`, and no agent writes HTML. Every field, cap and enum is
`build/web/brief.schema.json`, the single source of truth; this part names the pieces and restates
no cap.

- **Span**: `{"t": text, "c": claim}`. `c` names the `claims.jsonl` row or rows the text rests on,
  and is null only on connective text holding no numeral, name or quote. `"q": true` prints curly
  quotes around a verbatim quote; `"g": true` prints an English gloss after its language lead.
- **Entities**: `company` and `rivals`, each a name verbatim from its own site, a slug, its
  snapshot file and a logo key.
- **Authored sections**: `quick_take`, `map`, `recommendations`, `moves` with `moves_heading`,
  `matrix` with its `heading`, and `open_questions`. A matrix cell is `cited` or `unknown`; an
  unknown cell is a finding, never a blank.

Three tools hold the contract, and each collects every violation, then exits non-zero:
`tools/brief-check.py` grades `brief.json` against the schema and the run's ledger, fetch index
and logos; `build/web.py` renders it and audits the page; `tools/web-check.py` grades the page in
Chrome and WebKit.

## Part 2. Page anatomy

In page order, from the banner to the footer. **Template** parts come from
`build/web/template.html` and never from the run; **authored** parts are `brief.json` fields.

1. **Banner**: template, in T's framing only. A company's page carries none (N1).
2. **Bar**: template. The studio mark, the label "Competitor intel", Contents, Email me.
3. **Title block**: the h1 names the company and the agent; the run line gives the fetch day, the
   page count, the companies and the claim count. `web.py` writes both from the run, with no year.
4. **Contents rail**: generated from the h2s.
5. **Quick take**: fixed heading over `quick_take`, then the map figure drawn from `map`.
6. **Recommendations**: fixed heading over `recommendations`.
7. **Moves**: `moves_heading` over one row per `moves` entry, each tagged Act or Watch.
8. **Matrix**: `matrix.heading` over one column per company, its legend beneath. The legend and
   the cells carry every caveat on the evidence, each beside the claim it limits.
9. **Open questions**: fixed heading over `open_questions`, the brief's last h2.
10. **Also built by Ryan**: template, fixed heading.
11. **Sources**: generated, every cited URL with its label and its number; shown in print only.
12. **Footer**: template.

**Headings** (the operator, 2026-10-09). Quick take, Recommendations, Open questions and Also built by Ryan
are fixed. The moves and matrix headings are authored per brief, decided by the job description:
five words at most, under the same checks.

## Part 3. Tokens

The `:root` blocks of `build/web/template.html` are the source of truth for every token: colour
(`--ground`, `--text`, `--muted`, `--edge`, `--rule`, `--wash`, `--focus`), type (`--sans` and each
role's size and leading), grid and motion. Copy a value from there; never re-pick one. A width tuned
to one brief's text is not a token: `web.py` measures it on each page into the generated style
block, or the table's own min-content sets it. IBM Plex Sans is the only family, subset per page.

## Part 4. T's frozen decisions

From `T:HANDOFF.md` § the operator's rulings, 5 October 2026. Each binds every page; a change is the operator's.

- **Share card**: one per brief, drawn by `web.py` before the fill (Part 5). `og:image` carries
  `?v=`, the first 12 hex of `og.png`'s sha256, so a changed card is a new URL.
- **Icons**: rendered with every pixel opaque, on a white ground.
- **Banner**: "Example brief. Run the agent for your company: install it from GitHub.", above the
  sticky bar, its first ink aligned with the h1.
- **Kept**: the bar label "Competitor intel" and the h1 wording; "Email me" in the bar.
- **Order**: Open questions is the last h2 before Also built by Ryan.
- **Footer**: from 48rem its sides span the wide grid, the rail's left edge to the matrix's right.
- **Links**: no arrow glyph; the underline marks a link, and an outbound link opens a new tab.

## Part 5. Head metadata

Every page is public, unlisted and `noindex`. The template carries the tags; `web.py` fills the
address, title and image from its `FRAMINGS`, one definition each. `web-check.py` reds a page whose
`noindex`, canonical or `og:url` is wrong.

- `<meta name="robots" content="noindex">`.
- `<link rel="canonical">` and `og:url`: `https://ryanhennebry.xyz/<slug>/`, the slug
  `brief.json`'s `company.slug`, with the trailing slash the site serves at (D10).
- `<title>` and `og:title`: "Competitor intel brief: <Company>" (N1).
- `og:image`: the page's own `og.png`, with its `?v=`: the hiring company's logo, or its name
  when it has no logo.
