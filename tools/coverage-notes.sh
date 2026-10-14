#!/usr/bin/env bash
# V32. The Coverage Notes reader-voice lint. It grades ONE markdown brief's `## Coverage Notes`
# section on two checks, collects every finding, and fails closed.
#
# WHY IT EXISTS. `docs/PLAN.md:1244` books the slice "Coverage Notes is written to the reader, not
# about the pipeline": on the shipped shakedown brief the section stopped telling a founder what
# could not be seen and started narrating how the run went -- which rival was "graded below their
# own files", which fetch failed in "both tools" -- and it ran LONGER than the Quick Take while
# doing it. Two checks, one per half of that defect:
#
#   C1  a four-term process-noun blocklist, scoped to `## Coverage Notes`.
#   C2  Coverage Notes must be STRICTLY shorter, in prose words, than `## Quick Take`.
#
# The written standard these two checks hold the mechanical half of is `### Coverage Notes is
# written to the reader` in `references/briefing-template.md`, cited by heading and not by line
# because line numbers there move; its own source is register check 5, `docs/history/review/
# 08-register.md`.
#
# C1 COUNTS OFFENDING LINES, NOT TERM HITS, and that is load-bearing rather than a detail of
# reporting. On the shakedown brief the phrase "graded below their own files" carries TWO of the four
# terms in one span, so a per-term count reports 3 findings where `docs/PLAN.md:1244` records 2. The
# per-line count reproduces PLAN's 2. When one line matches more than one term the line is reported
# ONCE and every term it matched is named, in table order.
#
# C2'S COUNTING METHOD IS PINNED HERE, because the numbers below are only reproducible against a
# stated method. Within the section: drop table rows (`^[[:space:]]*|`), strip a leading heading
# marker (`^[[:space:]]*#+`) and keep the words after it, replace `[text](url)` with `text`, delete
# bare `https?://...` runs, strip `*`, `_`, backtick and a leading `>`, then count
# whitespace-delimited words. Six clauses, and the selftest measures the count directly for each.
#
# CALIBRATION, measured 2026-09-11 and reproduced by the selftest below on both committed briefs:
#
#                                        exemplar          shipped shakedown
#                                        build/briefing.md output/research/initech-shakedown/...
#   C1 offending lines                   0                 2  (:93 and :97)
#   Coverage Notes prose words           93                147
#   Quick Take prose words               166               143
#   C2                                   green (56%)       RED (147 against 143)
#
# SECTION SCOPE. Enter on the `## <name>` heading; a later `#` or `##` heading ENDS the section; a
# deeper heading (`###` and below) inside the section does NOT end it and IS GRADED -- C1 reads its
# text, C2 counts its words with the marker stripped. Only the section's own `##` heading line is
# dropped. `tools/gap-test.sh:157-187` is the precedent for awk-scoping to one named `##` section and
# it exits on ANY heading; this script diverges on the deeper case alone, and it has to, twice over:
# C2's method above only means anything if a heading can sit inside the section, and dropping the
# deeper heading from the GRADE opened an escape MEASURED 2026-09-11 -- a Coverage Notes section
# whose only two lines are `###` headings, carrying all four blocklist terms and 18 prose words,
# exited 0. A grader that stops reading at one extra `#` is one keystroke away from grading nothing.
#
# It collects every finding and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is.
#
# `grep` is wrapped to `ugrep` on this machine, where a pattern starting with `--` parses as an
# option, so every pattern below is passed after `-e`.
#
# HONEST LIMITS, named here rather than left for a reader to discover:
#
#   - THE BLOCKLIST IS A WORD LIST AND THE DEFECT IS A JUDGEMENT. C1 catches the two phrasings
#     measured on the shakedown brief and it will not catch the next one. The residue is not covered
#     here and is not meant to be: it belongs to the register review pass, `docs/history/review/
#     08-register.md` check 5, which reads the section and asks whether a founder is being told what
#     could not be seen or being told how the run went.
#   - C2 IS THE NARROW CATCH AND C1 THE WIDE ONE. C2's margin on the shakedown is FOUR WORDS
#     (147 against 143). A brief that trims one sentence walks past C2 with the same voice intact,
#     which is exactly why C1 exists alongside it.
#   - THE RATIO FORM IS WHAT LANDED; THE SHARE FORM DID NOT. `docs/PLAN.md:1244` also offers the
#     budget as "Coverage Notes may not exceed the exemplar's section share". That form is NOT
#     implemented: PLAN names no denominator, and the denominator is the whole rule. Under the
#     method pinned above, which drops table rows outright, the exemplar's whole-brief prose is 640
#     words and its Coverage Notes 93, or 14.5%; a tables-included figure is not computable at all.
#     The ratio against Quick Take is what V32's `the operator opens` line states and needs no denominator.
#   - THE TWO CHECKS READ TABLE ROWS DIFFERENTLY, DELIBERATELY. C1 grades EVERY non-heading line of
#     the section, a table row included, because `references/briefing-template.md` gives Coverage
#     Notes prose only, so a table row there is already off-template and process language hidden in
#     one should still red. C2's word count EXCLUDES table rows, because a cell is not a sentence and
#     counting cells would make the budget a function of table width. The asymmetry is intended.
#
# ONE PROPOSED TERM WAS MEASURED BACK OUT OF THE BLOCKLIST, recorded here with the words that forced
# it rather than dropped silently -- the discipline `tools/ai-smell.sh:28-40` and `tools/scan-layer.
# sh` exclusion 1 keep:
#
#   - "THE RESEARCH", proposed as a fifth term, REMOVED 2026-09-11, for two reasons either of which
#     is enough on its own. IT WAS UNMEASURED: `grep -ic research` returns 0 on `build/briefing.md`
#     and 0 on `output/research/initech-shakedown/artefacts/briefing-initech-shakedown.md`, so unlike
#     the four above it was never seen in a brief at all, and its only evidence was the fixture line
#     this slice wrote for it. AND IT REDS MANDATED CONTENT: `references/briefing-template.md:81-83`
#     requires Coverage Notes to carry "research this run gathered and did not use, named with what
#     it measured", so "The research this run gathered on Zaigo was not used, because it sells to US
#     sponsors." obeys the template and would red C1. A check that reds what the template mandates is
#     dropped here, the same ruling `tools/scan-layer.sh` made when grading every table column red
#     the exemplar 12 times. REMOVING IT MOVED NO CALIBRATION NUMBER ABOVE, because it matched
#     nothing in either brief: C1 stays 0 on the exemplar and 2 on the shakedown, at :93 and :97.
#
# PRECONDITION: none beyond the target file existing. No network, no MKT1 call, no env var, no build
# artefact, no run directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_TARGET="build/briefing.md"

# THE TWO SECTIONS ARE RESOLVED, NOT NAMED. Both are SPINE slots, so a run may not rename either --
# and `S5T-fix.md` instance 2 makes the argument that matters anyway: the spine heading is fixed by
# the CATALOGUE DEFAULT, and that default is editable. One coordinated edit to
# `references/headings.json`, `references/briefing-template.md`, the run record and the page renames
# a spine section legitimately, and the literal left behind here does not fail loudly -- it grades a
# section that is not there. `S5T-verify-2.md` measured exactly that: on such a rename this file
# exited 1 with `no '## Coverage Notes' heading ... (nothing to grade)` against a brief
# `python3 build/build.py` had just passed. Resolving through the record is the same seam
# `build/build.py:slot_html()` uses, and `tools/headings-check.sh` gates the whole repository
# against the literal coming back.
if [ ! -f "$ROOT/tools/slot-heading.sh" ]; then
  printf 'FAIL: no slot resolver at %s/tools/slot-heading.sh\n' "$ROOT" >&2
  exit 2
fi
# shellcheck source=tools/slot-heading.sh
. "$ROOT/tools/slot-heading.sh"

# Resolved once, at load, because every path through this file needs both. A spine slot missing from
# the record, or a record that cannot be read at all, is a FAIL-CLOSED exit and never a grade: a
# check that cannot find its subject must not report a pass.
resolve_section() {
  local slot="$1" what="$2" out rc=0
  out="$(slot_heading "$slot")" || rc=$?
  if [ "$rc" -eq 1 ]; then
    printf 'FAIL: the allocation record at %s carries no %s slot, so there is no %s to grade\n' \
      "$(slot_heading_record)" "$slot" "$what" >&2
    exit 2
  fi
  if [ "$rc" -ne 0 ]; then
    printf 'FAIL: no readable allocation record at %s; this check cannot know which section to grade\n' \
      "$(slot_heading_record)" >&2
    exit 2
  fi
  printf '%s\n' "$out"
}
GRADED_SECTION="$(resolve_section coverage-notes 'the graded section')"
BUDGET_SECTION="$(resolve_section quick-take 'the budget section')"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

# CHECKS_RUN is DERIVED FROM EXECUTION and never hardcoded. Interpolating it into the success line
# does NOT on its own earn the claim that the line cannot report two checks while one ran -- MEASURED
# 2026-09-11, replacing `"$CHECKS_RUN"` there with a literal `2` leaves `--selftest` at exit 0,
# because `main()` reaches that line only when FAILS is empty and an empty FAILS already implies both
# checks ran. So the claim is made true by an ASSERTION in `main()` instead: anything other than two
# checks is itself a finding, with its own message, and the selftest proves that arm red on a child
# copy whose first increment is deleted. Same counter as `tools/score-check.sh`, `tools/gap-test.sh`
# and `tools/scan-layer.sh`, and the selftest also asserts it at 0 on the fail-closed path and 2 on a
# full grade.
CHECKS_RUN=0

# The field separator of the awk streams below, named so no expansion in this file has to carry an
# invisible literal tab.
TAB=$'\t'

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# --- the blocklist --------------------------------------------------------------------------------
# Four terms, one per line, matched as literal substrings and case-insensitively. Exactly these four
# and no others: each one was MEASURED on the shipped shakedown brief or is the immediate inflection
# of one that was ("downgraded from" is "graded below" in the past tense). A fifth was proposed and
# measured back out; the header above records it and why. They are literal phrases and not regexes,
# which is why the match below is awk's `index(tolower(...))` and not a `grep -E` pass: the finding
# has to name EVERY term a line matched, and a per-term grep cannot report two terms as one line
# without a second reconciliation pass.
TERMS="their own files
both tools
graded below
downgraded from"

term_count() {
  # Counted from the list rather than written down, for the same reason CHECKS_RUN is.
  printf '%s\n' "$TERMS" | grep -c -e '^[a-z]' || true
}

# awk's `-v` REJECTS a newline inside the value -- MEASURED on `awk version 20200816`, the BWK awk
# this machine ships: `awk: newline in string ... at source line 1`, exit non-zero. So the list is
# handed over `~`-delimited. `~` is safe because no term contains one, the same reasoning that picked
# the delimiter for the rule table in `tools/ai-smell.sh`.
terms_packed() {
  printf '%s' "$TERMS" | tr '\n' '~'
}

# --- section scoping ------------------------------------------------------------------------------
# section_body prints `NR<TAB>text` for every non-heading line of one named `##` section, so both
# checks read ONE state machine and a scope fix cannot land in one check and miss the other. The tab
# carries the SOURCE line number, which is what lets a C1 finding cite `$f:$ln`.
section_body() {
  local sec="$1" f="$2"
  awk -v SEC="$sec" '
    # Enter on the section heading itself. `##` exactly: the `[[:space:]]+` after it cannot match a
    # third `#`, so `### Coverage Notes` does not open the section.
    $0 ~ ("^[[:space:]]*##[[:space:]]+" SEC "[[:space:]]*$") { ins = 1; next }
    # Any other h1 or h2 closes it. This is the boundary V32 states: the section ends at the next
    # `## ` heading.
    /^[[:space:]]*##?[[:space:]]/ { ins = 0; next }
    !ins { next }
    # A deeper heading inside the section is NOT dropped: it continues the section AND it is graded,
    # because a section written entirely as `###` headings is still a section a founder reads.
    { printf "%d\t%s\n", NR, $0 }
  ' "$f"
}

section_present() {
  # Counts the `## <name>` headings in the file. Zero is a FAILURE upstream, never a vacuous pass.
  local sec="$1" f="$2"
  awk -v SEC="$sec" '
    $0 ~ ("^[[:space:]]*##[[:space:]]+" SEC "[[:space:]]*$") { n++ }
    END { print n + 0 }
  ' "$f"
}

# --- C2: the word count ---------------------------------------------------------------------------
# prose_words prints ONE integer: the prose words of one named section under the method pinned at the
# head of this file. Implemented over section_body's stream, so it inherits the same scope.
prose_words() {
  local sec="$1" f="$2"
  section_body "$sec" "$f" | awk '
    {
      line = $0
      sub(/^[0-9]+\t/, "", line)            # drop the line-number prefix section_body added

      if (line ~ /^[[:space:]]*\|/) next    # a table row is not prose; see the header comment

      # A `###` marker is markup, not a word, but the words after it are prose and are counted. The
      # `##` heading that opens this section never reaches here: section_body consumes it.
      sub(/^[[:space:]]*#+[[:space:]]*/, "", line)

      # `[text](url)` -> `text`. The replacement is always shorter than the match, so the loop
      # terminates even on an empty link text.
      while (match(line, /\[[^]]*\]\([^)]*\)/)) {
        m = substr(line, RSTART, RLENGTH)
        b = index(m, "](")
        txt = substr(m, 2, b - 2)
        line = substr(line, 1, RSTART - 1) txt substr(line, RSTART + RLENGTH)
      }

      gsub(/https?:\/\/[^ \t]*/, "", line)  # a bare URL is an address, not a word
      gsub(/[*_`]/, "", line)               # emphasis and code markers are not words
      sub(/^[[:space:]]*>+[[:space:]]*/, "", line)   # a blockquote marker is not a word

      n += split(line, a, " ")              # " " as FS ignores leading, trailing and repeated space
    }
    END { print n + 0 }
  '
}

# --- the check ------------------------------------------------------------------------------------
# check_file populates FAILS for one target path and ALWAYS returns 0; the caller decides. Same
# contract as `check_file` in `tools/ai-smell.sh` and `tools/thesis-check.sh`, and it is what lets
# the selftest run every case in this shell without `set -e` ending the run at the first red.
check_file() {
  local f="$1" hits h ln terms text oldifs cn qt

  FAILS=""
  CHECKS_RUN=0

  # FOUR FAIL-CLOSED READINGS, each with its own message, and every check skipped when one fires. A
  # lint that reports two clean checks on a file that does not exist, or on a brief with no Coverage
  # Notes at all, is precisely the shape of green this repository treats as a lie.
  if [ ! -e "$f" ]; then
    add_fail "FAIL: no brief to grade at $f (no such file)"
    return 0
  fi
  if [ ! -s "$f" ]; then
    add_fail "FAIL: no brief to grade at $f (empty file)"
    return 0
  fi

  # Both heading failures are collected before returning, so a fragment missing both is told both
  # times rather than being sent back twice.
  if [ "$(section_present "$GRADED_SECTION" "$f")" -eq 0 ]; then
    add_fail "FAIL: no '## $GRADED_SECTION' heading in $f (nothing to grade)"
  fi
  if [ "$(section_present "$BUDGET_SECTION" "$f")" -eq 0 ]; then
    add_fail "FAIL: no '## $BUDGET_SECTION' heading in $f (no budget to grade against)"
  fi
  [ -z "$FAILS" ] || return 0

  # --- C1 -----------------------------------------------------------------------------------------
  # One finding per offending LINE. Every term the line matched is named, in the order of the list
  # above, which is why the whole list is tested against every line rather than short-circuiting on
  # the first hit.
  hits="$(section_body "$GRADED_SECTION" "$f" | awk -v TERMS="$(terms_packed)" '
    BEGIN { nt = split(TERMS, T, "~") }
    {
      line = $0
      sub(/^[0-9]+\t/, "", line)
      low = tolower(line)
      matched = ""
      for (i = 1; i <= nt; i++) {
        if (T[i] == "") continue
        if (index(low, tolower(T[i])) > 0) {
          matched = (matched == "" ? "\"" T[i] "\"" : matched ", \"" T[i] "\"")
        }
      }
      if (matched != "") {
        ln = $0
        sub(/\t.*$/, "", ln)
        printf "%s\t%s\t%s\n", ln, matched, line
      }
    }
  ')"
  CHECKS_RUN=$((CHECKS_RUN + 1))

  if [ -n "$hits" ]; then
    # Split on newlines only, with globbing OFF: a claim-header line carries `**`, and an unguarded
    # word split would let the shell expand it against the working directory. The three fields are
    # tab-separated, and the tab is named through `$TAB` rather than typed literally into the
    # expansions below, where an invisible character is a latent edit hazard.
    oldifs="$IFS"
    set -f
    IFS=$'\n'
    for h in $hits; do
      ln="${h%%"$TAB"*}"
      text="${h#*"$TAB"}"
      terms="${text%%"$TAB"*}"
      text="${text#*"$TAB"}"
      add_fail "FAIL: C1 process language in $GRADED_SECTION at $f:$ln: matched $terms -- $text"
    done
    IFS="$oldifs"
    set +f
  fi

  # --- C2 -----------------------------------------------------------------------------------------
  # STRICTLY shorter. Equal is red: a Coverage Notes section the length of the Quick Take has stopped
  # being a caveat and become a second brief.
  cn="$(prose_words "$GRADED_SECTION" "$f")"
  qt="$(prose_words "$BUDGET_SECTION" "$f")"
  CHECKS_RUN=$((CHECKS_RUN + 1))

  if [ "$cn" -ge "$qt" ]; then
    add_fail "FAIL: C2 $GRADED_SECTION is not shorter than $BUDGET_SECTION in $f: $cn words against $qt"
  fi

  return 0
}

# --- selftest -------------------------------------------------------------------------------------
# Proves each of the four terms red on its own, proves the per-line aggregation on a line carrying
# two of them, proves the section boundary in both directions, proves that a `###` heading inside the
# section is graded and does not end it, proves C2 at one word under, at equal and at one word over,
# proves each clause of the counting method by measuring the count directly, proves the check-count
# assertion red on a mutated child, reproduces all six calibration numbers on the two committed
# briefs, and leaves no residue. A check that has never gone red is an untested assertion.

# write_lines writes a file from its remaining arguments, one line each. `: >"$f"` then `printf`,
# because `docs/DESIGN.md` bans heredoc writes in this repository.
write_lines() {
  local f="$1" line
  shift
  : >"$f"
  for line in "$@"; do
    printf '%s\n' "$line" >>"$f"
  done
}

# write_brief builds a minimal four-section brief:
#   1 `# Competitor Intel Briefing`
#   3 `## Quick Take`      5 QT_LINE
#   7 `## Coverage Notes`  9.. the CN lines
#   then `## Sources` and AFTER_LINE
# The fixed geometry is what lets a case assert a LINE NUMBER: the first Coverage Notes line is
# always line 9. AFTER_LINE exists so the scope cases can plant a term in the section immediately
# after the graded one.
# The section the fixture writes AFTER the graded one, so a scope case can plant a term in it. Named
# here, once, and labelled: a fixture brief carries headings, and this is the only literal one in
# this file.
FX_AFTER="Sources"  # heading-literal: the fixture brief needs a section after the graded one

write_brief() {
  local f="$1" qt="$2" after="$3" line
  shift 3
  : >"$f"
  printf '%s\n' '# Competitor Intel Briefing' '' "## $BUDGET_SECTION" '' "$qt" '' \
    "## $GRADED_SECTION" '' >>"$f"
  for line in "$@"; do
    printf '%s\n' "$line" >>"$f"
  done
  printf '%s\n' '' "## $FX_AFTER" '' "$after" >>"$f"
}

expect_red() {
  local label="$1" f="$2" want="$3"
  check_file "$f"
  case "$FAILS" in
    *"$want"*) printf 'SELFTEST red OK   %-30s -> %s' "$label" "$FAILS" ;;
    *) printf 'SELFTEST FAIL: %s did not go red on %s; got: %s\n' \
         "$label" "$want" "${FAILS:-<no findings>}" >&2
       return 1 ;;
  esac
}

expect_green() {
  local label="$1" f="$2"
  check_file "$f"
  if [ -n "$FAILS" ]; then
    printf 'SELFTEST FAIL: %s went red; got: %s\n' "$label" "$FAILS" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-30s -> no findings\n' "$label"
}

# expect_findings pins the COUNT of findings as well as their content, which is the only way to prove
# the per-line rule: a per-term implementation reds the same fixture with a different count. The
# optional fourth argument narrows the count to one check, so C1's count can be pinned without C2's
# verdict moving it.
expect_findings() {
  local label="$1" f="$2" want="$3" pat="${4:-^FAIL:}" got
  check_file "$f"
  got="$(printf '%s' "$FAILS" | grep -c -e "$pat" || true)"
  if [ "$got" != "$want" ]; then
    printf 'SELFTEST FAIL: %s reported %s findings matching %s, want %s; got: %s\n' \
      "$label" "$got" "$pat" "$want" "${FAILS:-<no findings>}" >&2
    return 1
  fi
  printf 'SELFTEST count OK %-30s -> %s findings\n' "$label" "$got"
}

# expect_words measures the word count directly, so each clause of the counting method is proved by
# the number it produces and not by the pass/fail it happens to cause.
expect_words() {
  local label="$1" sec="$2" f="$3" want="$4" got
  got="$(prose_words "$sec" "$f")"
  if [ "$got" != "$want" ]; then
    printf 'SELFTEST FAIL: %s counted %s words in %s, want %s\n' "$label" "$got" "$sec" "$want" >&2
    return 1
  fi
  printf 'SELFTEST words OK %-30s -> %s words in %s\n' "$label" "$got" "$sec"
}

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main()`, its `cd "$ROOT"`, the default target,
# the argument dispatch, the COVERAGE-NOTES-OK line and the non-zero exit would be exercised by
# nothing. That gap is load-bearing and not hypothetical: inside `OUT="$( (f) 2>&1 )"` bash suspends
# `set -e`, so an in-process case cannot see an abort at all, and it was `main()` on the real corpus
# that killed `tools/known-traps.sh` while its twelve in-process cases stayed green. The cases below
# copy this script into a fixture root and run it as a CHILD with its own fully armed
# `set -euo pipefail`, which is the invocation a run actually makes.
PROC_RC=0
PROC_OUT=""

make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/build"
  cp "${BASH_SOURCE[0]}" "$root/tools/coverage-notes.sh"
  # The resolver and an allocation record travel with the script: a child that cannot resolve its
  # two sections exits 2 before grading anything, which P6 and P7 below assert on purpose.
  cp "$ROOT/tools/slot-heading.sh" "$root/tools/slot-heading.sh"
  write_lines "$root/build/headings.json" \
    "{ \"sections\": [ { \"slot\": \"quick-take\", \"heading\": \"$BUDGET_SECTION\" }," \
    "                  { \"slot\": \"coverage-notes\", \"heading\": \"$GRADED_SECTION\" } ] }"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/coverage-notes.sh" "$@" 2>&1 )" || PROC_RC=$?
  return 0
}

expect_proc_green() {
  local label="$1" root="$2" want="$3"
  run_proc "$root"
  if [ "$PROC_RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: %s exited %s, want 0; got: %s\n' "$label" "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *"$want"*) printf 'SELFTEST proc OK  %-30s -> exit 0, %s\n' "$label" "$PROC_OUT" ;;
    *) printf 'SELFTEST FAIL: %s was green but did not print %s; got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# expect_proc_red asserts the exit code AND the message AND the absence of the success token. A
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
    *COVERAGE-NOTES-OK*)
      printf 'SELFTEST FAIL: a red child run printed COVERAGE-NOTES-OK: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  printf 'SELFTEST proc red %-30s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp cases=0 fixture shakedown proc term nterms

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/coverage-notes-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # The prose used by the synthetic cases. QT13 is the budget every case below is measured against;
  # each CN line is shorter than it unless the case is about length.
  local qt13='The vendor ships payroll to forty finance teams across Iberia and Portugal today.'
  local clean='The vendor ships payroll.'
  local after='Corveo pricing page, fetched on 4 May 2026.'

  # THE EXEMPLAR ASSERTION, and the one that must never be weakened to reach green. If
  # `build/briefing.md` goes red here, the finding is the answer: report it and stop. Editing the
  # blocklist or the budget until the accepted brief passes would leave a lint that runs backwards
  # against the artefact it was calibrated on.
  expect_green "exemplar $DEFAULT_TARGET" "$ROOT/$DEFAULT_TARGET"
  cases=$((cases + 1))

  # The exemplar's two calibration numbers, measured directly rather than inferred from the green
  # above: 93 of 166 is a 56% section, a margin of 73 words.
  expect_words "exemplar $GRADED_SECTION" "$GRADED_SECTION" "$ROOT/$DEFAULT_TARGET" 93
  expect_words "exemplar $BUDGET_SECTION" "$BUDGET_SECTION" "$ROOT/$DEFAULT_TARGET" 166
  cases=$((cases + 1))

  # THE SHIPPED SHAKEDOWN BRIEF, which is the artefact V32 was measured on and the reason both checks
  # exist. C1 must report EXACTLY TWO findings -- the per-line count; a per-term implementation says
  # three here -- at the two pinned line numbers, and C2 must report 147 against 143.
  shakedown="$ROOT/output/research/initech-shakedown/artefacts/briefing-initech-shakedown.md"
  if [ ! -s "$shakedown" ]; then
    printf 'SELFTEST FAIL: no shipped shakedown brief at %s\n' "$shakedown" >&2
    return 1
  fi
  expect_words "shakedown $GRADED_SECTION" "$GRADED_SECTION" "$shakedown" 147
  expect_words "shakedown $BUDGET_SECTION" "$BUDGET_SECTION" "$shakedown" 143
  expect_red 'shakedown C1 line 93' "$shakedown" "FAIL: C1 process language in $GRADED_SECTION at $shakedown:93: matched \"their own files\", \"graded below\""
  expect_red 'shakedown C1 line 97' "$shakedown" "FAIL: C1 process language in $GRADED_SECTION at $shakedown:97: matched \"both tools\""
  expect_red 'shakedown C2 147 vs 143' "$shakedown" "FAIL: C2 $GRADED_SECTION is not shorter than $BUDGET_SECTION in $shakedown: 147 words against 143"
  expect_findings 'shakedown C1 per LINE' "$shakedown" 2 '^FAIL: C1'
  cases=$((cases + 1))

  # The synthetic red artefact. It is authored elsewhere: if it is absent, say so by path and fail,
  # rather than stubbing it here and grading this script against its own idea of pipeline voice.
  fixture="$ROOT/tools/fixtures/pipeline-voiced-coverage.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no pipeline-voiced red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  expect_red 'fixture C1' "$fixture" 'FAIL: C1 process language'
  expect_red 'fixture C2' "$fixture" "FAIL: C2 $GRADED_SECTION is not shorter"
  # THE FIXTURE'S OWN HEADER CLAIM, asserted rather than left as prose: three C1 lines, one per term
  # with a single line carrying two at once. The two substrings above pass on ANY red, so without
  # this count the fixture could lose a trigger line and nothing here would notice -- and neither
  # would its two deliberate scope decoys, a term in Quick Take and a term in the section after
  # Coverage Notes, which are proved not to fire by the count staying at three.
  expect_findings 'fixture C1 per line' "$fixture" 3 '^FAIL: C1'
  cases=$((cases + 1))

  # T1..T4: each term red ON ITS OWN, one term per fixture, so a red case proves that term and not
  # the scaffolding. Every CN line here is shorter than qt13, so C2 stays green and the finding
  # cannot be C2 wearing C1's name.
  write_brief "$tmp/t1.md" "$qt13" "$after" 'Two rivals sit above their own files on the grid.'
  expect_red 'T1 their own files' "$tmp/t1.md" "at $tmp/t1.md:9: matched \"their own files\""
  expect_findings 'T1 alone' "$tmp/t1.md" 1
  cases=$((cases + 1))

  write_brief "$tmp/t2.md" "$qt13" "$after" 'Two suppliers returned an error to both tools today.'
  expect_red 'T2 both tools' "$tmp/t2.md" "at $tmp/t2.md:9: matched \"both tools\""
  expect_findings 'T2 alone' "$tmp/t2.md" 1
  cases=$((cases + 1))

  write_brief "$tmp/t3.md" "$qt13" "$after" 'One rival is graded below the tier it claims.'
  expect_red 'T3 graded below' "$tmp/t3.md" "at $tmp/t3.md:9: matched \"graded below\""
  expect_findings 'T3 alone' "$tmp/t3.md" 1
  cases=$((cases + 1))

  write_brief "$tmp/t4.md" "$qt13" "$after" 'The newcomer was downgraded from the top tier.'
  expect_red 'T4 downgraded from' "$tmp/t4.md" "at $tmp/t4.md:9: matched \"downgraded from\""
  expect_findings 'T4 alone' "$tmp/t4.md" 1
  cases=$((cases + 1))

  # THE PER-LINE RULE at its minimum: one line, two terms, ONE finding naming both, in list order.
  # `expect_findings ... 1` is the half that fails under a per-term implementation.
  write_brief "$tmp/two-terms.md" "$qt13" "$after" \
    'Two rivals are graded below their own files on the grid.'
  expect_red 'two terms, one line' "$tmp/two-terms.md" \
    "at $tmp/two-terms.md:9: matched \"their own files\", \"graded below\""
  expect_findings 'two terms, one finding' "$tmp/two-terms.md" 1
  cases=$((cases + 1))

  # Case-insensitivity, on the term whose natural spelling opens a sentence.
  write_brief "$tmp/case.md" "$qt13" "$after" 'Both Tools returned an error at the same hour.'
  expect_red 'case-insensitive Both Tools' "$tmp/case.md" "at $tmp/case.md:9: matched \"both tools\""
  cases=$((cases + 1))

  # SCOPE, term by term, in BOTH directions that matter: the same four phrases in the section BEFORE
  # the graded one and in the section immediately AFTER it are green. Without these eight cases the
  # scoping could be deleted outright and every case above would still pass.
  # The list is walked with IFS set to newline for the EXPANSION only; the `for` list is expanded
  # once at loop entry, so IFS is restored on the first line of the body and the cases below run
  # under the normal separator.
  local i=0
  local oldifs2="$IFS"
  IFS=$'\n'
  for term in $TERMS; do
    IFS="$oldifs2"
    i=$((i + 1))
    write_brief "$tmp/scope-qt-$i.md" "The desk reviewed $term before the call and moved on." \
      "$after" "$clean"
    expect_green "scope: '$term' in $BUDGET_SECTION" "$tmp/scope-qt-$i.md"
    cases=$((cases + 1))

    write_brief "$tmp/scope-after-$i.md" "$qt13" "The desk reviewed $term before the call." "$clean"
    expect_green "scope: '$term' after section" "$tmp/scope-after-$i.md"
    cases=$((cases + 1))
  done
  IFS="$oldifs2"
  nterms="$i"
  if [ "$nterms" -ne "$(term_count)" ]; then
    printf 'SELFTEST FAIL: scope cases covered %s terms, list holds %s\n' "$nterms" "$(term_count)" >&2
    return 1
  fi

  # C2 AT THE BOUNDARY, with no blocklist term anywhere: one word under is green, EQUAL IS RED, one
  # word over is red. Each red pins both counts, so the boundary is proved by the numbers and not by
  # the verdict alone.
  write_brief "$tmp/c2-under.md" "$qt13" "$after" \
    'The vendor ships payroll to forty finance teams across Iberia and Portugal.'
  expect_words "C2 under, $GRADED_SECTION" "$GRADED_SECTION" "$tmp/c2-under.md" 12
  expect_green 'C2 one word under' "$tmp/c2-under.md"
  cases=$((cases + 1))

  write_brief "$tmp/c2-equal.md" "$qt13" "$after" "$qt13"
  expect_red 'C2 equal is red' "$tmp/c2-equal.md" \
    "in $tmp/c2-equal.md: 13 words against 13"
  cases=$((cases + 1))

  write_brief "$tmp/c2-over.md" "$qt13" "$after" \
    'The vendor ships payroll to forty finance teams across Iberia and Portugal this quarter.'
  expect_red 'C2 one word over' "$tmp/c2-over.md" \
    "in $tmp/c2-over.md: 14 words against 13"
  cases=$((cases + 1))

  # THE COUNTING METHOD, at least one case per clause and each measured directly, so the number is
  # the clause under test and nothing else: delete the clause and the count moves and the case fails
  # on the NUMBER, not on a verdict that might have come from anywhere. Six clauses -- the table-row
  # drop, the heading marker, the link substitution, the bare-URL strip, the markup strip and the
  # blockquote strip -- and where a clause's natural shape is count-neutral it is pinned as a pair,
  # the real shape first and the discriminating shape second. Most fixtures below hold the same
  # 12-word prose line so the arithmetic is the same everywhere; the heading case says where it does
  # not and why.
  write_brief "$tmp/count-table.md" "$qt13" "$after" \
    'The vendor ships payroll to forty finance teams across Iberia and Portugal.' \
    '' \
    '| Company | What it means and the action it forces on the reader today | Act |'
  expect_words 'a table row counts nothing' "$GRADED_SECTION" "$tmp/count-table.md" 12
  expect_green 'a table row keeps C2 green' "$tmp/count-table.md"
  cases=$((cases + 1))

  # THE DEEPER HEADING, where ONE number proves both halves of the scope rule: the heading's five
  # words plus the four of the line under it. Strip the words out with the marker and this reads 4;
  # end the section at the `###` and it reads 0. This fixture carries a shorter prose line than its
  # siblings above deliberately, so the heading's words fit under the budget and C2 stays green.
  write_brief "$tmp/count-heading.md" "$qt13" "$after" \
    '### What could not be seen' \
    '' \
    "$clean"
  expect_words 'a heading counts its words' "$GRADED_SECTION" "$tmp/count-heading.md" 9
  expect_green 'a heading keeps C2 green' "$tmp/count-heading.md"
  cases=$((cases + 1))

  # THE `###` ESCAPE, which is why the deeper heading is graded at all: a Coverage Notes section
  # whose ONLY two lines are `###` headings, carrying all four terms and 18 prose words. MEASURED
  # 2026-09-11 against the version that dropped deeper headings, it exited 0 on both checks. Both
  # lines must now red C1 by line number, and the words the headings carry must red C2.
  write_brief "$tmp/escape-headings.md" "$qt13" "$after" \
    '### Two rivals are graded below their own files today' \
    '### Both tools downgraded from the top tier this week'
  expect_red 'escape: heading line 9' "$tmp/escape-headings.md" \
    "at $tmp/escape-headings.md:9: matched \"their own files\", \"graded below\""
  expect_red 'escape: heading line 10' "$tmp/escape-headings.md" \
    "at $tmp/escape-headings.md:10: matched \"both tools\", \"downgraded from\""
  expect_red 'escape: C2 18 against 13' "$tmp/escape-headings.md" \
    "in $tmp/escape-headings.md: 18 words against 13"
  expect_findings 'escape: C1 on both headings' "$tmp/escape-headings.md" 2 '^FAIL: C1'
  cases=$((cases + 1))

  # The link pair. The PLAIN `[text](url)` form is the shape both real briefs use and it is what the
  # first case pins -- but MEASURED 2026-09-11, that form is COUNT-NEUTRAL: with the link
  # substitution deleted the bare-URL strip leaves `grid](` as one token where `grid` stood, and the
  # line counts 7 either way. So the first case alone would be an equivalent mutant, and the second
  # is what discriminates: a link TITLE sits outside the URL's `\S+` run, so the unreplaced form
  # counts 11 against the replaced form's 7.
  write_brief "$tmp/count-link.md" "$qt13" "$after" \
    'See the [practices grid](https://www.example-vendor.test/grid/page) for the detail.'
  expect_words 'a link counts its text only' "$GRADED_SECTION" "$tmp/count-link.md" 7
  cases=$((cases + 1))

  write_brief "$tmp/count-link-title.md" "$qt13" "$after" \
    'See the [practices grid](https://www.example-vendor.test/grid/page "The vendor grid page") for the detail.'
  expect_words 'a link title counts nothing' "$GRADED_SECTION" "$tmp/count-link-title.md" 7
  cases=$((cases + 1))

  write_brief "$tmp/count-url.md" "$qt13" "$after" \
    'See https://www.example-vendor.test/grid/page for the detail.'
  expect_words 'a bare URL counts nothing' "$GRADED_SECTION" "$tmp/count-url.md" 4
  cases=$((cases + 1))

  # The blockquote marker, on the same 12-word line: `>` followed by a space is a token of its own,
  # so with the strip deleted this counts 13.
  write_brief "$tmp/count-quote.md" "$qt13" "$after" \
    '> The vendor ships payroll to forty finance teams across Iberia and Portugal.'
  expect_words 'a blockquote marker counts nothing' "$GRADED_SECTION" "$tmp/count-quote.md" 12
  cases=$((cases + 1))

  # The emphasis pair, and it needs to be a pair for the same reason the link pair does. MEASURED
  # 2026-09-11: an emphasised span GLUED to its words, which is the only form either real brief uses,
  # is COUNT-NEUTRAL -- `*payroll*` is one token whether or not the markers are stripped, so that
  # case alone is an equivalent mutant. It is pinned first because it is the real shape. The case
  # that discriminates is a marker standing as its own token, which in markdown is an asterisk
  # bullet: strip it and the line counts 12, leave it and the `*` counts 13.
  write_brief "$tmp/count-emph.md" "$qt13" "$after" \
    'The vendor ships *payroll* to forty finance teams across _Iberia_ and Portugal.'
  expect_words 'an emphasised span counts once' "$GRADED_SECTION" "$tmp/count-emph.md" 12
  cases=$((cases + 1))

  write_brief "$tmp/count-emph-marker.md" "$qt13" "$after" \
    '* The vendor ships payroll to forty finance teams across Iberia and Portugal.'
  expect_words 'a lone marker counts nothing' "$GRADED_SECTION" "$tmp/count-emph-marker.md" 12
  cases=$((cases + 1))

  # THE FOUR FAIL-CLOSED READINGS, each as a CHILD PROCESS and each pinning its own message. Without
  # these the whole script could be pointed at nothing, or at a brief with no Coverage Notes at all,
  # and report two clean checks.
  proc="$tmp/proc-missing"
  make_proc_root "$proc"
  expect_proc_red 'child, missing default target' "$proc" \
    "FAIL: no brief to grade at $DEFAULT_TARGET (no such file)"
  cases=$((cases + 1))

  proc="$tmp/proc-empty"
  make_proc_root "$proc"
  : >"$proc/$DEFAULT_TARGET"
  expect_proc_red 'child, empty default target' "$proc" \
    "FAIL: no brief to grade at $DEFAULT_TARGET (empty file)"
  cases=$((cases + 1))

  proc="$tmp/proc-no-cn"
  make_proc_root "$proc"
  write_lines "$proc/$DEFAULT_TARGET" '# Competitor Intel Briefing' '' "## $BUDGET_SECTION" '' \
    "$qt13"
  expect_proc_red "child, no $GRADED_SECTION" "$proc" \
    "FAIL: no '## $GRADED_SECTION' heading in $DEFAULT_TARGET"
  cases=$((cases + 1))

  proc="$tmp/proc-no-qt"
  make_proc_root "$proc"
  write_lines "$proc/$DEFAULT_TARGET" '# Competitor Intel Briefing' '' "## $GRADED_SECTION" '' \
    "$clean"
  expect_proc_red "child, no $BUDGET_SECTION" "$proc" \
    "FAIL: no '## $BUDGET_SECTION' heading in $DEFAULT_TARGET"
  cases=$((cases + 1))

  # P1: the whole script as a child, green, with NO argument, so the default target is the thing
  # under test and the documented default is exercised by the run rather than by prose. The count in
  # the token is asserted against the CHECKS_RUN that the SAME fixture left in this shell, so the
  # printed number is tied to execution on both sides.
  proc="$tmp/proc-green"
  make_proc_root "$proc"
  write_brief "$proc/$DEFAULT_TARGET" "$qt13" "$after" "$clean"
  check_file "$proc/$DEFAULT_TARGET"
  expect_proc_green 'child, clean default target' "$proc" \
    "COVERAGE-NOTES-OK ($CHECKS_RUN checks, 0 findings in $DEFAULT_TARGET)"
  cases=$((cases + 1))

  # P2: the same child on a pipeline-voiced default target. Exit non-zero, the finding on the stream,
  # and an explicit guard inside expect_proc_red that COVERAGE-NOTES-OK was NOT printed.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  write_brief "$proc/$DEFAULT_TARGET" "$qt13" "$after" \
    'Two rivals are graded below their own files on the grid.'
  expect_proc_red 'child, pipeline-voiced default' "$proc" 'FAIL: C1 process language'
  cases=$((cases + 1))

  # P3: the child with a path ARGUMENT naming a file that does not exist, which is both the argument
  # dispatch and the missing-file failure, proved in the process that actually exits.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child, absent path argument' "$proc" 'FAIL: no brief to grade' 'build/nope.md'
  cases=$((cases + 1))

  # CHECKS_RUN DERIVED FROM EXECUTION, proved on the one pair of runs where a hardcoded 2 and a
  # derived count disagree: the fail-closed path runs NO check, a full grade runs both.
  check_file "$tmp/absent.md"
  if [ "$CHECKS_RUN" -ne 0 ]; then
    printf 'SELFTEST FAIL: the fail-closed path ran %s checks, want 0\n' "$CHECKS_RUN" >&2
    return 1
  fi
  check_file "$tmp/c2-under.md"
  if [ "$CHECKS_RUN" -ne 2 ]; then
    printf 'SELFTEST FAIL: a full grade ran %s checks, want 2\n' "$CHECKS_RUN" >&2
    return 1
  fi
  printf 'SELFTEST count OK %-30s -> 0 fail-closed, 2 on a full grade\n' 'CHECKS_RUN derived'
  cases=$((cases + 1))

  # P4: THE CHECK-COUNT ASSERTION IN `main()`, proved red the only way it can be. No input reaches
  # it: on a file that grades at all, both checks run, and on one that does not, a fail-closed
  # finding exits first. So the case MUTATES the child -- one copy of this script with its FIRST
  # `CHECKS_RUN` increment deleted -- and runs it on a brief that is clean on both checks. A script
  # that graded once must not report a clean grade. If the deletion below ever stops matching, the
  # child is unmutated and green, and `expect_proc_red` fails on the exit code; the case cannot
  # quietly stop testing anything.
  proc="$tmp/proc-onecheck"
  make_proc_root "$proc"
  write_brief "$proc/$DEFAULT_TARGET" "$qt13" "$after" "$clean"
  awk 'BEGIN { cut = 0 }
       cut == 0 && $0 == "  CHECKS_RUN=$((CHECKS_RUN + 1))" { cut = 1; next }
       { print }' "$proc/tools/coverage-notes.sh" >"$proc/tools/mutant.sh"
  mv "$proc/tools/mutant.sh" "$proc/tools/coverage-notes.sh"
  expect_proc_red 'child, one check of two ran' "$proc" \
    "FAIL: 1 of 2 checks ran on $DEFAULT_TARGET; a clean grade needs both"
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  if [ -e "$tmp" ]; then
    printf 'SELFTEST FAIL: residue left at %s\n' "$tmp" >&2
    return 1
  fi
  printf 'SELFTEST OK: %s cases, exemplar green at 93 graded-section words against 166 budget-section words (a 56%% section, 73 words of margin), the shipped shakedown red with C1 on EXACTLY 2 lines -- :93 matching "graded below" and "their own files" together as ONE finding where a per-term count would say 3, and :97 matching "both tools" -- and C2 red at 147 words against 143, %s red on both checks with C1 on EXACTLY 3 lines and its two scope decoys silent, each of the %s terms red alone and green when planted in the budget section and in the section after the graded one, two terms on one line reported once naming both, Both Tools red on case, C2 green one word under and red at equal and one word over with both counts pinned, a graded section written ENTIRELY as two `###` headings red on C1 at both lines and red on C2 at 18 words against 13, the counting method proved clause by clause (a table row 0, a `###` heading its own 5 words and the 4-word line under it at 9 without ending the section, a bare URL 0, a blockquote marker 0, an emphasis marker 0 -- pinned on the glued span the briefs use, which is count-neutral, and on a lone `*`, which is what discriminates -- and a link its text alone at 7 words, pinned on the plain form the briefs use, which is count-neutral, and on the titled form, which counts 7 against the unreplaced 11 and is what discriminates), 4 fail-closed child readings each pinning its own message (missing, empty, no graded section, no budget section), 4 further child cases (clean default green with the token and a count asserted against the CHECKS_RUN the same brief left in this shell, a pipeline-voiced default red with no token, an absent argument red, and a child with one increment deleted red on the check-count assertion rather than reporting a clean grade), CHECKS_RUN derived from execution at 0 and 2, no residue at %s\n' \
    "$cases" "tools/fixtures/pipeline-voiced-coverage.md" "$(term_count)" "$tmp"
}

main() {
  local target
  cd "$ROOT"
  target="${1:-$DEFAULT_TARGET}"
  check_file "$target"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  # No findings is not the same as both checks having run. This is what makes the count in the
  # success line falsifiable: without it, the line could be printed by a script that graded once.
  if [ "$CHECKS_RUN" -ne 2 ]; then
    printf 'FAIL: %s of 2 checks ran on %s; a clean grade needs both\n' "$CHECKS_RUN" "$target" >&2
    exit 1
  fi
  printf 'COVERAGE-NOTES-OK (%s checks, 0 findings in %s)\n' "$CHECKS_RUN" "$target"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
