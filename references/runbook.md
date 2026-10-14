# Runbook

A map of a run, for orienting. The order is code: `tools/run.py` builds the graph from the YAML
frontmatter of every `references/stages/*.md` (`after:`, `inputs:`, `outputs:`, `gate:`,
`lane:`), and `bin/intel run --dry-run` prints it. Where this map and the frontmatter differ, the
frontmatter is right and this map is stale.

## Lanes

| Lane | Templates | Main artefacts |
|---|---|---|
| bar | `00-bar-loader.md` | `00-bar.md`, cached on `quality-bar/` |
| role | `01-reader-frame.md`, `02-questions.md`, `02-mkt1.md`, `04-client-extract.md` | `reader.json`, `questions.json`, the client's claims |
| market | `03-market-map.md`, `03-discover.md` | `segments.json`, `pool/` |
| join | `03-selection.md`, `04-research.md` | `names.json`, `claims.jsonl`, `sources.tsv`, `logos/` |
| spine | `05-thesis-lock.md` (lock, screen, repair, rank) | `05-thesis.json`, `checkin.md` |
| back | `06-*.md` to `11-*.md` | `brief.json`, `web/`, the live page |
| finally | `12-compound.md` | `compound/`, on every run |

Each typed artefact has a schema in `references/schemas/`.

## What the runner holds

- **Sentinels.** The runner writes `state/done/<node>` after `tools/stage-check.py <node>` exits 0
  and the clone is clean. A sentinel an agent writes is deleted unread.
- **Repair.** A red node is re-dispatched once with the gate's stderr. A second red stops the run,
  or degrades a non-critical node with a coverage row.
- **Truth repair.** A span-verify FAIL gets up to `rounds` arbiter repair rounds (3, in
  `10-span-verify.md`), each on the spans still failing; a FAIL after the last stops the run
  unpublished, naming the spans. The report's `ROUNDS` line counts the rounds used.
- **Check-in.** `rank` writes `checkin.md` and notifies; the run continues (D1). The one blocking
  stop is no eligible candidate after one regeneration (D12).
- **Publish.** `tools/publish.py` deploys the page and probes it; `SHARE <url>` follows exit 0 or
  31.
- **Compound** runs in the runner's `finally`, and never edits a governing file.

## Commands

`bin/intel run <jd-url>`, `status`, `cost`, `veto` and `resume`; `bin/intel --help` gives each
one's arguments.
