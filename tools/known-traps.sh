#!/usr/bin/env bash
# R8, closing the `docs/PLAN.md:906` row: `output/review/known-traps.md` gates Phase 5 fail-closed
# and nothing generated it. This is that writer, and it is a HARVESTER AND A SHAPE GATE, never an
# author. R8 (`docs/plans/active/ci-v2-rulings.md:21`) makes the traps block "agent-authored,
# derived entirely from the run's own research corpus", so every row this script writes quotes the
# run's own text and cites the `file:line` an editor can open and falsify. It invents nothing and
# paraphrases nothing.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name and
# R18 fixes the count at seven, so this is a standalone script the pipeline invokes, exactly as the
# thesis sidecar gate, the ICP floor and the divergence ledger are standalone build-blocking lints.
# `docs/history/pipeline.md:562-565` is the caller: a non-zero exit blocks the fact-integrity dispatch.
#
# It collects every precondition failure and only then exits non-zero, the same discipline `audit()`
# uses: reading the printed output is not evidence, a zero exit is.
#
# WHAT IT HARVESTS. Three of the six sources at `docs/history/review/05-fact-integrity.md:58-63` are
# mechanisable and are the only ones this script touches:
#   S1  every `Corrections` / `Corrections to the record` block in this run's research files;
#   S4  every superlative and exclusivity claim in the draft `build/briefing.md`;
#   S5  every blocked source in this run's cohort snapshots, so "blocked" is never written up as
#       "absent" -- the refusal codes are the `blocked` arm of `classify()` in
#       `tools/follower-counts.sh`, i.e. 401, 403, 429 and LinkedIn's 999, plus the literal words.
# Sources 2 (figures that changed mid-run), 3 (values where two of the run's own files disagree)
# and 6 (the client's own numbers) need judgement. They are written into the output as named
# orchestrator slots so the orchestrator knows exactly what it still owes, and this script never
# fills them.
#
# NEVER PADS. If the finished file carries fewer than six `^- ` rows, the shortfall is stated rather
# than invented, per `docs/history/review/05-fact-integrity.md:65-66`. The word `shortfall` is written
# ONLY on that branch, so the assert's `grep -q 'shortfall'` arm stays honest instead of becoming a
# permanent loophole.
#
# THE EXISTING-FILE RULE, and why it is not "write only if absent". `docs/history/pipeline.md:562-565`
# has the orchestrator write its judgement-derived traps FIRST and this script run second, so
# refusing whenever the file exists would halt Phase 5 in exactly the case the pipeline prescribes.
# Instead the script owns only the marked block between BEGIN_MARK and END_MARK and nothing else:
#   file absent            -> create it: title line, then the marked block.
#   file exists, no block  -> append the marked block, every existing line preserved verbatim.
#   file exists, has block -> refuse, exit non-zero, unless `--force`, which replaces the text
#                             between the markers and leaves every line outside them untouched,
#                             except its OWN title line, which is re-stamped for this run.
# So orchestrator-authored rows are never clobbered, on any path, with or without `--force`.
#
# THE TITLE IS RE-STAMPED, and only the title this script itself wrote. The title sits outside the
# markers, so a plain replace left the previous run's `# KNOWN TRAPS -- <other client>, cohort
# captured <other date>, harvested <other date>` standing above the new client's rows -- wrong-run
# evidence in the first line the fact-integrity pass reads, which is precisely what R8 forbids. The
# re-stamp matches TITLE_RE below, the shape only this script emits, so an orchestrator's own title
# (`# KNOWN TRAPS -- Acme (orchestrator)`, the G5 fixture) does not match and is preserved.
#
# `grep` is wrapped to `ugrep` on this machine, where a pattern starting with `--` parses as an
# option, so every pattern below is passed as `grep -e '<pattern>'`. `/bin/bash` here is 3.2, where
# expanding an empty array under `set -u` is itself an error, so the failure accumulator is a
# newline-delimited string.
#
# PRECONDITION: the run's corpus, which is the run's own directory.
#   * `build/briefing.md` must exist and be non-empty. It is the document under audit; without it
#     there is no draft to trap.
#   * `BRIEF_ROOT` IS THE CORPUS. It is the run's own directory, `output/runs/<client>-<date>/`
#     (`AGENTS.md`, Output), and a run sets it. With it set, the research corpus is that directory
#     and the snapshot cohort is `$BRIEF_ROOT/snapshots/*.json` -- everything a run writes lands
#     inside its own root, and `output/snapshots/` is the EXEMPLAR's, which a run never writes to
#     and must never harvest its evidence out of. An S5 blocked row lifted from another company's
#     snapshot is exactly the "never a fact from a previous company" failure R8 forbids, and a
#     corpus path built from the client name found neither directory for any run but the exemplar.
#   * WITH `BRIEF_ROOT` UNSET this falls back to the exemplar's own layout,
#     `output/research/<client>-run` and `output/snapshots/`, which is the replay the committed
#     artefacts and the selftest below are in. The fallback is a replay affordance, not a default a
#     run relies on.
#   * The client is read from the draft's own `Prepared for <Client>.` subtitle on BOTH paths: it is
#     what the harvested block is stamped with, so the previous run's client cannot stand above this
#     run's rows. A draft carrying no such sentence fails closed on both.
#   * `BRIEF_RESEARCH_DIR` (a path relative to the repository root) overrides the corpus directory
#     on either path, with `BRIEF_CLIENT` for the name to stamp. The snapshot cohort follows
#     `BRIEF_ROOT` either way.
#   * The cohort is the set of `*.json` in that snapshot directory sharing the newest `captured`
#     date, which is exactly how `run_cohort()` in `build/build.py` separates this run's evidence
#     from an earlier client's.
#   * `BRIEF_RUN_DATE` (default today) is stamped into the header as the harvest date, so a stale
#     file is visible on sight.
#
# FAIL-CLOSED. A file that exists but describes no run is worse than no file, because "no run
# happened" would launder into "gate passed" -- the vacuous-pass defect this repository has already
# booked once. The script exits non-zero and writes NOTHING when the research corpus is missing or
# empty, when the draft is missing, and when the harvest yields zero rows.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRAPS_FILE="output/review/known-traps.md"
BRIEF="build/briefing.md"
RUN_DATE="${BRIEF_RUN_DATE:-$(date +%F)}"

BEGIN_MARK="<!-- known-traps.sh: harvested block begins -->"
END_MARK="<!-- known-traps.sh: harvested block ends -->"

# TITLE_RE matches a title line this script wrote, and nothing else. Deliberately narrow: the three
# fixed segments together are a shape no orchestrator writes by hand, so the --force re-stamp cannot
# reach a human-authored heading.
TITLE_RE='^# KNOWN TRAPS -- .*, cohort captured .*, harvested '

# Excerpt width in characters. Long enough to carry a claim, short enough that a table row or a
# whole Quick Take paragraph does not swamp the block. The citation, not the excerpt, is what
# settles a row.
EXCERPT_WIDTH=160

# S4's word list. Fixed, explicit and deliberately over-inclusive: a false row is a claim an editor
# checks and discards in seconds, a missed superlative is a false statement in the deliverable.
# Matched case-insensitively with non-alphanumeric boundaries on both sides.
SUPERLATIVES='only|alone|sole|solely|unique|uniquely|unmatched|unrivalled|unrivaled|exclusive|exclusively|first|best|most|largest|biggest|fastest|cheapest|leading|no other|no competitor|nobody|no one|not one|none|never'

# S5's refusal set: the `blocked` arm of classify() in tools/follower-counts.sh (401, 403, 429, 999)
# plus the words a snapshot uses for the same thing. Digit boundaries stop 403 matching inside a
# longer number such as an FRN.
BLOCKED_RE='(^|[^0-9])(401|403|429|999)([^0-9]|$)|blocked|authwall'

FAILS=""

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# --- empty is not failure -------------------------------------------------------------------------
# `set -euo pipefail` above turns three ordinary shell idioms into silent aborts, and each one has
# already fired here. A silent non-zero exit is the worst failure mode a fail-closed gate has,
# because it is indistinguishable from a real refusal and prints nothing to act on. The three:
#   * `grep | while read` -- grep exits 1 when it matches nothing, `pipefail` promotes that to the
#     pipeline's status and `set -e` kills the script mid-loop. A snapshot with no blocked source is
#     a normal snapshot. Guarded below with `|| [ $? -eq 1 ]`, which suppresses ONLY "no match" and
#     still lets grep's exit 2 (unreadable file, bad pattern) fail loudly. `|| true` would have hidden
#     that too, which is why it is not used on any grep whose subject is a corpus file.
#   * `cmd | head -1` -- `head` closing the pipe early can leave the writer with SIGPIPE, which
#     `pipefail` reports. Every such pipe is gone: the command is captured whole and the first line
#     taken with `${var%%$'\n'*}`, so the writer's own status is what governs.
#   * `n=$(grep -c ...)` -- `grep -c` prints `0` and exits 1 on no match, so the assignment aborts.
#     count_rows() below always prints an integer, which also keeps the `$(( ))` arithmetic that
#     consumes it total.

# count_rows prints how many lines of file $2 match BRE $1, as a decimal integer, always. A file
# that cannot be read counts 0 rather than aborting: every caller here feeds the result into the
# zero-rows fail-closed branch or into an explicit comparison, so an unreadable file surfaces as a
# stated failure instead of a silent one.
count_rows() {
  local n
  n="$(grep -c -e "$1" "$2" 2>/dev/null || true)"
  case "$n" in ''|*[!0-9]*) n=0 ;; esac
  printf '%s' "$n"
}

# --- temp files -----------------------------------------------------------------------------------
# Every temp path is registered as it is created and removed on every exit path, so a run and a
# selftest both leave nothing behind. Before this, three `mktemp` calls preceded a single RETURN
# trap: the harvest abort above skipped that trap entirely and had leaked fifteen files into TMPDIR
# by the time it was diagnosed. One directory per call closes the window between creating the first
# path and arming the trap.
TEMP_PATHS=""
NEW_TEMP_DIR=""

# make_temp_dir creates a fresh temp directory named for $1 (default known-traps), registers it for
# cleanup, and leaves the path in NEW_TEMP_DIR.
#
# It ASSIGNS rather than prints, and that is the whole point: a printing version has to be called as
# `$(make_temp_dir)`, which runs in a subshell, so the registration it performs is discarded when
# that subshell exits. Measured -- the printing version left the selftest's own sandbox behind on
# every run while appearing to work.
make_temp_dir() {
  NEW_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/${1:-known-traps}.XXXXXX")"
  TEMP_PATHS="${TEMP_PATHS}${NEW_TEMP_DIR}"$'\n'
  return 0
}

# GEN_TMPDIR holds generate()'s working directory for the duration of one call, and is global on
# purpose. A RETURN trap is installed by a function but stays armed in the caller afterwards, so it
# fires again when the caller returns -- and a trap naming a `local` then reads a variable that has
# gone out of scope, which under `set -u` is a fatal error AFTER the work succeeded. Measured on the
# unfixed script: a healthy corpus printed `TRAPS-OK (6)` and the process still exited 1. Holding
# the path globally and clearing it makes the second firing a no-op.
GEN_TMPDIR=""

# release_gen_tmpdir removes generate()'s working directory, at most once.
release_gen_tmpdir() {
  if [ -n "${GEN_TMPDIR:-}" ]; then
    rm -rf "$GEN_TMPDIR"
    GEN_TMPDIR=""
  fi
  return 0
}

# cleanup_temps removes every registered path. Idempotent, so calling it explicitly and again from
# the EXIT trap is safe.
cleanup_temps() {
  local p oldifs
  [ -n "$TEMP_PATHS" ] || return 0
  oldifs="$IFS"
  IFS=$'\n'
  for p in $TEMP_PATHS; do
    if [ -n "$p" ]; then rm -rf "$p"; fi
  done
  IFS="$oldifs"
  TEMP_PATHS=""
  return 0
}

# --- the assert -----------------------------------------------------------------------------------
# Copied byte-for-byte from `docs/history/review/05-fact-integrity.md:71-75`, indentation included, so
# a diff between the two is meaningful and this script proves the shipped assert rather than a
# paraphrase of it. That is why `f` and `n` are not `local` and why the body calls `exit`: it is not
# this script's code. Always call it in a subshell, from the run directory:
#   ( cd "$root" && assert_traps )
#
# Note its two documented behaviours. With zero `^- ` rows, `n=$(grep -c '^- ' "$f")` fails under
# `set -e` and the subshell exits non-zero with no message; the script never writes such a file, so
# that branch is reachable only for a file somebody else wrote. With a row count under six, the
# `grep -q 'shortfall'` arm decides, which is why this script writes that word only when it is true.
assert_traps() {
f=output/review/known-traps.md
test -s "$f" || { echo "FAIL: no traps block at $f"; exit 1; }
n=$(grep -c '^- ' "$f")
[ "$n" -ge 6 ] || grep -q 'shortfall' "$f" || { echo "FAIL: $n traps and no stated shortfall"; exit 1; }
echo "TRAPS-OK ($n)"
}

# --- corpus location ------------------------------------------------------------------------------

# client_name prints the client the draft was prepared for, read from the draft's own subtitle.
client_name() {
  local out
  out="$(sed -n -e 's/.*Prepared for \([^.<]*\)\..*/\1/p' "$1")"
  printf '%s' "${out%%$'\n'*}"
}

# client_slug lowercases a client name into the directory form the convention uses.
client_slug() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-'
}

# snapshot_dir prints the directory this run's snapshots live in: `$BRIEF_ROOT/snapshots` when the
# run set `BRIEF_ROOT`, which is where `AGENTS.md` (Output) puts every snapshot a run retains, and
# the exemplar's `output/snapshots` only on the replay path where no root is set. One function, so
# the two globs below cannot drift apart and the fallback is written down once.
snapshot_dir() {
  if [ -n "${BRIEF_ROOT:-}" ]; then
    printf '%s' "${BRIEF_ROOT%/}/snapshots"
  else
    printf '%s' "output/snapshots"
  fi
}

# cohort_date prints the newest `captured` date across the snapshots, or nothing when there are
# none. Same discriminator as run_cohort() in build/build.py.
cohort_date() {
  local f d newest="" dir
  dir="$(snapshot_dir)"
  for f in "$dir"/*.json; do
    [ -f "$f" ] || continue
    d="$(sed -n -e 's/.*"captured"[[:space:]]*:[[:space:]]*"\([0-9-]*\)".*/\1/p' "$f")"
    d="${d%%$'\n'*}"
    [ -n "$d" ] || continue
    if [ -z "$newest" ] || [ "$d" \> "$newest" ]; then
      newest="$d"
    fi
  done
  printf '%s' "$newest"
}

# cohort_files prints the snapshot paths carrying $1 as their captured date, one per line. An empty
# want prints nothing: without the guard, a snapshot with no captured date at all would match `""`
# and be read as this run's evidence, which is the failure `run_cohort()` exists to prevent.
cohort_files() {
  local want="$1" f d dir
  [ -n "$want" ] || return 0
  dir="$(snapshot_dir)"
  for f in "$dir"/*.json; do
    [ -f "$f" ] || continue
    d="$(sed -n -e 's/.*"captured"[[:space:]]*:[[:space:]]*"\([0-9-]*\)".*/\1/p' "$f")"
    d="${d%%$'\n'*}"
    [ "$d" = "$want" ] && printf '%s\n' "$f"
  done
  return 0
}

# --- harvest --------------------------------------------------------------------------------------

# excerpt collapses whitespace in a source line and cuts it to EXCERPT_WIDTH. When it cuts, it
# trims back to the last space, which also discards any partial multi-byte character a byte-wise
# locale could have left behind, and marks the cut with `[...]`.
excerpt() {
  local s cut
  s="$(printf '%s' "$1" | tr '\t' ' ' | sed -e 's/  */ /g' -e 's/^ *//' -e 's/ *$//')"
  if [ "${#s}" -gt "$EXCERPT_WIDTH" ]; then
    cut="${s:0:$EXCERPT_WIDTH}"
    case "$cut" in *" "*) cut="${cut% *}" ;; esac
    s="$cut [...]"
  fi
  printf '%s' "$s"
}

# row prints one trap. The quoted excerpt goes LAST, so a table row full of `|` characters cannot
# break the fields in front of it. Every row begins `- ` at column 0, which is what the assert
# counts.
row() {
  printf -- '- [%s] at %s | correct value: %s | claim: "%s"\n' "$1" "$2" "$3" "$(excerpt "$4")"
}

# harvest_corrections: source 1. Every item inside a `Corrections` heading in the run's research
# files. The heading form varies across the corpus (`## Corrections to pool table`, `## Part F:
# Corrections to the record`), so the match is on the word, and the block ends at the next heading.
harvest_corrections() {
  local rdir="$1" f line file lineno text
  for f in "$rdir"/*.md; do
    [ -f "$f" ] || continue
    awk -v f="$f" '
      /^#+[ \t]+.*[Cc]orrections/ { blk = 1; next }
      /^#+[ \t]/ { blk = 0 }
      blk && /^([0-9]+\.|[-*])[ \t]/ { printf "%s:%d\t%s\n", f, NR, $0 }
    ' "$f"
  done | while IFS=$'\t' read -r cite text; do
    row "S1 corrections" "$cite" \
      "the corrected form stated in this item, which supersedes any earlier figure in the corpus" \
      "$text"
  done
}

# harvest_superlatives: source 4. Every line of the draft carrying a word from SUPERLATIVES. The row
# names the term that matched, because that is what an editor checks first.
harvest_superlatives() {
  local brief="$1" line lineno text term
  { grep -niE -e "(^|[^[:alnum:]])(${SUPERLATIVES})([^[:alnum:]]|$)" "$brief" || [ $? -eq 1 ]; } | \
  while IFS= read -r line; do
    lineno="${line%%:*}"
    text="${line#*:}"
    term="$(printf '%s' "$text" \
      | grep -oiE -e "(^|[^[:alnum:]])(${SUPERLATIVES})([^[:alnum:]]|$)" || true)"
    term="${term%%$'\n'*}"
    term="$(printf '%s' "$term" | tr -d '[:space:][:punct:]')"
    row "S4 superlative, term \"${term}\"" "$brief:$lineno" \
      "not settled here: the claim is false if any cohort snapshot shows the same property, so check it against every snapshot named above" \
      "$text"
  done
}

# harvest_blocked: source 5. Every line in a cohort snapshot recording a refusal, so a blocked
# source is never written up as an absence. `references/provenance.md` rule 4 is the authority; only
# a 404 on a canonical path is absent.
harvest_blocked() {
  local snaps="$1" f line lineno text
  # `|| [ -n "$f" ]` keeps the LAST snapshot: `printf '%s'` writes no trailing newline, so `read`
  # returns 1 on that line and the unguarded loop skipped it. It cost nothing on today's corpus only
  # because the last cohort snapshot happens to record no refusal.
  printf '%s' "$snaps" | while IFS= read -r f || [ -n "$f" ]; do
    [ -n "$f" ] || continue
    { grep -niE -e "$BLOCKED_RE" "$f" || [ $? -eq 1 ]; } | while IFS= read -r line; do
      lineno="${line%%:*}"
      text="${line#*:}"
      row "S5 blocked" "$f:$lineno" \
        "blocked, not absent: a 401/403/429/999 refusal is recorded as blocked with the query shapes tried, and only a 404 on a canonical path is absent" \
        "$text"
    done
  done
}

# --- compose --------------------------------------------------------------------------------------

# compose_block prints the block this script owns: its heading, the notes that make every row
# auditable, the harvested rows, the orchestrator slots, and the shortfall statement when the
# finished file would carry fewer than six rows.
#
# No line of the prose here may begin `- ` at column 0, or the assert would count it as a trap.
compose_block() {
  local client="$1" cohort="$2" today="$3" rows_file="$4" rdir="$5" snaps="$6" total="$7"
  local n1="$8" n4="$9" n5="${10}" nmd="${11}" snaplist

  snaplist="$(printf '%s' "$snaps" | tr '\n' ' ' | sed -e 's/ *$//')"
  [ -n "$snaplist" ] || snaplist="none (no snapshot carries a captured date)"

  printf '## Harvested traps -- %s, cohort captured %s, harvested %s by tools/known-traps.sh\n\n' \
    "$client" "$cohort" "$today"
  printf 'Derived entirely from this run\x27s own corpus, per R8. No row here is authored: each quotes\n'
  printf 'the run\x27s own text and cites the file and line that settles it, so any row can be opened and\n'
  printf 'falsified. Harvested sources 1, 4 and 5 of the six at\n'
  printf 'docs/history/review/05-fact-integrity.md:58-63; sources 2, 3 and 6 need judgement and are\n'
  printf 'listed below as slots the orchestrator still owes.\n\n'
  printf 'Corpus read: %s; %s/*.md (%s files); cohort snapshots %s.\n\n' \
    "$BRIEF" "$rdir" "$nmd" "$snaplist"
  printf 'Row shape: `%s [S<n> source] at file:line | correct value: ... | claim: "excerpt"`.\n' '-'
  printf 'The excerpt is the source line, whitespace-collapsed and cut at %s characters; open the\n' \
    "$EXCERPT_WIDTH"
  printf 'citation before acting on it.\n\n'
  printf 'S4 matches this fixed, deliberately over-inclusive word list: %s.\n' "$(printf '%s' "$SUPERLATIVES" | tr '|' ',' | sed -e 's/,/, /g')"
  printf 'An S4 row is a claim to check, not a fault found: it is false only if a cohort snapshot\n'
  printf 'shows the same property.\n\n'
  printf 'Counts: %s from corrections blocks, %s superlative or exclusivity claims, %s blocked\n' \
    "$n1" "$n4" "$n5"
  printf 'sources.\n\n'

  cat "$rows_file"

  printf '\n### Orchestrator slots still owed (judgement, not mechanisable)\n\n'
  printf '  S2 every figure that changed mid-run: a raise restated, an overlap regraded, a URL\n'
  printf '     corrected.\n'
  printf '  S3 every value where two of this run\x27s own files disagree.\n'
  printf '  S6 the client\x27s own numbers, which are the ones a founder reader checks first.\n\n'
  printf 'Those three are docs/history/review/05-fact-integrity.md:57-58 and :61. This script does not\n'
  printf 'write them, because deciding that two files disagree, or that a figure moved, is judgement\n'
  printf 'and R8 makes the block agent-authored. Write them OUTSIDE this marked block: a re-run with\n'
  printf -- '--force replaces only the text between the two markers, re-stamping this file\x27s own title\n'
  printf 'line for the run that harvested and preserving every other line outside them.\n'

  if [ "$total" -lt 6 ]; then
    printf '\nshortfall: this file carries %s rows and the block wants six to ten. The three slots\n' "$total"
    printf 'above are unfilled and nothing has been padded to reach the count, per\n'
    printf 'docs/history/review/05-fact-integrity.md:65-66, which states the shortfall rather than\n'
    printf 'padding it.\n'
  fi
}

# title_line prints the file's title, naming the client, the cohort and the harvest date, with no
# trailing newline so the --force re-stamp can pass it straight into awk as a `-v`.
title_line() {
  printf '# KNOWN TRAPS -- %s, cohort captured %s, harvested %s' "$1" "$2" "$3"
}

# rows_outside counts `^- ` lines in an existing file, ignoring anything between the markers, so the
# total is what the assert will see once this script splices its own block in.
rows_outside() {
  local f="$1"
  [ -f "$f" ] || { printf '0'; return 0; }
  awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
    $0 == b { skip = 1; next }
    $0 == e { skip = 0; next }
    !skip && /^- / { n++ }
    END { printf "%d", n + 0 }
  ' "$f"
}

# --- generate -------------------------------------------------------------------------------------

# generate <root> <force yes|no> <today> does the whole job for one run directory: preconditions,
# harvest, compose, write, assert. Parameterised by root so the selftest drives the real code
# against a fixture instead of a shim.
generate() {
  local root="$1" force="$2" today="$3"
  local client slug rdir cohort snaps nmd n1 n4 n5 nrows outside total tmp block final existing

  cd "$root"
  FAILS=""

  if [ ! -s "$BRIEF" ]; then
    add_fail "FAIL: no draft at $root/$BRIEF; there is no document to trap."
  fi

  # WHERE THE CORPUS IS, in precedence order: the explicit override, then the run's own root, then
  # the exemplar's replay layout. `client` is read from the draft on both real paths, because it is
  # what the block is stamped with and a previous client's name above this run's rows is the defect
  # the re-stamp exists to stop.
  if [ -n "${BRIEF_RESEARCH_DIR:-}" ]; then
    rdir="$BRIEF_RESEARCH_DIR"
    client="${BRIEF_CLIENT:-$rdir}"
  elif [ ! -s "$BRIEF" ]; then
    rdir=""
    client=""
  elif [ -n "${BRIEF_ROOT:-}" ]; then
    rdir="${BRIEF_ROOT%/}"
    client="$(client_name "$BRIEF")"
    if [ -z "$(client_slug "$client")" ]; then
      add_fail "FAIL: $BRIEF carries no 'Prepared for <Client>.' subtitle, so the harvested block cannot name the run it was harvested for; the sentence is machine-read."
      client=""
    fi
  else
    client="$(client_name "$BRIEF")"
    slug="$(client_slug "$client")"
    if [ -z "$slug" ]; then
      add_fail "FAIL: $BRIEF carries no 'Prepared for <Client>.' subtitle, so the run's research directory cannot be located; set BRIEF_ROOT."
      rdir=""
    else
      rdir="output/research/${slug}-run"
    fi
  fi

  # The corpus must exist AND carry content. An empty research directory is "no run happened", and
  # letting that through is how a vacuous pass is manufactured.
  nmd=0
  if [ -n "$rdir" ]; then
    if [ ! -d "$rdir" ]; then
      # The diagnostic lists the PARENT of the corpus that was looked for, whichever layout named
      # it, so the reader sees what is actually there instead of a directory this run never used.
      add_fail "FAIL: no research corpus at $root/$rdir. Present under $(dirname "$rdir")/: $(ls "$(dirname "$rdir")" 2>/dev/null | tr '\n' ' ')"
    else
      nmd="$(find "$rdir" -maxdepth 1 -name '*.md' -size +0 | wc -l | tr -d ' ')"
      if [ "$nmd" -eq 0 ]; then
        add_fail "FAIL: research corpus $root/$rdir holds no non-empty .md file; this run wrote no research."
      fi
    fi
  fi

  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    return 1
  fi

  cohort="$(cohort_date)"
  snaps="$(cohort_files "$cohort")"

  make_temp_dir
  GEN_TMPDIR="$NEW_TEMP_DIR"
  trap release_gen_tmpdir RETURN
  tmp="$GEN_TMPDIR/rows"
  block="$GEN_TMPDIR/block"
  final="$GEN_TMPDIR/final"

  harvest_corrections "$rdir" >"$tmp"
  n1="$(count_rows '^- ' "$tmp")"
  harvest_superlatives "$BRIEF" >>"$tmp"
  n4="$(count_rows '^- ' "$tmp")"
  n4=$((n4 - n1))
  harvest_blocked "$snaps" >>"$tmp"
  nrows="$(count_rows '^- ' "$tmp")"
  n5=$((nrows - n1 - n4))

  if [ "$nrows" -eq 0 ]; then
    printf 'FAIL: harvested 0 traps from %s, %s and the %s cohort snapshots; writing a file that describes no run would launder "no run happened" into "gate passed".\n' \
      "$rdir" "$BRIEF" "$cohort" >&2
    return 1
  fi

  existing="$TRAPS_FILE"
  outside="$(rows_outside "$existing")"
  total=$((outside + nrows))

  compose_block "$client" "$cohort" "$today" "$tmp" "$rdir" "$snaps" "$total" \
    "$n1" "$n4" "$n5" "$nmd" >"$block"

  mkdir -p "$(dirname "$existing")"
  if [ ! -f "$existing" ]; then
    {
      printf '%s\n\n' "$(title_line "$client" "$cohort" "$today")"
      printf '%s\n' "$BEGIN_MARK"
      cat "$block"
      printf '%s\n' "$END_MARK"
    } >"$final"
  elif ! grep -qF -e "$BEGIN_MARK" "$existing"; then
    {
      cat "$existing"
      printf '\n%s\n' "$BEGIN_MARK"
      cat "$block"
      printf '%s\n' "$END_MARK"
    } >"$final"
  elif [ "$force" != "yes" ]; then
    printf 'FAIL: %s/%s already carries a harvested block. Re-run with --force to replace it; every line outside the two markers is preserved either way, apart from this script\x27s own title line, which --force re-stamps for the run that just harvested.\n' \
      "$root" "$existing" >&2
    return 1
  else
    awk -v b="$BEGIN_MARK" -v e="$END_MARK" -v f="$block" -v tre="$TITLE_RE" \
        -v t="$(title_line "$client" "$cohort" "$today")" '
      $0 == b { print; while ((getline l < f) > 0) print l; close(f); skip = 1; next }
      $0 == e { skip = 0; print; next }
      !skip && $0 ~ tre { print t; next }
      !skip { print }
    ' "$existing" >"$final"
  fi

  cat "$final" >"$existing"

  # The gate the pipeline reads, run against what was just written and nothing else.
  assert_traps
}

main() {
  generate "$ROOT" "$1" "$RUN_DATE"
}

# --- selftest ---------------------------------------------------------------------------------------
# Every case runs the real generate() against a fixture run directory under a mktemp -d, so what is
# proved here is what ships. No network, and no write outside the sandbox: the only path generate()
# writes is "$root/$TRAPS_FILE", and every $root below is inside $TMP.
#
# The dates are fixed, not today's, so no result moves with the calendar.
#
# A check that has never gone red is an untested assertion, so every fail-closed branch has its own
# red case here.

TMP=""

# THE ONE SECTION HEADING THE FIXTURE DRAFTS WRITE, named once and labelled. A fixture brief carries
# headings, and this is where this file writes one; `git grep -n heading-literal` finds it.
FX_SECTION="Quick Take"  # heading-literal: the fixture draft needs a section for its superlative

# make_root builds a complete, valid fixture run directory. Each flag switches off one ingredient so
# a case can drive one branch:
#   $2 brief=yes|no|bare   bare = a draft with no superlative and no subtitle-derived corpus problem
#   $3 research=full|empty|missing
#   $4 snaps=yes|no|mixed  mixed = yes, plus a cohort snapshot recording no refusal at all
make_root() {
  local root="$1" brief="$2" research="$3" snaps="$4"
  mkdir -p "$root/build" "$root/output/snapshots" "$root/output/review"

  if [ "$brief" != "no" ]; then
    {
      printf '<p class="subtitle">Prepared for Acme. Covering Beta, Gamma.</p>\n'
      printf '\n## %s\n\n' "$FX_SECTION"
      if [ "$brief" = "yes" ]; then
        printf '**Acme is the only platform in this set that moves money on rules.**\n'
        printf 'No competitor ships a control page, and Beta is alone in claiming one.\n'
      else
        printf 'Acme ships a control page and Beta ships a control page.\n'
      fi
      printf '| Beta | ERP data pass-through |\n'
    } >"$root/$BRIEF"
  fi

  case "$research" in
    missing) : ;;
    empty)
      mkdir -p "$root/output/research/acme-run"
      : >"$root/output/research/acme-run/00-notes.md"
      ;;
    full|bare)
      mkdir -p "$root/output/research/acme-run"
      {
        printf '# Notes\n\n'
        printf '## Corrections to the record\n\n'
        if [ "$research" = "full" ]; then
          printf '1. **Beta is not Series B.** It raised a EUR 5M seed in Nov 2022.\n'
          printf '2. **Gamma has no pricing page.** Confirmed 404.\n'
          printf -- '- **Beta headcount is ~57, not ~200.**\n'
        fi
        printf '\n## Something else\n\n'
        printf '1. This numbered item is outside the corrections block and must not be harvested.\n'
      } >"$root/output/research/acme-run/00-notes.md"
      ;;
  esac

  if [ "$snaps" != "no" ]; then
    if [ "$snaps" = "mixed" ]; then
      # A clean cohort snapshot, sorting FIRST so the glob reaches it before any match. Its grep
      # returns 1, which `pipefail` used to promote into a script-killing status: this file is what
      # makes the empty-result path reachable from the selftest.
      {
        printf '{\n  "domain": "alpha.com",\n  "captured": "2026-09-02",\n'
        printf '  "third_party": {"g2": "ALPHA CLEAN LINE, rating 4.5 fetched"}\n}\n'
      } >"$root/output/snapshots/alpha.com.json"
    fi
    {
      printf '{\n  "domain": "beta.com",\n  "captured": "2026-09-02",\n'
      printf '  "third_party": {"g2": "direct fetch returned HTTP 403, rating not obtained"},\n'
      printf '  "frn": "FRN 1050315"\n}\n'
    } >"$root/output/snapshots/beta.com.json"
    {
      printf '{\n  "domain": "gamma.com",\n  "captured": "2026-09-02",\n'
      printf '  "third_party": {"glassdoor": "listing found, 403 Forbidden on direct fetch"}\n}\n'
    } >"$root/output/snapshots/gamma.com.json"
    # An earlier client's snapshot, with its own blocked line. run_cohort() excludes it by date and
    # so must this script: a trap from a previous company is exactly what R8 forbids.
    {
      printf '{\n  "domain": "oldco.com",\n  "captured": "2026-05-06",\n'
      printf '  "third_party": {"g2": "OLDCO BLOCKED LINE 403 Forbidden"}\n}\n'
    } >"$root/output/snapshots/oldco.com.json"
  fi
}

# make_brief_root builds a fixture in THE LAYOUT A LIVE RUN USES: everything the run wrote sits under
# `output/runs/acme-2026-09-04/`, which is what `BRIEF_ROOT` names. Three properties make the case
# decide something no other fixture here can:
#   * `output/research/acme-run/` DOES NOT EXIST, so a corpus path built from the client name finds
#     nothing and the run fails closed -- which is what every non-exemplar run met.
#   * The exemplar's `output/snapshots/` holds a blocked line of its own, captured on THE SAME DATE
#     as the run's own cohort, so the date discriminator alone cannot exclude it. Only reading the
#     right directory can. That row appearing in the block is another company's evidence in this
#     company's fact-integrity input.
#   * The run's own snapshot carries a different blocked line, so the two are told apart by text.
#   $2 subtitle=yes|no  no = a draft with no `Prepared for <Client>.` sentence.
make_brief_root() {
  local root="$1" subtitle="$2" run="output/runs/acme-2026-09-04"
  mkdir -p "$root/build" "$root/output/review" "$root/output/snapshots" "$root/$run/snapshots" \
    "$root/tools"
  cp "${BASH_SOURCE[0]}" "$root/tools/known-traps.sh"

  {
    if [ "$subtitle" = "yes" ]; then
      printf '<p class="subtitle">Prepared for Acme. Covering Beta, Gamma.</p>\n'
    else
      printf '<p class="subtitle">Covering Beta, Gamma.</p>\n'
    fi
    printf '\n## %s\n\n' "$FX_SECTION"
    printf '**Acme is the only platform in this set that moves money on rules.**\n'
    printf 'No competitor ships a control page, and Beta is alone in claiming one.\n'
    printf '| Beta | ERP data pass-through |\n'
  } >"$root/$BRIEF"

  {
    printf '# Notes\n\n'
    printf '## Corrections to the record\n\n'
    printf '1. **Beta is not Series B.** It raised a EUR 5M seed in Nov 2022.\n'
    printf '2. **Gamma has no pricing page.** Confirmed 404.\n'
  } >"$root/$run/00-notes.md"

  {
    printf '{\n  "domain": "beta.com",\n  "captured": "2026-09-02",\n'
    printf '  "third_party": {"g2": "RUN COHORT BLOCKED LINE 403 Forbidden"}\n}\n'
  } >"$root/$run/snapshots/beta.com.json"

  {
    printf '{\n  "domain": "oldco.com",\n  "captured": "2026-09-02",\n'
    printf '  "third_party": {"g2": "EXEMPLAR BLOCKED LINE 403 Forbidden"}\n}\n'
  } >"$root/output/snapshots/oldco.com.json"
}

# run_case invokes the real entry points, capturing output and true exit status.
# `|| rc=$?` is what keeps `set -e` from aborting the harness on an expected red.
#
# THE `process` MODE, and why one case must not share this shell. Measured on this bash 3.2: inside
# `OUT="$( ( generate ... ) 2>&1 )"`, `set -e` is NOT in force, so a command that fails there is
# stepped over and the harvest completes anyway. Every in-process case below is therefore blind to a
# `set -e` abort by construction -- which is exactly how a `pipefail`-promoted grep miss shipped: it
# killed the real script and no case moved. The `process` mode runs the script file itself, so the
# child gets its own fully armed `set -euo pipefail`, which is how
# `docs/history/pipeline.md:562-565` runs it: a child bash on the script file, not a sourced function.
RC=0
OUT=""
CASE_ROOT=""
run_case() {
  local root="$1" mode="$2"
  RC=0
  case "$mode" in
    check)   OUT="$( ( cd "$root" && assert_traps ) 2>&1 )" || RC=$? ;;
    force)   OUT="$( ( generate "$root" yes '2026-09-04' ) 2>&1 )" || RC=$? ;;
    # A second --force on a LATER date, which is the only way the title re-stamp is observable: a
    # force run sharing the create run's date leaves a correct title behind whether or not the
    # script rewrote it.
    restamp) OUT="$( ( generate "$root" yes '2026-09-06' ) 2>&1 )" || RC=$? ;;
    process) OUT="$( BRIEF_RUN_DATE=2026-09-04 bash "$root/tools/known-traps.sh" 2>&1 )" || RC=$? ;;
    # The live path: a run exports BRIEF_ROOT and everything it wrote is under it. CASE_ROOT is the
    # value, set by the case, so one mode serves the green and the red.
    briefroot) OUT="$( BRIEF_ROOT="$CASE_ROOT" BRIEF_RUN_DATE=2026-09-04 \
                 bash "$root/tools/known-traps.sh" 2>&1 )" || RC=$? ;;
    *)       OUT="$( ( generate "$root" no  '2026-09-04' ) 2>&1 )" || RC=$? ;;
  esac
  return 0
}

expect_green() {
  local label="$1" root="$2" mode="$3" want="$4"
  run_case "$root" "$mode"
  if [ "$RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: %s exited %s, want 0; got: %s\n' "$label" "$RC" "$OUT" >&2
    return 1
  fi
  case "$OUT" in
    *"$want"*) printf 'SELFTEST green OK %-34s -> %s\n' "$label" "$OUT" ;;
    *) printf 'SELFTEST FAIL: %s was green but did not print %s; got: %s\n' "$label" "$want" "$OUT" >&2
       return 1 ;;
  esac
}

expect_red() {
  local label="$1" root="$2" mode="$3" want="$4"
  run_case "$root" "$mode"
  if [ "$RC" -eq 0 ]; then
    printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "$OUT" >&2
    return 1
  fi
  case "$OUT" in
    *"$want"*) printf 'SELFTEST red OK   %-34s -> exit %s, %s\n' "$label" "$RC" "$(printf '%s' "$OUT" | head -1)" ;;
    *) printf 'SELFTEST FAIL: %s went red with the wrong message; want %s, got: %s\n' "$label" "$want" "$OUT" >&2
       return 1 ;;
  esac
}

expect_absent() {
  local label="$1" f="$2"
  if [ -e "$f" ]; then
    printf 'SELFTEST FAIL: %s wrote %s; a file describing no run is worse than no file\n' "$label" "$f" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> no file written\n' "$label"
}

expect_contains() {
  local label="$1" f="$2" want="$3"
  if ! grep -qF -e "$want" "$f"; then
    printf 'SELFTEST FAIL: %s: %s does not contain %s\n' "$label" "$f" "$want" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> contains %s\n' "$label" "$want"
}

expect_lacks() {
  local label="$1" f="$2" unwanted="$3"
  if grep -qF -e "$unwanted" "$f"; then
    printf 'SELFTEST FAIL: %s: %s contains %s and must not\n' "$label" "$f" "$unwanted" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> lacks %s\n' "$label" "$unwanted"
}

selftest() {
  local root f n

  make_temp_dir known-traps-selftest
  TMP="$NEW_TEMP_DIR"

  # G1 the complete corpus: all three sources harvest, the file is created, the assert passes.
  root="$TMP/g1"
  make_root "$root" yes full yes
  expect_green 'full corpus writes and asserts' "$root" write 'TRAPS-OK'
  f="$root/$TRAPS_FILE"
  expect_contains 'S1 corrections harvested' "$f" 'Beta is not Series B'
  expect_contains 'S4 superlatives harvested' "$f" 'S4 superlative, term "only"'
  expect_contains 'S5 blocked harvested' "$f" 'S5 blocked'
  expect_contains 'header names run and date' "$f" '# KNOWN TRAPS -- Acme, cohort captured 2026-09-02, harvested 2026-09-04'
  expect_contains 'slots 2, 3, 6 named' "$f" 'Orchestrator slots still owed'
  # Cohort scoping, the R8 guard: the earlier client's blocked line must not appear.
  expect_lacks 'earlier client excluded' "$f" 'OLDCO BLOCKED LINE'
  # Only items inside a Corrections heading count.
  expect_lacks 'non-corrections item ignored' "$f" 'must not be harvested'
  # Six or more rows, so the shortfall word must be absent: it is the assert's other arm, and
  # writing it unconditionally would make `grep -q shortfall` a permanent loophole.
  n="$(count_rows '^- ' "$f")"
  if [ "$n" -lt 6 ]; then
    printf 'SELFTEST FAIL: full corpus harvested %s rows, want >= 6 for the no-shortfall case\n' "$n" >&2
    return 1
  fi
  expect_lacks 'no shortfall when rows >= 6' "$f" 'shortfall'
  printf 'SELFTEST OK       %-34s -> %s rows\n' 'full corpus row count' "$n"

  # G2 --check against what was just written.
  expect_green 'check-only on a good file' "$root" check 'TRAPS-OK'

  # G3 a second run without --force refuses, and the file is untouched.
  local before after
  before="$(cat "$f")"
  expect_red 'refuses to clobber its own block' "$root" write 'already carries a harvested block'
  after="$(cat "$f")"
  if [ "$before" != "$after" ]; then
    printf 'SELFTEST FAIL: the refused re-run modified %s\n' "$f" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> file byte-identical\n' 'refused re-run changes nothing'

  # G4 --force replaces the block and preserves an orchestrator row written outside it.
  printf -- '- [S6 orchestrator] at output/research/acme-run/00-notes.md:1 | correct value: judgement row | claim: "the client own numbers"\n' >>"$f"
  expect_green 'force replaces its own block' "$root" force 'TRAPS-OK'
  expect_contains 'orchestrator row survives --force' "$f" 'S6 orchestrator'
  if [ "$(count_rows "$BEGIN_MARK" "$f")" -ne 1 ]; then
    printf 'SELFTEST FAIL: --force left %s begin markers in %s\n' "$(count_rows "$BEGIN_MARK" "$f")" "$f" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> exactly one marked block\n' 'force does not duplicate the block'

  # G4b the title, which sits OUTSIDE the markers and so was never touched by the replace. MEASURED
  # red before the fix: this file still read `harvested 2026-09-04` above rows harvested on
  # 2026-09-06, so the fact-integrity pass met a previous run's header in front of this run's
  # evidence. The later date is what makes the defect observable at all.
  expect_green 'force re-stamps the title' "$root" restamp 'TRAPS-OK'
  expect_contains 'title names the harvesting run' "$f" \
    '# KNOWN TRAPS -- Acme, cohort captured 2026-09-02, harvested 2026-09-06'
  expect_lacks 'no previous run date left behind' "$f" '2026-09-04'
  expect_contains 'orchestrator row survives re-stamp' "$f" 'S6 orchestrator'

  # G5 an orchestrator file with no marked block is appended to, never rewritten.
  root="$TMP/g5"
  make_root "$root" yes full yes
  mkdir -p "$root/output/review"
  {
    printf '# KNOWN TRAPS -- Acme (orchestrator)\n\n'
    printf -- '- [S2 orchestrator] at output/research/acme-run/00-notes.md:1 | correct value: the raise was restated | claim: "Beta raised EUR 5M"\n'
  } >"$root/$TRAPS_FILE"
  expect_green 'appends beside orchestrator rows' "$root" write 'TRAPS-OK'
  expect_contains 'orchestrator row preserved' "$root/$TRAPS_FILE" 'S2 orchestrator'
  expect_contains 'block appended' "$root/$TRAPS_FILE" 'S1 corrections'

  # G6 the shortfall branch: a corpus yielding one to five rows states the shortfall and does not
  # pad. Here only S5 harvests, because the draft carries no superlative and the corrections block
  # is empty.
  root="$TMP/g6"
  make_root "$root" bare bare yes
  expect_green 'few rows state the shortfall' "$root" write 'TRAPS-OK'
  expect_contains 'shortfall stated' "$root/$TRAPS_FILE" 'shortfall: this file carries'
  n="$(count_rows '^- ' "$root/$TRAPS_FILE")"
  if [ "$n" -ge 6 ] || [ "$n" -eq 0 ]; then
    printf 'SELFTEST FAIL: shortfall fixture harvested %s rows, want 1..5\n' "$n" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> %s rows, under six, none invented\n' 'shortfall fixture row count' "$n"

  # G7 a cohort holding a snapshot with no blocked source at all, run as its own process. This is
  # the ordinary case in the field -- five of this repository's own cohort snapshots record no
  # refusal -- and it used to kill the script: grep exits 1 on no match, `pipefail` made that the
  # pipeline's status and `set -e` aborted mid-harvest, exiting 1 with nothing written and nothing
  # printed. The clean snapshot sorts first, so the abort landed before any blocked row was
  # composed. `process` mode is load-bearing here, not incidental: run in-process this case passes
  # against the broken code, because `set -e` does not reach inside a command substitution. The last
  # two assertions cover the other half of the same loop: `read` returns 1 on the unterminated last
  # line, which silently dropped the final cohort snapshot's refusals.
  root="$TMP/g7"
  make_root "$root" yes full mixed
  mkdir -p "$root/tools"
  cp "${BASH_SOURCE[0]}" "$root/tools/known-traps.sh"
  expect_green 'clean snapshot in cohort' "$root" process 'TRAPS-OK'
  f="$root/$TRAPS_FILE"
  expect_lacks 'clean snapshot yields no row' "$f" 'ALPHA CLEAN LINE'
  expect_contains 'harvest continues past it' "$f" 'listing found, 403 Forbidden on direct fetch'
  n="$(count_rows '^- ' "$f")"
  if [ "$n" -lt 6 ]; then
    printf 'SELFTEST FAIL: mixed cohort harvested %s rows, want >= 6 as in the full corpus\n' "$n" >&2
    return 1
  fi
  printf 'SELFTEST OK       %-34s -> %s rows, clean snapshot skipped not fatal\n' 'mixed cohort row count' "$n"

  # G8 the same empty-result hazard on the other harvester, and the reason it needs its own case:
  # every other fixture draft carries a superlative, so S4's grep always matched and its identical
  # `pipefail` bug stayed invisible. A draft that claims nothing is a normal draft. Process mode for
  # the same reason as G7 -- in-process this passes against the broken code.
  root="$TMP/g8"
  make_root "$root" bare bare yes
  mkdir -p "$root/tools"
  cp "${BASH_SOURCE[0]}" "$root/tools/known-traps.sh"
  expect_green 'draft with no superlative' "$root" process 'TRAPS-OK'
  expect_lacks 'no superlative row invented' "$root/$TRAPS_FILE" 'S4 superlative'

  # G9 THE LIVE LAYOUT: `BRIEF_ROOT` set, the corpus and the cohort both inside it. Process mode, so
  # the child arms its own `set -euo pipefail` and the env var arrives the way a run exports it.
  root="$TMP/g9"
  make_brief_root "$root" yes
  CASE_ROOT="output/runs/acme-2026-09-04"
  expect_green 'corpus and cohort under BRIEF_ROOT' "$root" briefroot 'TRAPS-OK'
  f="$root/$TRAPS_FILE"
  expect_contains 'corpus read from the run root' "$f" 'Beta is not Series B'
  expect_contains 'cohort read from the run root' "$f" 'RUN COHORT BLOCKED LINE'
  # THE R8 GUARD, and the reason this case exists: the exemplar's snapshot shares this run's
  # captured date, so nothing but reading the right directory keeps it out.
  expect_lacks 'exemplar cohort not harvested' "$f" 'EXEMPLAR BLOCKED LINE'
  expect_contains 'block stamped with this client' "$f" '# KNOWN TRAPS -- Acme, cohort captured 2026-09-02'

  # G10 the same root with no `Prepared for <Client>.` sentence: the block cannot say whose run it
  # harvested, so the harvest fails closed and writes nothing. The corpus is present and complete,
  # so the subtitle rule is the only rule that can red this.
  root="$TMP/g10"
  make_brief_root "$root" no
  CASE_ROOT="output/runs/acme-2026-09-04"
  expect_red 'BRIEF_ROOT set, draft has no subtitle' "$root" briefroot 'carries no'
  expect_absent 'BRIEF_ROOT set, draft has no subtitle' "$root/$TRAPS_FILE"

  # R1 no research directory at all.
  root="$TMP/r1"
  make_root "$root" yes missing yes
  expect_red 'missing research corpus' "$root" write 'no research corpus at'
  expect_absent 'missing research corpus' "$root/$TRAPS_FILE"

  # R2 a research directory whose files are all empty. "No run happened" must not launder into
  # "gate passed", so this is a different message from R1 and a different repair.
  root="$TMP/r2"
  make_root "$root" yes empty yes
  expect_red 'empty research corpus' "$root" write 'holds no non-empty .md file'
  expect_absent 'empty research corpus' "$root/$TRAPS_FILE"

  # R3 no draft.
  root="$TMP/r3"
  make_root "$root" no full yes
  expect_red 'missing draft' "$root" write 'no draft at'
  expect_absent 'missing draft' "$root/$TRAPS_FILE"

  # R4 a complete corpus that yields nothing: no corrections items, no superlative, no snapshot.
  root="$TMP/r4"
  make_root "$root" bare bare no
  expect_red 'zero rows harvested' "$root" write 'harvested 0 traps'
  expect_absent 'zero rows harvested' "$root/$TRAPS_FILE"

  # R5 the assert's own first arm: --check with no file.
  root="$TMP/r5"
  make_root "$root" yes full yes
  expect_red 'check with no traps file' "$root" check 'no traps block at'

  # R6 the assert's shortfall arm: a file somebody else wrote, three rows and no shortfall.
  root="$TMP/r6"
  make_root "$root" yes full yes
  {
    printf '# KNOWN TRAPS\n\n'
    printf -- '- one\n- two\n- three\n'
  } >"$root/$TRAPS_FILE"
  expect_red 'check on three rows, no shortfall' "$root" check '3 traps and no stated shortfall'

  cleanup_temps
  printf 'SELFTEST OK: 10 green cases (full corpus, check, refuse-to-clobber, force-preserves-orchestrator-rows, force-re-stamps-the-title, append-beside-orchestrator-rows, shortfall, clean-snapshot-in-cohort, draft-with-no-superlative, corpus-and-cohort-under-BRIEF_ROOT with the exemplar cohort of the same captured date proved absent from the block) and 7 red cases (missing corpus, empty corpus, missing draft, zero rows, check-with-no-file, check-under-six-with-no-shortfall, BRIEF_ROOT-set-draft-with-no-subtitle), every red one writing no file\n'
}

usage() {
  printf 'usage: known-traps.sh [--force | --check | --selftest]\n' >&2
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  trap cleanup_temps EXIT
  trap 'cleanup_temps; exit 130' HUP INT TERM
  case "${1:-}" in
    --selftest) selftest ;;
    --check)    ( cd "$ROOT" && assert_traps ) ;;
    --force)    main yes ;;
    "")         main no ;;
    *)          usage; exit 2 ;;
  esac
fi
