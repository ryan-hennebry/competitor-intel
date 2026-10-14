#!/usr/bin/env bash
# The gap falsification lint. It grades one run-authored gap ledger against the Threat Landscape
# table of one brief, collects every finding, and fails closed.
#
# THE ABSTRACTION. A Key Gap is the one column of the brief that tells the reader where to attack.
# It is also the column most easily written by assertion: a rival's page does not mention payroll,
# so "No payroll" is typed into `build/briefing.md:43` and ships. The GAP LEDGER at
# `output/review/gaps.md` is the run's record of having tried to KILL each candidate gap before
# printing it -- what was claimed, which sub-claims died and why, and what state the surviving
# absence rests on. This script grades that record. G1 asks whether every rival in the Threat
# Landscape has a ledger block at all. G2 asks whether each block has the shape the exercise needs:
# one claim, at least one attempt on it, a reason for every kill, one absence. G3 asks whether the
# surviving absence is an absence the run may call an absence -- the vocabulary is
# `references/provenance.md:9-13` rule 4, verbatim, "Verified-blocked is not verified-absent. A 403
# is recorded as blocked ... Only a 404 on a canonical path is absent, and a path this run
# constructed is not canonical." G4 asks the question with teeth: did the falsification REACH THE
# BRIEF. A killed phrase that is still sitting in the rival's Key Gap cell means the ledger recorded
# a kill the brief never applied, and the exercise was paperwork.
#
# WHY IT EXISTS. Nothing downstream reads the Key Gap column as a claim that was tested.
# `build/build.py`'s `audit()` grades structure and grades the URLs and threat levels against the
# snapshot cohort, `tools/thesis-check.sh` grades the thesis sidecar, `tools/date-stamp.sh` grades
# how the brief stamps time, `tools/scan-layer.sh` grades the scan read, `tools/ai-smell.sh` grades
# voice -- and a brief whose five Key Gap cells were each one unfalsified assertion, or one
# category-wide fact printed five times, renders green through all five. "Every gap is falsified
# before it ships" was an authoring standard with no check behind it, which `docs/DESIGN.md` says is
# the shape of an absolute claim that wants a gate.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name, so
# this is a standalone script the pipeline invokes, exactly as `tools/thesis-check.sh`,
# `tools/ai-smell.sh`, `tools/date-stamp.sh`, `tools/scan-layer.sh` and the ICP floor are standalone
# build-blocking lints. NOT a tenth review pass either: `docs/history/review/` holds one file per pass
# and every pass there is a JUDGEMENT dispatched to a subagent, while this is a mechanical grade of
# two files that a run executes and reads the exit code of. It is the FOURTH lint of the Phase 5
# chain, after `tools/ai-smell.sh`, `tools/date-stamp.sh` and `tools/scan-layer.sh`: the block headed
# `GAP TEST (V24)` in Phase 5 of `docs/history/pipeline.md` is the caller, and it reads "Fourth:";
# `tools/coverage-notes.sh` is fifth and last. Cited by its heading and not by a line number,
# because this file's slice renumbered `docs/history/pipeline.md` inside one session and a line
# citation went stale in it.
#
# It runs BEFORE the first build and reads the MARKDOWN brief only -- never the HTML and never the
# PDF. Every finding it raises is a prose edit or a ledger edit, and after the build a prose edit
# costs a rebuild.
#
# It collects every finding and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is. A ledger that breaks all four checks
# reports all four.
#
# THE LEDGER FORMAT, and why it is this shape. A header, then `---`, then one `### <Competitor>`
# block per rival, each carrying `claimed:`, one or more `killed:`, a `reason:` immediately under
# every kill, and one `absence:`. Every field value sits WHOLLY ON ONE LINE and every field line
# starts at column 0, so the format is greppable and a wrap cannot hide a field -- the same
# discipline `tools/fixtures/scan-blind-brief.md` records for fixture triggers. Everything before
# the first `### ` is prose the run writes for a human and is ignored: `output/review/gaps.md:1-17`
# is exactly that, a provenance header naming where the reconstructed exemplar ledger came from.
#
# TWO CLOSED VOCABULARIES, written once each at `G_REASON_TAGS` and `G_ABSENCE_STATES`. Of the three
# absence states, `verified-blocked` and `verified-absent` are rule 4's and `unfound` is this
# repository's own, defined at `G_ABSENCE_STATES` below. The reason tags are the four ways a
# candidate gap dies -- it is true of every rival (`same-thing`), the evidence was never found
# (`unfound`), the rival's own evidence says otherwise (`contradicted`), or it is real and is not a
# gap (`not-a-gap`). Both are matched by a whole-token prefix test against `TAG. `, never by a
# substring search, so `unfound` inside a sentence cannot pass as a tag.
#
# THE BRIEF SIDE. The Key Gap column is located by its HEADER TEXT, `Key Gap You Exploit`, and never
# by index. `references/briefing-template.md` owns the section list and the tables in it, so a column
# reorder is a legal edit there, and a check that hardcoded column 4 would silently start grading
# `Trend` -- a green with the wrong meaning, which is this repository's whole failure class. The
# competitor is column 1, which `references/brief-contract.md` fixes for every table in the brief.
#
# `grep` is wrapped to `ugrep` in the interactive shell, where a pattern starting with `--` parses as
# an option, so every pattern below is passed after `-e`. Inside this script `grep` is /usr/bin/grep
# (BSD). The parsing is `awk`, not `grep`: the units are positional (a field line's block, a killed
# line's immediately following line, a table cell's column) and a line-matching tool cannot express
# position.
#
# WHAT IT DELIBERATELY DOES NOT CHECK, and why each one is absent rather than forgotten:
#
#   1. WHETHER THE KILL IS TRUE. `reason: contradicted. ...` asserts that a rival's own page says
#      otherwise, and no shell script can grade that. It is a review-pass judgement and belongs to
#      `docs/history/review/`. What is mechanical is whether a reason was GIVEN, whether its tag is in
#      the closed vocabulary, and whether the killed phrase left the brief -- and those three are
#      graded here.
#   2. THE SURVIVING GAP'S WORDING. G4 asserts that killed phrases are ABSENT from the Key Gap cell.
#      It asserts nothing about what the cell does say, because the cell is prose and the brief's
#      own word discipline is `references/briefing-template.md`'s.
#   3. THE SNAPSHOTS. Whether `verified-absent` is supported by a 404 in
#      `output/snapshots/*.json` is `build/build.py`'s cohort work, not this script's; grading it
#      here would need the run directory, which this lint deliberately does not require.
#   4. CASE AND PUNCTUATION IN G4. The substring test is VERBATIM and case-sensitive. A run that
#      killed `No payroll` and shipped `no payroll module` is not caught. Booked rather than
#      guessed at: a case-folded test also matches a phrase the author legitimately reused in
#      another sense, and the fixture proves the verbatim direction, which is the one that matters.
#   5. THE RENDERED PDF. The check reads the source markdown. A gap the renderer mangles is
#      invisible to it.
#
# PRECONDITION: none beyond the two target files existing. No network, no MKT1 call, no env var, no
# build artefact, no run directory, no browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BRIEF="build/briefing.md"
DEFAULT_LEDGER="output/review/gaps.md"

# WHICH SECTION CARRIES THE GAP TABLE IS THE RUN'S TO NAME. D3 made a section a slot id plus the
# heading a run writes over it, and `references/briefing-template.md` grants a menu slot's run those
# words explicitly. This file asked for them by literal until `S5T-verify-2.md` R3 measured the
# consequence: a brief renamed under that grant renders at `audit()` exit 0 and gets a fail-closed
# message here naming a heading it deliberately does not carry, which reads as "your ledger is
# broken" rather than "this gate is keyed on a stale literal". `tools/slot-heading.sh` is the one
# resolver, and a missing one is a fail-closed exit rather than a gate that grades the wrong words.
if [ ! -f "$ROOT/tools/slot-heading.sh" ]; then
  printf 'FAIL: no slot resolver at %s/tools/slot-heading.sh\n' "$ROOT" >&2
  exit 2
fi
# shellcheck source=tools/slot-heading.sh
. "$ROOT/tools/slot-heading.sh"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

# The reason a run carried no gap table at all. Set only in the ABSENT state, printed by main_check,
# and never a finding -- see the three states in check_file.
SKIPPED=""

# Incremented once per check that ACTUALLY RUNS, so the success line cannot claim four checks while
# two run. Same intent as `CHECKS_RUN` in `tools/scan-layer.sh` and `tools/date-stamp.sh`, derived
# from execution rather than from a table. On the fail-closed path it stays 0 and the caller exits 1,
# so the OK line is never printed with a count of zero.
CHECKS_RUN=0

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# THE TWO CLOSED VOCABULARIES, and the only place either is written. Space-delimited, matched as a
# whole token followed by `. ` at position 1 of the value, so no tag can match inside a longer word
# and no sentence containing the word can pass as a tag.
#
# The four reason tags. A candidate gap dies one of four deaths and the ledger says which.
G_REASON_TAGS="same-thing unfound contradicted not-a-gap"

# The three absence states. TWO of them are `references/provenance.md:9-13` rule 4's, verbatim: a
# 403, 401, 429 or LinkedIn 999 is `verified-blocked`, and only a 404 on a canonical path is
# `verified-absent`. `unfound` is NOT rule 4's word. Rule 4 says a source that answers and does not
# carry the value is neither of the two, and stops there; `unfound` is this repository's name for
# that unnamed state, widened to cover a value the run does not hold because the source that would
# settle it either answered without carrying it or was never queried. Nilus's kill is the worked
# example, at `output/review/gaps.md:50-51`: no UK customer was found AND Companies House was never
# queried, and the second half is outside what rule 4 itself reaches. A durable change to this
# vocabulary belongs in `references/provenance.md` under `AGENTS.md`'s routing rule, not here.
G_ABSENCE_STATES="verified-absent verified-blocked unfound"

# --- the brief side -------------------------------------------------------------------------------
# brief_gaps() prints one TAB-separated record per gap-table row: competitor <TAB> Key Gap cell,
# both normalised (inline HTML stripped, ends trimmed, internal whitespace collapsed). The heading
# it opens on is the SECOND ARGUMENT, resolved from the run's own allocation record by the caller,
# never a literal. It prints NOTHING when that heading is absent from the brief, when no table
# follows it, or when the table carries no `Key Gap You Exploit` header -- and the caller treats
# empty as a FAILURE, never as zero rows.
brief_gaps() {
  awk -v OFS='\t' -v head="$2" '
    function norm(s) {
      gsub(/<[^>]*>/, "", s)            # inline HTML tags, inner text kept
      sub(/^[ \t]+/, "", s)
      sub(/[ \t]+$/, "", s)
      gsub(/[ \t]+/, " ", s)
      return s
    }
    # normhdr() reduces a header cell to its comparable form: norm() plus emphasis markers stripped
    # and case folded, so `**Key Gap You Exploit**` and `key gap you exploit` are the same label.
    function normhdr(s) {
      s = norm(s)
      gsub(/[*_]/, "", s)
      return tolower(s)
    }
    done { next }
    # ONE heading rule, and the comparison is against the heading text this run wrote, rather than
    # a pattern: the section opens where a heading matches it, any other heading ends the section.
    # If a table was already read, the FIRST table under the heading is the one graded and the scan
    # is over; if not, the heading was not followed by a table at all.
    /^#+[ \t]/ {
      h = $0
      sub(/^#+[ \t]+/, "", h)
      sub(/[ \t]+$/, "", h)
      if (h == head) { insec = 1; phase = ""; next }
      if (rows > 0) { done = 1 }
      insec = 0; phase = ""; next
    }
    !insec { next }
    /^[ \t]*\|/ {
      if (phase == "") {
        phase = "header"
        n = split($0, cell, "|")
        gapidx = 0
        for (i = 2; i < n; i++) if (normhdr(cell[i]) == "key gap you exploit") gapidx = i
        next
      }
      if (phase == "header") {
        if ($0 ~ /^[ \t]*\|[-: \t|]+$/) phase = "body"
        next
      }
      if (phase == "body" && gapidx > 0) {
        n = split($0, cell, "|")
        if (n > gapidx) {
          comp = norm(cell[2])
          if (comp != "") { print comp, norm(cell[gapidx]); rows++ }
        }
      }
      next
    }
    # A non-pipe line ends the table. Everything after it, up to the next heading, is ignored.
    phase == "body" { done = (rows > 0); insec = 0; phase = "" }
  ' "$1"
}

# --- the ledger side ------------------------------------------------------------------------------
# ledger_fields() prints one TAB-separated record per ledger unit, in document order:
#   line <TAB> competitor <TAB> key <TAB> value
# where key is `BLOCK` for a `### <Competitor>` heading and otherwise one of the four field names.
# Everything before the first `### ` is skipped, which is what makes the ledger's human header free
# prose. A `key: value` line whose key is not one of the four is skipped as prose too: the ledger is
# a document a person reads, and the failure of an unknown key surfaces as the field it was meant to
# be going missing, which G2 reports by name.
ledger_fields() {
  awk -v OFS='\t' '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    /^###[ \t]/ { comp = trim(substr($0, 4)); if (comp != "") print NR, comp, "BLOCK", comp; next }
    comp == "" { next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1)
      if (k != "claimed" && k != "killed" && k != "reason" && k != "absence") next
      print NR, comp, k, trim(substr($0, i + 1))
    }
  ' "$1"
}

# --- G2 -------------------------------------------------------------------------------------------
# g2_findings() prints one ready-made finding per line, sorted by source line so the output is
# deterministic. The shape rules are per block and one of them is POSITIONAL -- a `killed:` that is
# not `none` must be answered by a `reason:` on the very next line -- which is why this is awk and
# not a grep: any line at all between the two breaks the pairing, and that is the intent. A reason
# two lines below its kill reads as a reason for something else.
g2_findings() {
  awk -v f="$1" -v tags="$G_REASON_TAGS" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    # opens() returns the vocabulary token the value opens with, as `TOKEN. `, or "" for none.
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (index(v, arr[i] ". ") == 1) return arr[i]
      return ""
    }
    function flush() {
      if (comp == "") return
      if (pend != "")
        printf "%d\tFAIL: G2 killed \"%s\" under \"%s\" is not immediately followed by a reason: line at %s:%d\n", \
          pendline, pend, comp, f, pendline
      pend = ""
      if (nclaimed != 1)
        printf "%d\tFAIL: G2 block \"%s\" carries %d claimed: lines, want exactly 1, at %s:%d\n", \
          bline, comp, nclaimed, f, bline
      if (nabsence != 1)
        printf "%d\tFAIL: G2 block \"%s\" carries %d absence: lines, want exactly 1, at %s:%d\n", \
          bline, comp, nabsence, f, bline
      if (nkilled == 0)
        printf "%d\tFAIL: G2 block \"%s\" carries no killed: line, so nothing was attempted on the claim, at %s:%d\n", \
          bline, comp, f, bline
      if (nnone > 0 && nreason > 0)
        printf "%d\tFAIL: G2 block \"%s\" carries killed: none and %d reason: lines; a block with nothing killed carries no reason, at %s:%d\n", \
          bline, comp, nreason, f, bline
      # "A block with nothing killed carries EXACTLY ONE `killed: none`". `nnone` was counted and
      # never compared, so two of them in one block shipped green -- half a rule, which is the shape
      # `docs/DESIGN.md` calls a claim with no gate behind it.
      if (nnone > 1)
        printf "%d\tFAIL: G2 block \"%s\" carries %d killed: none lines, want exactly 1, at %s:%d\n", \
          bline, comp, nnone, f, bline
    }
    /^###[ \t]/ {
      flush()
      comp = trim(substr($0, 4)); bline = NR
      nclaimed = 0; nabsence = 0; nkilled = 0; nnone = 0; nreason = 0; pend = ""; pendline = 0
      next
    }
    comp == "" { next }
    {
      k = ""; v = ""
      i = index($0, ":")
      if (i > 1) { k = substr($0, 1, i - 1); v = trim(substr($0, i + 1)) }
      iskey = (k == "claimed" || k == "killed" || k == "reason" || k == "absence")
      # The pairing test, taken on EVERY line: a pending kill survives only if THIS line is its
      # reason. Any other line -- another field, prose, a blank -- answers it with nothing.
      if (pend != "" && !(iskey && k == "reason")) {
        printf "%d\tFAIL: G2 killed \"%s\" under \"%s\" is not immediately followed by a reason: line at %s:%d\n", \
          pendline, pend, comp, f, pendline
        pend = ""
      }
      # "EVERY FIELD VALUE SITS WHOLLY ON ONE LINE", which `docs/history/pipeline.md` Phase 4 step 2
      # states and which nothing asserted until V24. A wrapped `claimed:` or `absence:` continuation
      # carries no colon, so `ledger_fields()` drops it silently and the field grades as its first
      # half. Inside a block, a non-blank line that is neither a `### ` heading nor one of the four
      # recognised `key: value` lines is that wrap, or prose that belongs in the header -- reported
      # either way, by line, because the check cannot tell them apart and both are edits.
      if (!iskey) {
        if ($0 !~ /^[ \t]*$/)
          printf "%d\tFAIL: G2 stray or wrapped line inside block \"%s\" at %s:%d: \"%s\"; every field value sits wholly on one line and every field line starts at column 0\n", \
            NR, comp, f, NR, substr($0, 1, 40)
        next
      }
      if (k == "claimed") nclaimed++
      else if (k == "absence") nabsence++
      else if (k == "killed") {
        nkilled++
        if (v == "none") nnone++
        else { pend = v; pendline = NR }
      }
      else if (k == "reason") {
        nreason++
        pend = ""
        if (opens(v, tags) == "")
          printf "%d\tFAIL: G2 reason under \"%s\" opens \"%s\", which is not one of %s followed by \". \", at %s:%d\n", \
            NR, comp, substr(v, 1, 24), tags, f, NR
      }
    }
    END { flush() }
  ' "$1" | sort -n | cut -f2-
}

# --- G3 -------------------------------------------------------------------------------------------
# g3_findings() grades the absence state, and the one consequence rule that follows from it: a gap
# resting on an absence that was never verified may not ship as an absence unless something was
# actually killed to get there. `references/provenance.md:9-13` rule 4 -- a 403 is blocked, a source
# that answers without the value is neither blocked nor absent -- so a block claiming
# `verified-blocked` or `unfound` with `killed: none` has recorded no work at all and is asserting
# the gap, which is the thing this lint exists to stop.
g3_findings() {
  awk -v f="$1" -v states="$G_ABSENCE_STATES" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (index(v, arr[i] ". ") == 1) return arr[i]
      return ""
    }
    function flush() {
      if (comp == "") return
      if ((state == "verified-blocked" || state == "unfound") && nreal == 0)
        printf "%d\tFAIL: G3 block \"%s\" rests on an absence state \"%s\" with nothing killed; an absence that was not verified may not ship as a gap (references/provenance.md rule 4), at %s:%d\n", \
          bline, comp, state, f, bline
    }
    /^###[ \t]/ {
      flush()
      comp = trim(substr($0, 4)); bline = NR; state = ""; nreal = 0
      next
    }
    comp == "" { next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1); v = trim(substr($0, i + 1))
      if (k == "killed") { if (v != "none") nreal++ }
      else if (k == "absence") {
        state = opens(v, states)
        if (state == "")
          printf "%d\tFAIL: G3 absence under \"%s\" opens \"%s\", which is not one of %s followed by \". \", at %s:%d\n", \
            NR, comp, substr(v, 1, 24), states, f, NR
      }
    }
    END { flush() }
  ' "$1" | sort -n | cut -f2-
}

# --- the check ------------------------------------------------------------------------------------
# list_has tests a newline-delimited list for an exact whole-line member, with a bash `case` and no
# grep in the path: `case` patterns are whole-string anchored, so a competitor name cannot match
# inside a longer one.
list_has() {
  case $'\n'"$1"$'\n' in
    *$'\n'"$2"$'\n'*) return 0 ;;
  esac
  return 1
}

# check_file populates FAILS for one brief and one ledger and ALWAYS returns 0; the caller decides.
# Same contract as `check_file` in `tools/scan-layer.sh`, `tools/date-stamp.sh` and
# `tools/ai-smell.sh`, and it is what lets the selftest run every case in this shell without `set -e`
# ending the run at the first red.
check_file() {
  local brief="$1" ledger="$2" rows blocks recs kills name cell rec ln comp key val oldifs dups \
    rownames ordb ordr head rc

  FAILS=""
  CHECKS_RUN=0
  SKIPPED=""

  # FAIL CLOSED, four distinct messages, and every check skipped when any of them fires. A vacuous
  # pass is the failure mode this whole file exists to prevent: four checks reporting no findings on
  # a ledger that does not exist is precisely the shape of green this repository treats as a lie.
  if [ ! -e "$brief" ]; then
    add_fail "FAIL: no brief to grade at $brief (missing)"
  elif [ ! -s "$brief" ]; then
    add_fail "FAIL: no brief to grade at $brief (empty)"
  fi
  if [ ! -e "$ledger" ]; then
    add_fail "FAIL: no gap ledger to grade at $ledger (missing)"
  elif [ ! -s "$ledger" ]; then
    add_fail "FAIL: no gap ledger to grade at $ledger (empty)"
  fi
  if [ -n "$FAILS" ]; then
    return 0
  fi

  # THE THREE STATES OF THE SLOT, which are `build/build.py:slot_html()`'s and are kept identical
  # here on purpose. ABSENT is not a failure: the gap ledger grades the table a run chose to carry,
  # and `references/briefing-template.md` defines the ledger INSIDE the `threat-landscape` slot's
  # own description, so a run that took no such slot owes no ledger and this check says so and
  # passes. An unreadable record IS a failure, for the reason every fail-closed path in this file
  # exists: a check that cannot find its subject must not report a pass.
  rc=0
  head="$(slot_heading threat-landscape)" || rc=$?
  if [ "$rc" -eq 2 ]; then
    add_fail "FAIL: no readable allocation record at $(slot_heading_record); this check cannot know which section carries the gap table"
    return 0
  fi
  if [ "$rc" -eq 1 ]; then
    SKIPPED="this run's allocation record carries no threat-landscape slot, so $brief has no gap table to grade"
    return 0
  fi

  # The two structural preconditions, also fail-closed and also distinct. Empty here means the
  # heading is missing, no table follows it, or the table carries no `Key Gap You Exploit` column --
  # one message, because in all three the graded thing was not found. The heading is named in the
  # message as the RUN wrote it, so the fix a reader is sent to is a fix to the brief in front of
  # them.
  rows="$(brief_gaps "$brief" "$head")"
  if [ -z "$rows" ]; then
    add_fail "FAIL: no \"$head\" table with a Key Gap You Exploit column in $brief"
  fi
  recs="$(ledger_fields "$ledger")"
  blocks="$(printf '%s\n' "$recs" | awk -F'\t' '$3 == "BLOCK" { print $2 }')"
  if [ -z "$blocks" ]; then
    add_fail "FAIL: no ### competitor block in $ledger"
  fi
  if [ -n "$FAILS" ]; then
    return 0
  fi

  oldifs="$IFS"
  set -f
  IFS=$'\n'

  # --- G1: exactly one ledger block per Threat Landscape row -----------------------------------
  # Reported in both directions and by name, because the two are different defects with different
  # fixes: a missing block is falsification that was never done, and an extra block is a rival the
  # brief dropped -- or, on a live run, a ledger copied from another client.
  CHECKS_RUN=$((CHECKS_RUN + 1))
  for name in $(printf '%s\n' "$rows" | cut -f1); do
    if ! list_has "$blocks" "$name"; then
      add_fail "FAIL: G1 no ledger block for \"$name\", which the \"$head\" table of $brief carries"
    fi
  done
  for name in $blocks; do
    if ! list_has "$(printf '%s\n' "$rows" | cut -f1)" "$name"; then
      add_fail "FAIL: G1 ledger block \"$name\" names a competitor the \"$head\" table of $brief \
does not carry"
    fi
  done
  dups="$(printf '%s\n' "$blocks" | sort | uniq -d)"
  for name in $dups; do
    [ -n "$name" ] || continue
    add_fail "FAIL: G1 ledger carries more than one block named \"$name\"; want exactly one per row"
  done

  # ORDER, which `docs/history/pipeline.md` Phase 4 step 2 states as a contract -- one block per row
  # "in the brief's row order" -- and which nothing asserted until V24: a ledger holding every block
  # in reverse exits 0 unless the order is compared. Compared on the names the two sides SHARE, so a
  # missing or extra block is reported once, by the coverage rules above, and not a second time here
  # as an order defect it did not cause.
  rownames="$(printf '%s\n' "$rows" | cut -f1)"
  ordb=""
  for name in $blocks; do
    if list_has "$rownames" "$name"; then ordb="${ordb}${name}"$'\n'; fi
  done
  ordr=""
  for name in $rownames; do
    if list_has "$blocks" "$name"; then ordr="${ordr}${name}"$'\n'; fi
  done
  ordb="${ordb%$'\n'}"
  ordr="${ordr%$'\n'}"
  if [ "$ordb" != "$ordr" ]; then
    add_fail "FAIL: G1 ledger blocks are out of the \"$head\" row order of $brief; the \
ledger runs \"${ordb//$'\n'/ then }\" where the brief runs \"${ordr//$'\n'/ then }\""
  fi

  # --- G2: block shape ---------------------------------------------------------------------------
  CHECKS_RUN=$((CHECKS_RUN + 1))
  for rec in $(g2_findings "$ledger"); do
    add_fail "$rec"
  done

  # --- G3: the absence state is one rule 4 allows --------------------------------------------
  CHECKS_RUN=$((CHECKS_RUN + 1))
  for rec in $(g3_findings "$ledger"); do
    add_fail "$rec"
  done

  # --- G4: the falsification reached the brief ---------------------------------------------------
  # The check with teeth. A killed phrase still sitting verbatim in its rival's Key Gap cell means
  # the ledger recorded a kill the brief never applied.
  CHECKS_RUN=$((CHECKS_RUN + 1))
  kills="$(printf '%s\n' "$recs" | awk -F'\t' '$3 == "killed" && $4 != "none"')"
  if [ -n "$kills" ]; then
    for rec in $kills; do
      ln="${rec%%$'\t'*}"
      comp="${rec#*$'\t'}"
      key="${comp#*$'\t'}"
      comp="${comp%%$'\t'*}"
      val="${key#*$'\t'}"
      cell="$(printf '%s\n' "$rows" | awk -F'\t' -v c="$comp" '$1 == c { print $2; exit }')"
      # A block naming a competitor the brief does not carry has no cell to grade; G1 already
      # reported it by name, and inventing a finding here would report one defect twice.
      [ -n "$cell" ] || continue
      case "$cell" in
        *"$val"*)
          add_fail "FAIL: G4 killed phrase \"$val\" under \"$comp\" still appears verbatim in its \
Key Gap cell (\"$cell\") in $brief, at $ledger:$ln" ;;
      esac
    done
  fi

  IFS="$oldifs"
  set +f
  return 0
}

# --- the record -----------------------------------------------------------------------------------
# record_lines() prints the falsification record for one ledger: the derived counts, then per
# competitor in LEDGER ORDER the claim, each killed phrase with the tag of the reason that killed
# it, and the absence state. Plain text, readable cold, and every number derived from the file.
record_lines() {
  awk -v f="$1" -v tags="$G_REASON_TAGS" -v states="$G_ABSENCE_STATES" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (index(v, arr[i] ". ") == 1) return arr[i]
      return ""
    }
    function flush(   i) {
      if (comp == "") return
      body = body sprintf("\n%s\n", comp)
      body = body sprintf("  claimed: %s\n", claimed == "" ? "(none recorded)" : claimed)
      for (i = 1; i <= nk; i++)
        body = body sprintf("  killed [%s]: %s\n", tag[i] == "" ? "no reason" : tag[i], kill[i])
      if (nk == 0) body = body "  killed: none\n"
      body = body sprintf("  absence: %s\n", state == "" ? "(none recorded)" : state)
    }
    /^###[ \t]/ {
      flush()
      comp = trim(substr($0, 4)); claimed = ""; state = ""; nk = 0
      if (comp != "") gaps++
      next
    }
    comp == "" { next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1); v = trim(substr($0, i + 1))
      if (k == "claimed") claimed = v
      else if (k == "killed") { if (v != "none") { nk++; kill[nk] = v; tag[nk] = ""; killed++ } }
      else if (k == "reason") { if (nk > 0 && tag[nk] == "") tag[nk] = opens(v, tags) }
      else if (k == "absence") { state = opens(v, states); if (state == "") state = substr(v, 1, 24) }
    }
    END {
      flush()
      printf "GAP-TEST (%s): %d gaps, %d killed claims\n", f, gaps + 0, killed + 0
      printf "%s", body
    }
  ' "$1"
}

# --- selftest -------------------------------------------------------------------------------------
# Proves each failure mode red on its own minimal fixture, proves both vocabularies accepted in full
# from an INDEPENDENT literal, proves each fail-closed path red with its own message, proves the
# committed red artefact red on all four checks, proves the exemplar brief and the committed ledger
# green, and runs the script as a child process so `main_check()`, `main_record()`, the defaults, the
# argument dispatch, the OK line and the non-zero exit are exercised by the run and not by prose. A
# check that has never gone red is an untested assertion.

# write_lines writes a fixture from its remaining arguments, one line each. `: >"$f"` then `printf`,
# because `docs/DESIGN.md` bans heredoc writes in this repository.
write_lines() {
  local f="$1" line
  shift
  : >"$f"
  for line in "$@"; do
    printf '%s\n' "$line" >>"$f"
  done
}

# THE FIXTURE HEADINGS, NAMED ONCE. Every fixture brief below, the allocation record the resolver
# reads during the selftest, and every assertion that quotes a section derive from these three
# names, so the suite has exactly three places where a heading is written and `git grep -n
# heading-literal` finds all three. They are real catalogue defaults on purpose: a fixture heading
# nobody ships would leave the resolver untested against the shape a run actually writes, and the
# rename case below proves the other direction on a heading no catalogue carries.
FX_THREAT="Threat Landscape"  # heading-literal: the fixture record and every fixture brief derive from this name
FX_OPEN="Open Questions"      # heading-literal: the second heading of the clean fixture brief
FX_QUICK="Quick Take"         # heading-literal: the heading of the fixture brief that carries no table at all

# A clean brief fragment: the Threat Landscape shaped exactly as `build/briefing.md:41-47` shapes it,
# spans and all, so the normaliser is exercised by every case and not by one.
write_clean_brief() {
  local f="$1"
  write_lines "$f" \
    '# Competitor Intel Briefing' \
    '' \
    "## $FX_THREAT" \
    '' \
    '| Competitor | Threat | Trend | Key Gap You Exploit |' \
    '|---|---|---|---|' \
    '| Acme | <span class="t-high">HIGH</span> | <span class="trend">rising</span> | No payroll module. Buyer friction on the review sites. |' \
    '| Borealis | <span class="t-watch">WATCH</span> | <span class="trend">steady</span> | No UK entity. Payments export as a file. |' \
    '' \
    "## $FX_OPEN" \
    '' \
    '1. Can the approval rule gate the agent, or only payables?'
}

# The matching clean ledger: one block per row, one kill with a reason under Acme, `killed: none`
# under Borealis, both absences verified. Every red fixture below is this file plus one defect.
write_clean_ledger() {
  local f="$1"
  write_lines "$f" \
    '# Key Gap falsification -- Northwind brief' \
    '' \
    'captured: 2026-09-02' \
    '' \
    'This header is prose and is ignored: everything before the first block heading is free text.' \
    '' \
    '---' \
    '' \
    '### Acme' \
    '' \
    'claimed: No payroll module. Buyer friction on the review sites. Ten thousand clients.' \
    'killed: Ten thousand clients' \
    'reason: not-a-gap. It is a threat and not a gap.' \
    'absence: verified-absent. A 404 on the canonical payroll path.' \
    '' \
    '### Borealis' \
    '' \
    'claimed: No UK entity. Payments export as a file.' \
    'killed: none' \
    'absence: verified-absent. The payments module exports a file for manual upload.'
}

expect_red() {
  local label="$1" brief="$2" ledger="$3" want="$4"
  check_file "$brief" "$ledger"
  case "$FAILS" in
    *"$want"*) printf 'SELFTEST red OK   %-32s -> %s' "$label" "$FAILS" ;;
    *) printf 'SELFTEST FAIL: %s did not go red on %s; got: %s\n' \
         "$label" "$want" "${FAILS:-<no findings>}" >&2
       return 1 ;;
  esac
}

expect_green() {
  local label="$1" brief="$2" ledger="$3"
  check_file "$brief" "$ledger"
  if [ -n "$FAILS" ]; then
    printf 'SELFTEST FAIL: %s went red; got: %s\n' "$label" "$FAILS" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-32s -> no findings\n' "$label"
}

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main_check()`, `main_record()`, the
# `cd "$ROOT"`, the two defaults, the argument dispatch, the GAP-TEST-OK line, the record header and
# the non-zero exit would be exercised by nothing. That gap is load-bearing and not hypothetical:
# inside `OUT="$( (f) 2>&1 )"` bash suspends `set -e`, so an in-process case cannot see an abort at
# all, and it was `main()` on the real corpus that killed `tools/known-traps.sh` while its twelve
# in-process cases stayed green. The cases below copy this script into a fixture root and run it as a
# CHILD with its own fully armed `set -euo pipefail`, which is the invocation a run actually makes.
# The idiom is `tools/scan-layer.sh:446-511`.
PROC_RC=0
PROC_OUT=""

make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/build" "$root/output/review"
  cp "${BASH_SOURCE[0]}" "$root/tools/gap-test.sh"
  # The resolver travels with the script, because a child that cannot source it exits 2 before it
  # grades anything -- which is itself asserted, at P6 below.
  cp "$ROOT/tools/slot-heading.sh" "$root/tools/slot-heading.sh"
  write_lines "$root/build/headings.json" \
    "{ \"sections\": [ { \"slot\": \"threat-landscape\", \"heading\": \"$FX_THREAT\" } ] }"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/gap-test.sh" "$@" 2>&1 )" || PROC_RC=$?
  return 0
}

expect_proc_green() {
  local label="$1" root="$2" want="$3"
  shift 3
  run_proc "$root" "$@"
  if [ "$PROC_RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: %s exited %s, want 0; got: %s\n' "$label" "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *"$want"*) printf 'SELFTEST proc OK  %-32s -> exit 0, %s\n' "$label" "$want" ;;
    *) printf 'SELFTEST FAIL: %s was green but did not print %s; got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# expect_proc_red asserts the exit code AND the message AND the ABSENCE of the success token. A
# script that printed its OK line and then exited 1 anyway is the exact defect a sibling gate
# shipped with.
expect_proc_red() {
  local label="$1" root="$2" want="$3"
  shift 3
  run_proc "$root" "$@"
  if [ "$PROC_RC" -eq 0 ]; then
    printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *"$want"*) : ;;
    *) printf 'SELFTEST FAIL: %s went red with the wrong message; want %s, got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *GAP-TEST-OK*)
      printf 'SELFTEST FAIL: a red child run printed GAP-TEST-OK: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  printf 'SELFTEST proc red %-32s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp b l fixture cases=0 id missing proc tag st ntag nst rtags rstates eg ek

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/gap-test-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # THE SUITE OWNS ITS OWN ALLOCATION RECORD, and exports BRIEF_ROOT to say so. Same reason the
  # `bar-check` rows in `tools/ci-gates.sh` carry `BRIEF_ROOT=`: an operator with the variable
  # exported from a live run would otherwise have every case below resolve its section out of THAT
  # run record, and a fixture brief would be graded against a heading no fixture carries. Pinned
  # here rather than hoped for.
  write_lines "$tmp/headings.json" \
    "{ \"sections\": [ { \"slot\": \"threat-landscape\", \"heading\": \"$FX_THREAT\" } ] }"
  export BRIEF_ROOT="$tmp"

  b="$tmp/brief.md"
  l="$tmp/ledger.md"
  write_clean_brief "$b"
  write_clean_ledger "$l"

  # The scaffolding itself, green.
  expect_green 'clean brief and ledger' "$b" "$l"
  cases=$((cases + 1))

  # G1, DIRECTION ONE: a Threat Landscape row with no ledger block. This is falsification that was
  # never done, and it is the whole reason the check is not "the ledger is well-formed".
  sed -e '/^### Borealis/,$d' "$l" >"$tmp/g1-missing.md"
  expect_red 'G1 missing ledger block' "$b" "$tmp/g1-missing.md" \
    'FAIL: G1 no ledger block for "Borealis"'
  cases=$((cases + 1))

  # G1, DIRECTION TWO: a block naming a company the brief does not carry. On a live run this is a
  # ledger copied from another client, which is the same class of defect `run_cohort()` hits when a
  # foreign snapshot cohort is committed.
  cp "$l" "$tmp/g1-extra.md"
  write_lines "$tmp/g1-block.md" \
    '' \
    '### Vantor' \
    '' \
    'claimed: No payroll and no UK entity.' \
    'killed: none' \
    'absence: verified-absent. A 404 on the canonical payroll path.'
  cat "$tmp/g1-block.md" >>"$tmp/g1-extra.md"
  expect_red 'G1 extra ledger block' "$b" "$tmp/g1-extra.md" \
    'FAIL: G1 ledger block "Vantor" names a competitor'
  cases=$((cases + 1))

  # G1, the third shape: TWO blocks for one row. "Exactly one" is the rule, and two blocks means two
  # different answers to the same question with nothing deciding between them.
  cp "$l" "$tmp/g1-dup.md"
  sed -e 's/^### Borealis/### Acme/' "$tmp/g1-block.md" | sed -e 's/^### Vantor/### Acme/' \
    >>"$tmp/g1-dup.md"
  expect_red 'G1 duplicate ledger block' "$b" "$tmp/g1-dup.md" \
    'FAIL: G1 ledger carries more than one block named "Acme"'
  cases=$((cases + 1))

  # G1, THE MEMBERSHIP TEST ITSELF. `list_has` anchors on whole lines, and nothing proved it: on a
  # table whose first competitor is a strict PREFIX of its second, a substring test finds "Acme"
  # inside the block named "Acme Group" and reports full coverage of a ledger that never falsified
  # Acme at all. Only the anchored test sees the missing block.
  write_lines "$tmp/prefix-brief.md" \
    "## $FX_THREAT" \
    '' \
    '| Competitor | Threat | Trend | Key Gap You Exploit |' \
    '|---|---|---|---|' \
    '| Acme | HIGH | rising | No payroll module. |' \
    '| Acme Group | WATCH | steady | No UK entity. |'
  write_lines "$tmp/prefix-ledger.md" \
    '### Acme Group' \
    '' \
    'claimed: No UK entity. Ten thousand clients.' \
    'killed: Ten thousand clients' \
    'reason: not-a-gap. It is a threat and not a gap.' \
    'absence: verified-absent. A 404 on the canonical UK path.'
  expect_red 'G1 name is a prefix of another' "$tmp/prefix-brief.md" "$tmp/prefix-ledger.md" \
    'FAIL: G1 no ledger block for "Acme"'
  cases=$((cases + 1))

  # G1, THE ORDER CONTRACT. Same two blocks, same two rows, every field well formed -- and the
  # ledger runs backwards. `docs/history/pipeline.md` Phase 4 step 2 says "in the brief's row order",
  # and before V24 that sentence had nothing behind it.
  write_lines "$tmp/g1-order.md" \
    '# Key Gap falsification -- Northwind brief' \
    '' \
    '---' \
    '' \
    '### Borealis' \
    '' \
    'claimed: No UK entity. Payments export as a file.' \
    'killed: none' \
    'absence: verified-absent. The payments module exports a file for manual upload.' \
    '' \
    '### Acme' \
    '' \
    'claimed: No payroll module. Buyer friction on the review sites. Ten thousand clients.' \
    'killed: Ten thousand clients' \
    'reason: not-a-gap. It is a threat and not a gap.' \
    'absence: verified-absent. A 404 on the canonical payroll path.'
  expect_red 'G1 blocks out of row order' "$b" "$tmp/g1-order.md" \
    "FAIL: G1 ledger blocks are out of the \"$FX_THREAT\" row order of"
  cases=$((cases + 1))

  # G2, one case per sub-rule. Each fixture is the clean ledger plus exactly one defect, so a red
  # proves the rule and not the scaffolding.
  sed -e '/^claimed: No payroll module/d' "$l" >"$tmp/g2-noclaim.md"
  expect_red 'G2 no claimed: line' "$b" "$tmp/g2-noclaim.md" \
    'FAIL: G2 block "Acme" carries 0 claimed: lines'
  cases=$((cases + 1))

  awk '{ print } /^claimed: No payroll module/ { print }' "$l" >"$tmp/g2-twoclaim.md"
  expect_red 'G2 two claimed: lines' "$b" "$tmp/g2-twoclaim.md" \
    'FAIL: G2 block "Acme" carries 2 claimed: lines'
  cases=$((cases + 1))

  sed -e '/^absence: verified-absent. A 404/d' "$l" >"$tmp/g2-noabs.md"
  expect_red 'G2 no absence: line' "$b" "$tmp/g2-noabs.md" \
    'FAIL: G2 block "Acme" carries 0 absence: lines'
  cases=$((cases + 1))

  sed -e '/^killed: Ten thousand clients/d' -e '/^reason: not-a-gap/d' "$l" >"$tmp/g2-nokill.md"
  expect_red 'G2 no killed: line at all' "$b" "$tmp/g2-nokill.md" \
    'FAIL: G2 block "Acme" carries no killed: line'
  cases=$((cases + 1))

  # The POSITIONAL sub-rule. The reason is deleted, so the kill stands unanswered.
  sed -e '/^reason: not-a-gap/d' "$l" >"$tmp/g2-noreason.md"
  expect_red 'G2 killed with no reason' "$b" "$tmp/g2-noreason.md" \
    'FAIL: G2 killed "Ten thousand clients" under "Acme" is not immediately followed by a reason:'
  cases=$((cases + 1))

  # The same sub-rule from the other side, and the reason it is POSITIONAL and not a per-block count:
  # the reason is present but a line away, so it reads as a reason for something else. Without this
  # case, counting `reason:` lines per block would pass and the check would be weaker than it says.
  awk '/^reason: not-a-gap/ { print "The reason for that kill is on the line below." } \
       { print }' "$l" >"$tmp/g2-farreason.md"
  expect_red 'G2 reason one line late' "$b" "$tmp/g2-farreason.md" \
    'FAIL: G2 killed "Ten thousand clients" under "Acme" is not immediately followed by a reason:'
  cases=$((cases + 1))

  awk '{ print } /^killed: none/ { print "reason: unfound. Nothing was attempted." }' "$l" \
    >"$tmp/g2-nonereason.md"
  expect_red 'G2 killed: none with a reason' "$b" "$tmp/g2-nonereason.md" \
    'FAIL: G2 block "Borealis" carries killed: none and 1 reason: lines'
  cases=$((cases + 1))

  # "EXACTLY ONE `killed: none`", the other half of the same sentence. Two of them read as two
  # answers to "what did you attempt", and `nnone` was counted and never compared.
  awk '{ print } /^killed: none/ { print "killed: none" }' "$l" >"$tmp/g2-twonone.md"
  expect_red 'G2 two killed: none lines' "$b" "$tmp/g2-twonone.md" \
    'FAIL: G2 block "Borealis" carries 2 killed: none lines, want exactly 1'
  cases=$((cases + 1))

  # "EVERY FIELD VALUE SITS WHOLLY ON ONE LINE". The continuation below carries no colon, so
  # `ledger_fields()` drops it and Acme's claim grades as its first half -- a silent truncation, and
  # the one wrap `tools/fixtures/scan-blind-brief.md` records as having under-triggered V21's rules.
  awk '{ print } /^claimed: No payroll module/ { print "and ten thousand clients on the review sites." }' \
    "$l" >"$tmp/g2-wrapped.md"
  expect_red 'G2 wrapped field continuation' "$b" "$tmp/g2-wrapped.md" \
    'FAIL: G2 stray or wrapped line inside block "Acme"'
  cases=$((cases + 1))

  sed -e 's/^reason: not-a-gap\./reason: weak-evidence./' "$l" >"$tmp/g2-badtag.md"
  expect_red 'G2 reason tag outside the four' "$b" "$tmp/g2-badtag.md" \
    'FAIL: G2 reason under "Acme" opens "weak-evidence.'
  cases=$((cases + 1))

  # THE WHOLE-TOKEN PREFIX TEST, which the header claims and which `weak-evidence.` cannot prove: it
  # contains no tag as a substring, so a checker degraded to a substring search reds on it anyway.
  # This reason line CARRIES `unfound. ` -- in the middle of a sentence, where it is a word and not
  # a tag. Only the `== 1` position test sees that, and a run that narrates its way to a tag has
  # recorded a sentence, not a classification.
  sed -e 's/^reason: not-a-gap\..*$/reason: We could not find it, so it is unfound. Nobody queried the registry./' \
    "$l" >"$tmp/g2-tag-midsentence.md"
  expect_red 'G2 tag word mid-sentence' "$b" "$tmp/g2-tag-midsentence.md" \
    'FAIL: G2 reason under "Acme" opens "We could not find it, so'
  cases=$((cases + 1))

  # The OTHER half of "whole-token prefix against `TAG. `", and the other degradation it has to
  # survive: the value OPENS with the tag's letters and carries on into a longer word, so a bare
  # `index(...) == 1` with no `. ` terminator accepts it. Measured: the mid-sentence case above
  # cannot see that one, because its value does not open with a tag at all.
  sed -e 's/^reason: not-a-gap\..*$/reason: unfoundable evidence, so the claim stands./' \
    "$l" >"$tmp/g2-tag-longword.md"
  expect_red 'G2 tag inside a longer word' "$b" "$tmp/g2-tag-longword.md" \
    'FAIL: G2 reason under "Acme" opens "unfoundable evidence, so'
  cases=$((cases + 1))

  # THE REASON VOCABULARY, all four proved ACCEPTED, one fixture per tag. The list is pinned by the
  # LITERAL below and NOT by iterating `G_REASON_TAGS`, which would be a tautology: a loop reading
  # the list under test cannot see a word deleted from it, and deleting a tag would delete its own
  # test case at the same time and mutate green. That trap cost V23 a review round and is recorded at
  # `.claude/agent-memory/builder/`. The second loop closes the other direction: a tag ADDED to
  # `G_REASON_TAGS` and not pinned here is a failure too, so the two lists cannot drift apart.
  rtags="same-thing unfound contradicted not-a-gap"
  ntag=0
  for tag in $rtags; do
    ntag=$((ntag + 1))
    sed -e "s/^reason: not-a-gap\./reason: $tag./" "$l" >"$tmp/g2-tag.md"
    check_file "$b" "$tmp/g2-tag.md"
    if [ -n "$FAILS" ]; then
      printf 'SELFTEST FAIL: reason tag "%s" was not accepted; got: %s\n' "$tag" "$FAILS" >&2
      return 1
    fi
  done
  for tag in $G_REASON_TAGS; do
    case " $rtags " in
      *" $tag "*) : ;;
      *) printf 'SELFTEST FAIL: G_REASON_TAGS carries "%s", which no selftest case pins\n' \
           "$tag" >&2
         return 1 ;;
    esac
  done
  if [ "$ntag" -ne 4 ]; then
    printf 'SELFTEST FAIL: the pinned reason vocabulary holds %s tags, want 4\n' "$ntag" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-32s -> all %s pinned reason tags accepted\n' 'G2 reason vocabulary' \
    "$ntag"
  cases=$((cases + 1))

  # G3, the state vocabulary. Same two-loop discipline, and the fixture is ACME -- which carries a
  # real kill -- so `verified-blocked` and `unfound` are accepted here on their own merits and the
  # consequence rule below is tested separately rather than by accident.
  rstates="verified-absent verified-blocked unfound"
  nst=0
  for st in $rstates; do
    nst=$((nst + 1))
    sed -e "s/^absence: verified-absent\. A 404/absence: $st. A 404/" "$l" >"$tmp/g3-state.md"
    check_file "$b" "$tmp/g3-state.md"
    if [ -n "$FAILS" ]; then
      printf 'SELFTEST FAIL: absence state "%s" was not accepted; got: %s\n' "$st" "$FAILS" >&2
      return 1
    fi
  done
  for st in $G_ABSENCE_STATES; do
    case " $rstates " in
      *" $st "*) : ;;
      *) printf 'SELFTEST FAIL: G_ABSENCE_STATES carries "%s", which no selftest case pins\n' \
           "$st" >&2
         return 1 ;;
    esac
  done
  if [ "$nst" -ne 3 ]; then
    printf 'SELFTEST FAIL: the pinned absence vocabulary holds %s states, want 3\n' "$nst" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-32s -> all %s pinned absence states accepted\n' \
    'G3 absence vocabulary' "$nst"
  cases=$((cases + 1))

  sed -e 's/^absence: verified-absent\. A 404/absence: probably-absent. A 404/' "$l" \
    >"$tmp/g3-badstate.md"
  expect_red 'G3 absence state outside rule 4' "$b" "$tmp/g3-badstate.md" \
    'FAIL: G3 absence under "Acme" opens "probably-absent.'
  cases=$((cases + 1))

  # The same whole-token prefix test on the STATE vocabulary, and the reason it matters more here:
  # `unfound` is the state that triggers G3's consequence rule, so a narrated absence that merely
  # contains the word would be graded as the state and could carry a gap that nothing verified.
  sed -e 's/^absence: verified-absent\. A 404.*$/absence: We could not find it, so it is unfound. Nobody queried the registry./' \
    "$l" >"$tmp/g3-state-midsentence.md"
  expect_red 'G3 state word mid-sentence' "$b" "$tmp/g3-state-midsentence.md" \
    'FAIL: G3 absence under "Acme" opens "We could not find it, so'
  cases=$((cases + 1))

  sed -e 's/^absence: verified-absent\. A 404.*$/absence: unfoundable evidence at the registry./' \
    "$l" >"$tmp/g3-state-longword.md"
  expect_red 'G3 state inside a longer word' "$b" "$tmp/g3-state-longword.md" \
    'FAIL: G3 absence under "Acme" opens "unfoundable evidence at'
  cases=$((cases + 1))

  # THE CONSEQUENCE RULE, fired on each of the two unverified states. Borealis is the block with
  # `killed: none`, so an unverified absence there rests on no work at all.
  sed -e 's/^absence: verified-absent\. The payments/absence: verified-blocked. Every page 403ed. The payments/' \
    "$l" >"$tmp/g3-blocked.md"
  expect_red 'G3 verified-blocked, nothing killed' "$b" "$tmp/g3-blocked.md" \
    'FAIL: G3 block "Borealis" rests on an absence state "verified-blocked" with nothing killed'
  cases=$((cases + 1))

  sed -e 's/^absence: verified-absent\. The payments/absence: unfound. The page answered. The payments/' \
    "$l" >"$tmp/g3-unfound.md"
  expect_red 'G3 unfound, nothing killed' "$b" "$tmp/g3-unfound.md" \
    'FAIL: G3 block "Borealis" rests on an absence state "unfound" with nothing killed'
  cases=$((cases + 1))

  # And GREEN on `verified-absent` with nothing killed, which is Borealis in the clean ledger: the
  # consequence rule must fire on the state and not on `killed: none`.
  expect_green 'G3 verified-absent, nothing killed' "$b" "$l"
  cases=$((cases + 1))

  # G4, the check with teeth: the killed phrase is one the brief still prints in that rival's Key
  # Gap cell.
  sed -e 's/^killed: Ten thousand clients/killed: No payroll module/' "$l" >"$tmp/g4-red.md"
  expect_red 'G4 killed phrase still in the cell' "$b" "$tmp/g4-red.md" \
    'FAIL: G4 killed phrase "No payroll module" under "Acme" still appears verbatim in its Key Gap cell'
  cases=$((cases + 1))

  # G4 GREEN on a NEAR MISS -- one word different from the cell's text. Without this case the check
  # could be matching on any word of the phrase and the suite would not notice.
  sed -e 's/^killed: Ten thousand clients/killed: No payroll ledger/' "$l" >"$tmp/g4-near.md"
  expect_green 'G4 near miss, one word apart' "$b" "$tmp/g4-near.md"
  cases=$((cases + 1))

  # G4 IS PINNED TO ITS OWN COMPETITOR'S CELL, proved in both directions, because every case above
  # puts the kill under the FIRST table row -- so a checker that always graded row 1 passes all of
  # them. RED half: the kill sits under the SECOND competitor and its phrase is in the SECOND cell,
  # which only a per-competitor lookup can reach.
  awk '$0 == "killed: none" { print "killed: No UK entity"; \
         print "reason: contradicted. The UK page names a London office."; next } \
       { print }' "$l" >"$tmp/g4-second.md"
  expect_red 'G4 kill under the second row' "$b" "$tmp/g4-second.md" \
    'FAIL: G4 killed phrase "No UK entity" under "Borealis" still appears verbatim in its Key Gap cell'
  cases=$((cases + 1))

  # GREEN half, and the direction that stops the fix from being "search every cell": Acme's killed
  # phrase is printed in BOREALIS's cell and nowhere in Acme's. Acme applied its own falsification,
  # so there is no finding -- a checker that unioned the cells would invent one.
  sed -e 's/^killed: Ten thousand clients/killed: No UK entity/' "$l" >"$tmp/g4-crosscell.md"
  expect_green 'G4 killed phrase in another cell' "$b" "$tmp/g4-crosscell.md"
  cases=$((cases + 1))

  # THE COLUMN IS FOUND BY HEADER TEXT, NOT BY INDEX, proved in both directions on a brief whose Key
  # Gap column sits SECOND. The green half alone would not prove it: a checker hardcoding column 4
  # would read `Trend` on this table, find no killed phrase in it, and stay green. The red half is
  # the one that pins the anchor -- the killed phrase is in the reordered gap cell, and only a
  # checker that located the column by its header can see it.
  write_lines "$tmp/reordered.md" \
    "## $FX_THREAT" \
    '' \
    '| Competitor | Key Gap You Exploit | Threat | Trend |' \
    '|---|---|---|---|' \
    '| Acme | No payroll module. Buyer friction on the review sites. | <span class="t-high">HIGH</span> | rising |' \
    '| Borealis | No UK entity. Payments export as a file. | <span class="t-watch">WATCH</span> | steady |'
  expect_green 'gap column second, clean ledger' "$tmp/reordered.md" "$l"
  cases=$((cases + 1))

  expect_red 'gap column second, killed in cell' "$tmp/reordered.md" "$tmp/g4-red.md" \
    'FAIL: G4 killed phrase "No payroll module" under "Acme" still appears verbatim in its Key Gap cell'
  cases=$((cases + 1))

  # FAIL CLOSED, seven readings, each with its own message. Without these the whole script
  # could be pointed at nothing and report four clean checks.
  # Each assertion pins its OWN message, `(missing)` and `(empty)` included: the four readings are
  # four distinct defects and a run is sent to a different fix by each, so a shared prefix would let
  # "absent" and "empty" be rewritten into one message and still ship green.
  expect_red 'absent brief' "$tmp/nope.md" "$l" "FAIL: no brief to grade at $tmp/nope.md (missing)"
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty brief' "$tmp/empty.md" "$l" '(empty)'
  cases=$((cases + 1))

  expect_red 'absent ledger' "$b" "$tmp/nope-ledger.md" \
    "FAIL: no gap ledger to grade at $tmp/nope-ledger.md (missing)"
  cases=$((cases + 1))

  expect_red 'empty ledger' "$b" "$tmp/empty.md" 'FAIL: no gap ledger to grade at'
  cases=$((cases + 1))

  write_lines "$tmp/no-table.md" \
    '# Competitor Intel Briefing' \
    '' \
    "## $FX_QUICK" \
    '' \
    '**Nobody in this category has published a control model.** One page per agent would do it.'
  expect_red 'brief with no gap table' "$tmp/no-table.md" "$l" \
    "FAIL: no \"$FX_THREAT\" table with a Key Gap You Exploit column"
  cases=$((cases + 1))

  # The same message from the third direction: the heading and the table are there, and the column
  # is not. A checker that hardcoded the index would grade whatever sat in position 4.
  write_lines "$tmp/no-column.md" \
    "## $FX_THREAT" \
    '' \
    '| Competitor | Threat | Trend | Notes |' \
    '|---|---|---|---|' \
    '| Acme | HIGH | rising | No payroll module. |'
  expect_red 'table with no Key Gap column' "$tmp/no-column.md" "$l" \
    "FAIL: no \"$FX_THREAT\" table with a Key Gap You Exploit column"
  cases=$((cases + 1))

  write_lines "$tmp/no-block.md" \
    '# Key Gap falsification -- Northwind brief' \
    '' \
    'captured: 2026-09-02' \
    '' \
    '---'
  expect_red 'ledger with no ### block' "$b" "$tmp/no-block.md" 'FAIL: no ### competitor block in'
  cases=$((cases + 1))

  # THE RED ARTEFACT. It must red ALL FOUR checks, because a fixture that reds three leaves the
  # fourth proved by this file's own minimal strings alone. It is a committed artefact: if it is
  # absent, say so by path and fail, rather than stubbing it here and grading this script against its
  # own idea of an unfalsified ledger. It is graded against the REAL exemplar brief, which is what
  # makes its G1 and G4 triggers real rather than arranged.
  fixture="$ROOT/tools/fixtures/unfalsified-gaps.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no unfalsified-gaps red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  check_file "$ROOT/$DEFAULT_BRIEF" "$fixture"
  missing=""
  for id in G1 G2 G3 G4; do
    case "$FAILS" in
      *"FAIL: $id "*) : ;;
      *) missing="$missing $id" ;;
    esac
  done
  if [ -n "$missing" ]; then
    printf 'SELFTEST FAIL: %s did not go red on%s; got: %s\n' \
      "$fixture" "$missing" "${FAILS:-<no findings>}" >&2
    return 1
  fi
  printf 'SELFTEST red OK   %-32s -> all four checks red\n' 'unfalsified-gaps.md'
  cases=$((cases + 1))

  # THE EXEMPLAR ASSERTION, and the one that must never be weakened to reach green. If the exemplar
  # brief and the committed ledger go red here, the finding is the answer: report it and stop.
  # Editing a rule until the accepted artefacts pass is how a sibling rule ended up running backwards
  # against the thing it was meant to grade -- and `build/check_exemplar.sh` pins the brief's SHA256,
  # so the other direction is not available either.
  expect_green 'exemplar brief and gap ledger' "$ROOT/$DEFAULT_BRIEF" "$ROOT/$DEFAULT_LEDGER"
  cases=$((cases + 1))

  # P1: the whole script as a child, green, in --check mode with NO arguments, so both documented
  # defaults are the thing under test and are exercised by the run rather than by prose.
  proc="$tmp/proc-green"
  make_proc_root "$proc"
  cp "$b" "$proc/$DEFAULT_BRIEF"
  cp "$l" "$proc/$DEFAULT_LEDGER"
  expect_proc_green 'child, clean defaults' "$proc" 'GAP-TEST-OK' '--check'
  cases=$((cases + 1))

  # The OK line reports the check count and names the LEDGER, which is the artefact the run authored
  # and the one a finding sends the author back to. Four checks ran on this pair, so it must say 4.
  case "$PROC_OUT" in
    *"GAP-TEST-OK (4 checks, 0 findings in $DEFAULT_LEDGER)"*) : ;;
    *) printf 'SELFTEST FAIL: OK line did not report 4 checks on the ledger; got: %s\n' \
         "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-31s -> "%s"\n' 'OK line check count' "$PROC_OUT"
  cases=$((cases + 1))

  # And that the count is DERIVED FROM EXECUTION rather than written down, proved on the one pair of
  # runs where a derived counter and a constant differ: the fail-closed path runs no check and must
  # leave the counter at 0, a full grade must leave it at 4, and both readings come from the same
  # variable in the same shell. A counter assigned once, or not reset between grades, fails one of
  # the two. What no case can separate is the LITERAL `4` inside `main_check`'s printf, because
  # every green run runs all four checks and the two spellings print the same line -- so this pins
  # the counter, which is the thing that can drift, and claims nothing about the printf.
  check_file "$tmp/nope.md" "$l"
  if [ "$CHECKS_RUN" -ne 0 ]; then
    printf 'SELFTEST FAIL: the fail-closed path ran %s checks, want 0\n' "$CHECKS_RUN" >&2
    return 1
  fi
  check_file "$b" "$l"
  if [ "$CHECKS_RUN" -ne 4 ]; then
    printf 'SELFTEST FAIL: a full grade ran %s checks, want 4\n' "$CHECKS_RUN" >&2
    return 1
  fi
  printf 'SELFTEST detail OK %-31s -> 0 on the fail-closed path, 4 on a full grade\n' \
    'CHECKS_RUN derived'
  cases=$((cases + 1))

  # P2: the same child on the RED ARTEFACT as the default ledger, against the real exemplar brief.
  # Exit non-zero, the finding on the stream, and an explicit guard inside expect_proc_red that
  # GAP-TEST-OK was NOT printed.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  cp "$ROOT/$DEFAULT_BRIEF" "$proc/$DEFAULT_BRIEF"
  cp "$fixture" "$proc/$DEFAULT_LEDGER"
  expect_proc_red 'child, unfalsified default ledger' "$proc" 'FAIL: G4 killed phrase' '--check'
  cases=$((cases + 1))

  # P3: the child with a path ARGUMENT naming a file that does not exist, which is both the argument
  # dispatch and the fail-closed path, proved in the process that actually exits.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  cp "$b" "$proc/$DEFAULT_BRIEF"
  expect_proc_red 'child, absent ledger argument' "$proc" 'FAIL: no gap ledger to grade at' \
    '--check' "$DEFAULT_BRIEF" 'output/review/nope.md'
  cases=$((cases + 1))

  # P4: BARE MODE as a child with no argument at all -- the default mode and the default ledger
  # together. The two counts in the header are asserted against numbers derived HERE, from the
  # fixture, by a different method than the script uses, so a header that printed a constant would
  # fail. `eg` counts block headings; `ek` counts killed lines that are not `none`.
  proc="$tmp/proc-record"
  make_proc_root "$proc"
  cp "$l" "$proc/$DEFAULT_LEDGER"
  eg="$(grep -c -e '^### ' "$l" || true)"
  ek="$(awk '/^killed:/ { if ($0 != "killed: none") n++ } END { print n + 0 }' "$l")"
  expect_proc_green 'child, bare record mode' "$proc" \
    "GAP-TEST ($DEFAULT_LEDGER): $eg gaps, $ek killed claims"
  cases=$((cases + 1))

  # The record must print each competitor, its claim, its kills with the tag that killed them, and
  # its absence state -- which is what a reader opens it for.
  case "$PROC_OUT" in
    *'killed [not-a-gap]: Ten thousand clients'*) : ;;
    *) printf 'SELFTEST FAIL: the record did not tag a killed claim; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *'absence: verified-absent'*) : ;;
    *) printf 'SELFTEST FAIL: the record did not print an absence state; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-31s -> claim, tagged kill and absence state printed\n' 'record shape'
  cases=$((cases + 1))

  # P5: BARE MODE AGAIN, on a SECOND ledger whose two counts are different numbers. P4's fixture
  # derives 2 and 1, and a header that printed the constants 2 and 1 passed it -- one fixture cannot
  # tell a derived count from a written one. This ledger holds three blocks and two real kills, and
  # the same two independent counting methods are applied to it here.
  proc="$tmp/proc-record2"
  make_proc_root "$proc"
  write_lines "$tmp/ledger3.md" \
    '# Key Gap falsification -- a second ledger, three blocks and two kills' \
    '' \
    '---' \
    '' \
    '### Acme' \
    '' \
    'claimed: No payroll module. Ten thousand clients.' \
    'killed: Ten thousand clients' \
    'reason: not-a-gap. It is a threat and not a gap.' \
    'absence: verified-absent. A 404 on the canonical payroll path.' \
    '' \
    '### Borealis' \
    '' \
    'claimed: No UK entity. Payments export as a file.' \
    'killed: none' \
    'absence: verified-absent. The payments module exports a file for manual upload.' \
    '' \
    '### Vantor' \
    '' \
    'claimed: No UK entity and no payroll.' \
    'killed: No UK entity' \
    'reason: contradicted. The UK page names a London office.' \
    'absence: verified-absent. A 404 on the canonical payroll path.'
  cp "$tmp/ledger3.md" "$proc/$DEFAULT_LEDGER"
  eg="$(grep -c -e '^### ' "$tmp/ledger3.md" || true)"
  ek="$(awk '/^killed:/ { if ($0 != "killed: none") n++ } END { print n + 0 }' "$tmp/ledger3.md")"
  if [ "$eg" = "2" ] || [ "$ek" = "1" ]; then
    printf 'SELFTEST FAIL: the second record fixture derives %s gaps and %s kills, which does not \
differ from the first fixture in both counts\n' "$eg" "$ek" >&2
    return 1
  fi
  expect_proc_green 'child, second record ledger' "$proc" \
    "GAP-TEST ($DEFAULT_LEDGER): $eg gaps, $ek killed claims"
  cases=$((cases + 1))

  # --- THE THREE STATES OF THE SLOT, the whole reason this file stopped naming a section ---------
  # P6 THE RUN-WRITTEN HEADING. `S5T-verify-2.md` R3 measured this exact pair red: a brief whose
  # menu slot carries a heading the run chose renders at `audit()` exit 0 and was failed here, by a
  # message naming a heading the brief deliberately does not carry. The record and the page agree;
  # only the words differ, and the words are the run to choose. The heading below is in NO
  # catalogue, which is what makes the case prove resolution rather than a second literal.
  proc="$tmp/proc-renamed"
  make_proc_root "$proc"
  sed -e "s|^## $FX_THREAT\$|## Where Each Rival Can Hurt You|" "$b" >"$proc/$DEFAULT_BRIEF"
  cp "$l" "$proc/$DEFAULT_LEDGER"
  write_lines "$proc/build/headings.json" \
    '{ "sections": [ { "slot": "threat-landscape", "heading": "Where Each Rival Can Hurt You" } ] }'
  PROC_RC=0
  PROC_OUT="$( BRIEF_ROOT="$proc/build" bash "$proc/tools/gap-test.sh" --check 2>&1 )" || PROC_RC=$?
  if [ "$PROC_RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: a run-written heading was not resolved; exit %s: %s\n' "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *'GAP-TEST-OK (4 checks'*) printf 'SELFTEST proc OK  %-32s -> exit 0, four checks on a renamed section\n' 'child, run-written heading' ;;
    *) printf 'SELFTEST FAIL: a run-written heading did not reach a full grade; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))

  # P7 THE ABSENT SLOT, and it is NOT a failure. A run that took no threat-landscape slot owes no
  # gap ledger for it, so the check says which state it is in and exits 0. The brief here still
  # carries the table -- the RECORD is what decides, and a check that read the page instead would
  # grade it and report four checks on a section this run never allocated.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  cp "$b" "$proc/$DEFAULT_BRIEF"
  cp "$l" "$proc/$DEFAULT_LEDGER"
  write_lines "$proc/build/headings.json" \
    '{ "sections": [ { "slot": "recommendations", "heading": "Recommendations" } ] }'  # heading-literal: the fixture record allocates one slot that is not the one under test
  PROC_RC=0
  PROC_OUT="$( BRIEF_ROOT="$proc/build" bash "$proc/tools/gap-test.sh" --check 2>&1 )" || PROC_RC=$?
  if [ "$PROC_RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: an unallocated slot was a failure; exit %s: %s\n' "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *'GAP-TEST SKIPPED (0 checks): this run'*'no threat-landscape slot'*)
      printf 'SELFTEST proc OK  %-32s -> exit 0, the absent state named\n' 'child, slot not allocated' ;;
    *) printf 'SELFTEST FAIL: the absent state was silent; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *GAP-TEST-OK*) printf 'SELFTEST FAIL: the absent state printed the four-check OK line: %s\n' "$PROC_OUT" >&2
                   return 1 ;;
  esac
  cases=$((cases + 1))

  # P8 NO READABLE RECORD, which is a failure and the third state. A check that cannot find out
  # which section it grades must not report a pass, so this is the fail-closed direction and it
  # names the path it could not read.
  proc="$tmp/proc-norecord"
  make_proc_root "$proc"
  cp "$b" "$proc/$DEFAULT_BRIEF"
  cp "$l" "$proc/$DEFAULT_LEDGER"
  rm -f "$proc/build/headings.json"
  PROC_RC=0
  PROC_OUT="$( BRIEF_ROOT="$proc/build" bash "$proc/tools/gap-test.sh" --check 2>&1 )" || PROC_RC=$?
  if [ "$PROC_RC" -eq 0 ]; then
    printf 'SELFTEST FAIL: a missing allocation record passed; got: %s\n' "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *'FAIL: no readable allocation record at '*'headings.json'*)
      printf 'SELFTEST proc red %-32s -> exit %s, fail-closed on the record\n' 'child, no allocation record' "$PROC_RC" ;;
    *) printf 'SELFTEST FAIL: a missing record went red with the wrong message; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))

  # P9 THE RESOLVER ITSELF MISSING. Sourced code that is absent must stop the script before it
  # grades anything, or a copy of this file taken alone reports a clean run it never performed.
  proc="$tmp/proc-noresolver"
  make_proc_root "$proc"
  cp "$b" "$proc/$DEFAULT_BRIEF"
  cp "$l" "$proc/$DEFAULT_LEDGER"
  rm -f "$proc/tools/slot-heading.sh"
  PROC_RC=0
  PROC_OUT="$( bash "$proc/tools/gap-test.sh" --check 2>&1 )" || PROC_RC=$?
  if [ "$PROC_RC" -ne 2 ]; then
    printf 'SELFTEST FAIL: a missing resolver exited %s, want 2; got: %s\n' "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *'FAIL: no slot resolver at '*) printf 'SELFTEST proc red %-32s -> exit 2, before any grading\n' 'child, no slot resolver' ;;
    *) printf 'SELFTEST FAIL: a missing resolver was silent; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  printf 'SELFTEST OK: %s cases, G1 red on a missing block, an extra block, a duplicate block, a competitor name that is a strict prefix of another in the same table, and a ledger whose blocks run out of the gap table row order, G2 red on each of its twelve sub-rules (no claimed, two claimed, no absence, no killed, a kill with no reason, a reason one line late, killed: none carrying a reason, two killed: none lines, a wrapped field continuation, a tag outside the four, a tag word sitting mid-sentence rather than opening the value, and a tag opening the value inside a longer word) and green on all %s pinned reason tags read from an independent literal with a reverse membership check, G3 red on a state outside rule 4, on a state word sitting mid-sentence, on a state opening the value inside a longer word, and on verified-blocked and unfound with nothing killed, green on verified-absent with nothing killed and on all %s pinned absence states, G4 red on a killed phrase still in the Key Gap cell and on a kill recorded under the SECOND table row, green on a one-word near miss and on a killed phrase that sits in a cell belonging to another row, the gap column located by header text proved in both directions on a table whose gap column sits second, seven fail-closed readings each pinning its own message (absent brief missing, empty brief empty, absent ledger missing, empty ledger, no gap table under the heading the record names, no Key Gap column, no ### block), %s red on all four checks, the exemplar brief and the committed ledger green, CHECKS_RUN derived from execution at 0 on the fail-closed path and 4 on a full grade, 5 child-process cases (clean defaults green with the token and a count of 4, unfalsified default ledger red with no token, absent ledger argument red, and two bare record modes whose gap and kill counts are derived from two fixtures holding different numbers), and the three states of the slot proved end to end in child processes (a run-written heading graded in full, an unallocated slot exiting 0 with the state named and no OK line, an unreadable record failing closed, and a missing resolver exiting 2 before any grading)\n' \
    "$cases" "$ntag" "$nst" "tools/fixtures/unfalsified-gaps.md"
}

# --- main -----------------------------------------------------------------------------------------
main_check() {
  local brief ledger
  cd "$ROOT"
  brief="${1:-$DEFAULT_BRIEF}"
  ledger="${2:-$DEFAULT_LEDGER}"
  check_file "$brief" "$ledger"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  # The absent state, said out loud and exited 0. A silent pass here would be indistinguishable from
  # four clean checks, which is the shape of green this file exists to end.
  if [ -n "$SKIPPED" ]; then
    printf 'GAP-TEST SKIPPED (0 checks): %s\n' "$SKIPPED"
    exit 0
  fi
  printf 'GAP-TEST-OK (%s checks, 0 findings in %s)\n' "$CHECKS_RUN" "$ledger"
}

# main_record prints the falsification record and grades nothing. It still fails closed on a ledger
# it cannot read, so bare mode cannot report a record of nothing.
main_record() {
  local ledger
  cd "$ROOT"
  ledger="${1:-$DEFAULT_LEDGER}"
  if [ ! -e "$ledger" ]; then
    printf 'FAIL: no gap ledger to grade at %s (missing)\n' "$ledger" >&2
    exit 1
  fi
  if [ ! -s "$ledger" ]; then
    printf 'FAIL: no gap ledger to grade at %s (empty)\n' "$ledger" >&2
    exit 1
  fi
  record_lines "$ledger"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  elif [ "${1:-}" = "--check" ]; then
    shift
    main_check "${1:-}" "${2:-}"
  else
    main_record "${1:-}"
  fi
fi
