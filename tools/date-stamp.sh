#!/usr/bin/env bash
# The date-stamp lint. It greps one markdown brief for how the brief stamps TIME, collects every
# finding, and fails closed.
#
# THE ABSTRACTION. A brief carries two kinds of date and they have opposite requirements. The
# DOCUMENT STAMP is what the brief says about ITSELF -- when its evidence was gathered, and by
# extension the moment every present-tense claim in it is read against. An EVENT DATE is what the
# brief says about the WORLD -- a raise, a post, a hire. A document stamp carries month and year and
# never a day, so the artefact does not age between the build and the send: a brief stamped
# "September 2026" is as true on the 28th as on the 2nd, and one stamped "2 September 2026" is
# visibly stale the moment it sits a week in an inbox. An event date keeps its day, because a day
# that is knowable and dropped is evidence thrown away. This script grades the first and never the
# second.
#
# WHY IT EXISTS. Nothing downstream reads the brief's own stamp. `build/build.py`'s `audit()` grades
# structure, `tools/thesis-check.sh` grades the sidecar, `tools/ai-smell.sh` grades voice; a brief
# that stamped itself day-exact, or twice, or not at all, rendered green through all three. The
# masthead half is the same gap from the other side: `build/briefing.html:222-223` records the intent
# verbatim -- "NO running header and NO date. The date was removed from the masthead deliberately and
# a folio is not the place to reintroduce it." -- and that intent was an authoring standard with no
# grep behind it.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name, so
# this is a standalone script the pipeline invokes, exactly as `tools/thesis-check.sh`,
# `tools/ai-smell.sh` and the ICP floor are standalone build-blocking lints.
#
# It runs in PHASE 5, BEFORE the first build, and it reads the MARKDOWN target only -- never the
# HTML and never the PDF. Every finding it raises is a prose edit, and after the build a prose edit
# costs a rebuild.
#
# It collects every finding and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is.
#
# `grep` is wrapped to `ugrep` in the interactive shell, where a pattern starting with `--` parses as
# an option, so every pattern below is passed after `-e`. Inside this script `grep` is /usr/bin/grep
# (BSD); `\b` is honoured there and is MEASURED -- `\b(mar)\b` does not match `markdown="1"`, which
# is on the exemplar's own masthead opening line and would otherwise red D3 on sight.
#
# WHAT IT DELIBERATELY DOES NOT CHECK, and why each one is absent rather than forgotten:
#
#   1. EVENT DATES, in either direction -- any date describing something in the world, including one
#      attached to a cited source. Measured on the exemplar 2026-09-07: 12 day-exact event dates
#      (`build/briefing.md:14,24,32,33,35,36,37`) and 4 month-only ones (`:26,33,34,82`). A
#      month-only event date is what an undated source yields, not a violation, so no check can
#      separate the two. Grading them either way reds the accepted brief.
#   2. "PROSE SPELLS THE MONTH, TABLES ABBREVIATE." Proposed by
#      `output/research/agent-v2/A1-transcript-learnings.md:199-202`. Refused on measurement: the
#      exemplar breaks it in its own thesis paragraph -- `build/briefing.md:14` "a New York post
#      dated 11 Aug 2026" is prose and abbreviated, against `:24` "went quiet on 10 April 2026",
#      prose and spelled. `docs/PLAN.md` section 2 puts the shipped brief above the source, so the
#      exemplar wins and the rule does not land.
#   3. UNANCHORED PRESENT-TENSE CLAIMS. `build/briefing.md:26` "right now", `:32` "nothing published
#      since", "now shows", "still cites", `:36` "in twelve months". These are what actually ages,
#      and they cannot be banned: the exemplar uses all of them. D1 is the mechanical half -- it
#      holds the anchor those claims are read against -- and the judgement half stays an authoring
#      standard.
#   4. MACHINE-READ DATES. `captured` in `output/snapshots/*.json`, `^captured:` in
#      `output/review/thesis.md`, `BRIEF_RUN_DATE` and `EXEMPLAR_RUN_DATE` are day-exact
#      `YYYY-MM-DD` and load-bearing as such: `build/build.py:276-286` selects the cohort by exact
#      string compare and `tools/thesis-check.sh:99` rejects any other shape. This lint reads the
#      brief markdown only and touches none of them.
#   5. THE RENDERED PDF. See the Phase 5 note above.
#   6. A DATE WITH NO NUMBER SHAPE, in the masthead. D3 was narrowed from "any bare month word or
#      4-digit year, anywhere in the masthead" to "a month adjacent to a number, or a fully numeric
#      date", because the bare-token version reds a legitimate client masthead on its one per-run
#      variable line, the subtitle: measured by review, `<p class="subtitle">Prepared for June
#      Capital. Covering Acme, Borealis.</p>`, `...May Mobility...`, `...Jan.ai, Sierra,
#      Decagon...` and `...Nine2Five, 2026 Labs.</p>` all red today and none is a defect. `May
#      Mobility` and `Jan.ai` are real companies in the market this repo briefs on, `may` is also
#      the modal verb, and a bare `20[0-9]{2}` cannot be told from `2026 Labs`. The shape rule buys
#      that back and gives up three things in exchange, each MEASURED against the new pattern: a
#      bare 4-digit year alone in the masthead (`2026`, no adjacent month or day) is no longer
#      detected; a numeric date with no year (`07/09`) is no longer detected; and a bare month or
#      season word with no adjacent digit at all (`published in October`, `Autumn`) is no longer
#      detected, because every one of the four shapes below requires a digit next to the month or a
#      fully numeric date. Also true before this change and unrelated to D3: a day spelled as a
#      word carries no digit either -- `the second of September 2026` -- so D2's residue rule, which
#      only strips 4-digit years and looks at what digits remain, cannot see it. D2 catches a
#      digit-bearing day, not every day.
#
# PRECONDITION: none beyond the target file existing. No network, no MKT1 call, no env var, no build
# artefact, no run directory, no browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_TARGET="build/briefing.md"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

# Incremented once per check that ACTUALLY RUNS, so the success line cannot claim three checks while
# two run. Same intent as `rule_count()` in `tools/ai-smell.sh`, derived from execution rather than
# from a table, because these three checks are not uniform enough to be table rows and a table would
# then be a second thing to drift. On the empty/absent path it stays 0 and main() exits 1, so the OK
# line is never printed with a count of zero.
CHECKS_RUN=0

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# --- the patterns ---------------------------------------------------------------------------------
# The document stamp is the `.meta` element. `build/brief.css:940-942` documents it as "The
# accessed-date line", `references/brief-contract.md:40` lists `meta` among the 18 required
# load-bearing classes, and the exemplar carries exactly one occurrence (measured 2026-09-07,
# `grep -c 'class="meta"' build/briefing.md` = 1).
#
# Two patterns and not one, on purpose. D1 counts the CLASS TOKEN, which is the thing the class
# contract names and the thing a count can be compared against. D2 needs the INNER TEXT, so it needs
# the whole element. Where the two disagree -- a `class="meta"` that no element pattern can extract,
# i.e. a malformed or nested stamp -- D2 says so and fails, rather than grading zero stamps clean.
META_CLASS='class="meta"'
META_ELEMENT='<span class="meta"[^>]*>[^<]*</span>'

# D3's date tell requires a date SHAPE, not a bare month or year token: a month directly adjacent to
# a number, or a fully numeric date. See item 6 of "WHAT IT DELIBERATELY DOES NOT CHECK" above for
# why the bare-token version was refused and what this narrower one gives up. Four alternatives and
# nothing else:
#   1. a full month name or three-letter abbreviation, up to 3 non-alphanumeric characters, then 1
#      to 4 digits -- catches "September 2026", "Sep 2026", "September, 2026".
#   2. 1 to 2 digits, up to 3 non-alphanumeric characters, then a full month name or abbreviation --
#      catches "7 September", "07 Sep".
#   3. a d/m/y numeric date: 1-2 digits, one of `/`, `.` or `-`, 1-2 digits, the same separator
#      class, 2-4 digits -- catches "07/09/2026", "7.9.26".
#   4. an ISO date: 4 digits, `-`, 2 digits, `-`, 2 digits -- catches "2026-09-07".
# `may` appears in the full-name alternation only; listing it twice would change nothing. The
# TRAILING `\b` on the abbreviations is load-bearing and not decoration, exactly as before the
# narrowing: without it `mar` matches `markdown="1"` on the masthead's own opening line. MEASURED
# still to hold below (`D3 markdown="1" is not March`).
MONTH_FULL='(january|february|march|april|may|june|july|august|september|october|november|december)'
MONTH_ABBR='(jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b'
MONTH_ANY="($MONTH_FULL|$MONTH_ABBR)"

MASTHEAD_DATE="$MONTH_ANY"'[^A-Za-z0-9]{0,3}[0-9]{1,4}'
MASTHEAD_DATE="$MASTHEAD_DATE"'|[0-9]{1,2}[^A-Za-z0-9]{0,3}'"$MONTH_ANY"
MASTHEAD_DATE="$MASTHEAD_DATE"'|[0-9]{1,2}[/.-][0-9]{1,2}[/.-][0-9]{2,4}'
MASTHEAD_DATE="$MASTHEAD_DATE"'|[0-9]{4}-[0-9]{2}-[0-9]{2}'

# --- the check ------------------------------------------------------------------------------------
# check_file populates FAILS for one target path and ALWAYS returns 0; the caller decides. Same
# contract as `check_file` in `tools/ai-smell.sh` and `tools/thesis-check.sh`, and it is what lets
# the selftest run every case in this shell without `set -e` ending the run at the first red.
check_file() {
  local f="$1" class_hits n stamps stamp_n h ln raw text residue oldifs
  local mstart mend block hits lines

  FAILS=""
  CHECKS_RUN=0

  # `test -s` first, and every check skipped when it fires. An absent or empty brief is a FAILURE and
  # never a vacuous pass: `grep` over nothing matches nothing, and three checks reporting no findings
  # on a file that does not exist is precisely the shape of green this repository treats as a lie.
  if [ ! -s "$f" ]; then
    add_fail "FAIL: no brief to grade at $f (missing or empty)"
    return 0
  fi

  # --- D1: exactly one document stamp ---------------------------------------------------------
  # Counted by OCCURRENCE and not by line: `grep -c` counts matching lines, so two stamps sharing a
  # source line would report 1 and walk past the plural case this check exists for.
  class_hits="$(grep -o -e "$META_CLASS" "$f" || true)"
  if [ -z "$class_hits" ]; then
    n=0
  else
    n="$(printf '%s\n' "$class_hits" | wc -l | tr -d ' ')"
  fi
  CHECKS_RUN=$((CHECKS_RUN + 1))

  if [ "$n" -eq 0 ]; then
    add_fail "FAIL: D1 no document stamp in $f: the <span class=\"meta\"> element is absent, so \
every present-tense claim in the brief floats free of the date it is read against"
  elif [ "$n" -gt 1 ]; then
    lines="$(grep -n -o -e "$META_CLASS" "$f" | cut -d: -f1 | tr '\n' ' ' | sed -e 's/ $//')"
    add_fail "FAIL: D1 $n document stamps in $f (lines $lines): exactly one is required, so the \
brief has one anchor and not a choice of them"
  fi

  # --- D2: the document stamp carries no day --------------------------------------------------
  # Strip the tags, remove every 4-digit year, and look at what is left. After the years are gone, a
  # surviving digit in a DOCUMENT stamp can only be a day number or an ordinal; there is nothing else
  # a stamp legitimately counts.
  stamps="$(grep -no -e "$META_ELEMENT" "$f" || true)"
  if [ -z "$stamps" ]; then
    stamp_n=0
  else
    stamp_n="$(printf '%s\n' "$stamps" | wc -l | tr -d ' ')"
  fi
  CHECKS_RUN=$((CHECKS_RUN + 1))

  if [ "$n" -ge 1 ] && [ "$stamp_n" -eq 0 ]; then
    # D1 found the class and D2 cannot read the element. Reporting "no day found" here would be a
    # pass over an unreadable stamp, which is the vacuous green this file exists to refuse.
    add_fail "FAIL: D2 document stamp in $f is not readable: class=\"meta\" occurs $n time(s) but \
no <span class=\"meta\">text</span> element could be extracted"
  fi

  # Split on newlines with globbing OFF: a stamp's text is prose and may carry `*`, and an unguarded
  # word split would expand it against the working directory.
  oldifs="$IFS"
  set -f
  IFS=$'\n'
  for h in $stamps; do
    ln="${h%%:*}"
    raw="${h#*:}"
    text="$(printf '%s' "$raw" | sed -e 's/<[^>]*>//g')"
    residue="$(printf '%s' "$text" | sed -E -e 's/20[0-9]{2}//g' | tr -cd '0-9')"
    if [ -n "$residue" ]; then
      add_fail "FAIL: D2 document stamp carries a day at $f:$ln: \"$text\" (digits surviving after \
every 4-digit year is removed: $residue)"
    fi
  done
  IFS="$oldifs"
  set +f

  # --- D3: the masthead carries no date -------------------------------------------------------
  # The block runs from the line opening `<div class="masthead"` to the next line closing `</div>`.
  # An absent or unterminated masthead is a FAILURE and never a vacuous pass: an empty block matches
  # no date, and "no date found in a block that does not exist" is the same lie as grading an empty
  # file clean.
  CHECKS_RUN=$((CHECKS_RUN + 1))
  mstart="$(awk '/<div class="masthead"/{print NR; exit}' "$f")"
  if [ -z "$mstart" ]; then
    add_fail "FAIL: D3 no masthead block in $f: no line opens <div class=\"masthead\", so the \
no-date rule of build/briefing.html:222-223 could not be graded"
  else
    mend="$(awk -v s="$mstart" 'NR>=s && /<\/div>/{print NR; exit}' "$f")"
    if [ -z "$mend" ]; then
      add_fail "FAIL: D3 masthead block in $f opens at line $mstart and is never closed by </div>"
    else
      # Numbered by awk from the FILE's own NR, so every reported line number is the source line and
      # not an offset into the extracted block.
      block="$(awk -v s="$mstart" -v e="$mend" 'NR>=s && NR<=e {printf "%d:%s\n", NR, $0}' "$f")"
      hits="$(printf '%s\n' "$block" | grep -iE -e "$MASTHEAD_DATE" || true)"
      if [ -n "$hits" ]; then
        oldifs="$IFS"
        set -f
        IFS=$'\n'
        for h in $hits; do
          ln="${h%%:*}"
          text="${h#*:}"
          add_fail "FAIL: D3 masthead carries a date at $f:$ln: $text"
        done
        IFS="$oldifs"
        set +f
      fi
    fi
  fi

  return 0
}

# --- selftest -------------------------------------------------------------------------------------
# Proves each of the four failure modes red on its own minimal fixture, proves D2 and D3 in BOTH
# directions on the same words, proves the exemplar green, proves the red artefact red on all three
# checks, and runs the script as a child process three times so `main()`, the default target, the
# argument dispatch, the OK line and the non-zero exit are exercised by the run and not by prose.
# A check that has never gone red is an untested assertion.

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

# THE ONE SECTION HEADING THE FIXTURES WRITE, named once and labelled. A fixture brief carries
# headings, and this is where this file writes one; `git grep -n heading-literal` finds it.
FX_SOURCES="Sources"  # heading-literal: the fixture brief needs the section the stamp sits under

# A clean masthead and a clean stamp, reused by every fixture below, so a red case proves the tell
# and not the scaffolding.
write_clean() {
  local f="$1"
  write_lines "$f" \
    '<div class="masthead" markdown="1">' \
    '' \
    '<p class="wordmark"><a href="https://in-the-loop.studio">In The Loop</a></p>' \
    '<p class="tagline">Agent-native startup operations</p>' \
    '' \
    '# Competitor Intel Briefing' \
    '' \
    '<p class="subtitle">Prepared for Northwind. Covering Acme, Borealis.</p>' \
    '<hr class="masthead-rule">' \
    '</div>' \
    '' \
    "## $FX_SOURCES" \
    '' \
    '<p markdown="1">Acme pricing page <span class="meta">All pages accessed September 2026.</span></p>'
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

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main()`, its `cd "$ROOT"`, the default target,
# the argument dispatch, the DATE-STAMP-OK line and the non-zero exit would be exercised by nothing.
# That gap is load-bearing and not hypothetical: inside `OUT="$( (f) 2>&1 )"` bash suspends `set -e`,
# so an in-process case cannot see an abort at all, and it was `main()` on the real corpus that
# killed `tools/known-traps.sh` while its twelve in-process cases stayed green. The cases below copy
# this script into a fixture root and run it as a CHILD with its own fully armed `set -euo pipefail`,
# which is the invocation a run actually makes. The idiom is `tools/ai-smell.sh:246-310`.
PROC_RC=0
PROC_OUT=""

make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/build"
  cp "${BASH_SOURCE[0]}" "$root/tools/date-stamp.sh"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/date-stamp.sh" "$@" 2>&1 )" || PROC_RC=$?
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
    *DATE-STAMP-OK*)
      printf 'SELFTEST FAIL: a red child run printed DATE-STAMP-OK: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  printf 'SELFTEST proc red %-30s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp fixture cases=0 id missing proc

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/date-stamp-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # The scaffolding itself, green. Every red fixture below is this file plus one defect.
  write_clean "$tmp/clean.md"
  expect_green 'clean brief fragment' "$tmp/clean.md"
  cases=$((cases + 1))

  # D1-zero: the stamp deleted, nothing else touched.
  write_clean "$tmp/d1-zero.md"
  sed -e '/class="meta"/d' "$tmp/clean.md" >"$tmp/d1-zero.md"
  expect_red 'D1 zero stamps' "$tmp/d1-zero.md" 'FAIL: D1 no document stamp'
  cases=$((cases + 1))

  # D1-plural: a SECOND month-only stamp, so the finding is the count and not a day. Both stamps are
  # legitimate in isolation, which is what makes this a D1 case and not a D2 one.
  write_clean "$tmp/d1-plural.md"
  printf '%s\n' \
    '<p markdown="1">Borealis changelog <span class="meta">All pages accessed September 2026.</span></p>' \
    >>"$tmp/d1-plural.md"
  expect_red 'D1 two stamps' "$tmp/d1-plural.md" 'FAIL: D1 2 document stamps'
  cases=$((cases + 1))

  # D1-plural, both stamps sharing ONE source line. D1 counts by OCCURRENCE (`grep -o`) and not by
  # LINE (`grep -c`), and the comment on that count says why: two stamps sharing a source line would
  # report 1 under line-counting and walk past the plural case this check exists for. No case above
  # exercises that: `d1-plural.md` puts its second stamp on its own new line. Without this case, a
  # regression that swapped `grep -o -e "$META_CLASS"` back to a plain `grep -e` would leave the
  # whole suite green.
  write_clean "$tmp/d1-plural-oneline.md"
  sed -e 's#<span class="meta">All pages accessed September 2026\.</span></p>#<span class="meta">All pages accessed September 2026.</span> <span class="meta">All pages accessed September 2026.</span></p>#' \
    "$tmp/clean.md" >"$tmp/d1-plural-oneline.md"
  expect_red 'D1 two stamps, one line' "$tmp/d1-plural-oneline.md" 'FAIL: D1 2 document stamps'
  cases=$((cases + 1))

  # D2 in both directions on the SAME words, which is the whole rule: the month-only spelling is the
  # correct one and must stay green, the day-bearing spelling must red. A one-sided pair would be
  # satisfied by a check that reds every stamp.
  write_clean "$tmp/d2-green.md"
  expect_green 'D2 month-only stamp' "$tmp/d2-green.md"
  cases=$((cases + 1))

  write_clean "$tmp/d2-red.md"
  sed -e 's/accessed September 2026/accessed 2 September 2026/' "$tmp/clean.md" >"$tmp/d2-red.md"
  expect_red 'D2 day-bearing stamp' "$tmp/d2-red.md" 'FAIL: D2 document stamp carries a day'
  cases=$((cases + 1))

  # The year itself must not be mistaken for a day. Without this case D2 could be a plain
  # "any digit is a finding" rule and the suite would not notice.
  case "$FAILS" in
    *'digits surviving after every 4-digit year is removed: 2'*) : ;;
    *) printf 'SELFTEST FAIL: D2 reported the wrong residue; got: %s\n' "$FAILS" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-29s -> residue is the day 2, not the year 2026\n' 'D2 residue'
  cases=$((cases + 1))

  # An ordinal, which carries a digit and no month-day spelling. Same failure, different shape.
  write_clean "$tmp/d2-ordinal.md"
  sed -e 's/accessed September 2026/accessed the 2nd of September 2026/' "$tmp/clean.md" \
    >"$tmp/d2-ordinal.md"
  expect_red 'D2 ordinal in stamp' "$tmp/d2-ordinal.md" 'FAIL: D2 document stamp carries a day'
  cases=$((cases + 1))

  # A `class="meta"` D2 cannot read. Without this case an unreadable stamp would be graded clean.
  write_lines "$tmp/d2-unreadable.md" \
    '<div class="masthead" markdown="1">' \
    '<p class="tagline">Agent-native startup operations</p>' \
    '</div>' \
    '<p><span class="meta">All pages accessed <em>September 2026</em>.</span></p>'
  expect_red 'D2 unreadable stamp' "$tmp/d2-unreadable.md" 'FAIL: D2 document stamp'
  cases=$((cases + 1))

  # D3 on THE EXEMPLAR'S OWN MASTHEAD, in both directions. The green half is the real block lifted
  # verbatim; the red half is the same block with a date inserted and nothing else changed, so the
  # pair fails if either the pattern or the block extraction stops working.
  sed -n -e '/<div class="masthead"/,/<\/div>/p' "$ROOT/$DEFAULT_TARGET" >"$tmp/mast-green.md"
  printf '%s\n' \
    '<p markdown="1">Acme pricing page <span class="meta">All pages accessed September 2026.</span></p>' \
    >>"$tmp/mast-green.md"
  expect_green 'D3 exemplar masthead' "$tmp/mast-green.md"
  cases=$((cases + 1))

  awk '{print} /class="tagline"/{print "<p class=\"dateline\">September 2026</p>"}' \
    "$tmp/mast-green.md" >"$tmp/mast-red.md"
  expect_red 'D3 year in exemplar masthead' "$tmp/mast-red.md" 'FAIL: D3 masthead carries a date'
  cases=$((cases + 1))

  # The number-then-month shape (alternative 2), a day with no year. A BARE month token with no
  # adjacent digit at all, e.g. "Autumn, published in October", is no longer caught after the
  # narrowing documented in item 6 of "WHAT IT DELIBERATELY DOES NOT CHECK" above -- MEASURED: it
  # is what a shape rule that keeps "May Mobility" and "Jan.ai" out of D3 necessarily gives up, since
  # every alternative below requires a digit next to the month.
  write_clean "$tmp/d3-month.md"
  sed -e 's|<hr class="masthead-rule">|<p class="dateline">Published 7 October</p>|' \
    "$tmp/clean.md" >"$tmp/d3-month.md"
  expect_red 'D3 day-then-month, no year' "$tmp/d3-month.md" 'FAIL: D3 masthead carries a date'
  cases=$((cases + 1))

  # `markdown="1"` is on the exemplar's own masthead opening line and begins with `mar`. Delete the
  # trailing `\b` from the abbreviation alternation and the exemplar reds. The green cases above
  # already cover it; this one names it so a later widening of the pattern has a case to fail.
  write_lines "$tmp/d3-markdown.md" \
    '<div class="masthead" markdown="1">' \
    '<p class="tagline">Agent-native startup operations</p>' \
    '</div>' \
    '<p><span class="meta">All pages accessed September 2026.</span></p>'
  expect_green 'D3 markdown="1" is not March' "$tmp/d3-markdown.md"
  cases=$((cases + 1))

  # An absent masthead and an unterminated one, both FAILURES. Without these two an empty block
  # would match no date and report clean.
  write_lines "$tmp/d3-absent.md" \
    "## $FX_SOURCES" \
    '<p><span class="meta">All pages accessed September 2026.</span></p>'
  expect_red 'D3 masthead absent' "$tmp/d3-absent.md" 'FAIL: D3 no masthead block'
  cases=$((cases + 1))

  write_lines "$tmp/d3-open.md" \
    '<div class="masthead" markdown="1">' \
    '<p class="tagline">Agent-native startup operations</p>' \
    '<p><span class="meta">All pages accessed September 2026.</span></p>'
  expect_red 'D3 masthead unterminated' "$tmp/d3-open.md" 'FAIL: D3 masthead block'
  cases=$((cases + 1))

  # An absent and an empty target are FAILURES. Without these two the whole script could be pointed
  # at nothing and report three clean checks.
  expect_red 'absent file' "$tmp/absent.md" 'no brief to grade'
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty file' "$tmp/empty.md" 'no brief to grade'
  cases=$((cases + 1))

  # THE RED ARTEFACT. It must red ALL THREE checks, because a fixture that reds two leaves one check
  # proved by this file's own minimal strings alone. It is a committed artefact: if it is absent, say
  # so by path and fail, rather than stubbing it here and grading this script against its own idea of
  # an aged brief.
  fixture="$ROOT/tools/fixtures/aged-brief.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no aged red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  check_file "$fixture"
  missing=""
  for id in D1 D2 D3; do
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
  printf 'SELFTEST red OK   %-30s -> all three checks red\n' 'aged-brief.md'
  cases=$((cases + 1))

  # THE EXEMPLAR ASSERTION, and the one that must never be weakened to reach green. If
  # `build/briefing.md` goes red here, the finding is the answer: report it and stop. Editing a
  # pattern until the accepted brief passes is how a sibling rule ended up running backwards against
  # the artefact it was meant to grade.
  expect_green 'exemplar build/briefing.md' "$ROOT/$DEFAULT_TARGET"
  cases=$((cases + 1))

  # P1: the whole script as a child, green, with NO argument, so the default target is the thing
  # under test and the documented default is exercised by the run rather than by prose.
  proc="$tmp/proc-green"
  make_proc_root "$proc"
  write_clean "$proc/$DEFAULT_TARGET"
  expect_proc_green 'child, clean default target' "$proc" 'DATE-STAMP-OK'
  cases=$((cases + 1))

  # The OK line's check count must be derived, not asserted. Three checks ran, so it must say 3.
  case "$PROC_OUT" in
    *'DATE-STAMP-OK (3 checks, 0 findings in build/briefing.md)'*) : ;;
    *) printf 'SELFTEST FAIL: OK line did not report 3 checks; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-29s -> "%s"\n' 'OK line check count' "$PROC_OUT"
  cases=$((cases + 1))

  # P2: the same child on an AGED default target. Exit non-zero, the finding on the stream, and an
  # explicit guard inside expect_proc_red that DATE-STAMP-OK was NOT printed.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  cp "$fixture" "$proc/$DEFAULT_TARGET"
  expect_proc_red 'child, aged default target' "$proc" 'FAIL: D3 masthead carries a date'
  cases=$((cases + 1))

  # P3: the child with a path ARGUMENT naming a file that does not exist, which is both the argument
  # dispatch and the missing-file failure, proved in the process that actually exits.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child, absent path argument' "$proc" 'no brief to grade' 'build/nope.md'
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  printf 'SELFTEST OK: %s cases, D1 red at zero and at two (on separate lines and sharing one line), D2 red on a day and on an ordinal and green on a month-only stamp of the same words, D2 red on an unreadable stamp, D3 green on the exemplar'"'"'s real masthead and red on the same block with a date inserted, D3 red on a day-then-month with no year and on an absent and an unterminated block, markdown="1" proved not to be March, absent and empty red, %s red on all three checks, exemplar green, 3 child-process cases (clean default green with the token and a derived count of 3, aged default red with no token, absent argument red)\n' \
    "$cases" "tools/fixtures/aged-brief.md"
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
  printf 'DATE-STAMP-OK (%s checks, 0 findings in %s)\n' "$CHECKS_RUN" "$target"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
