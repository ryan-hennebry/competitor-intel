#!/usr/bin/env bash
# S14, R12. Run-time gate for the thesis sidecar `output/review/thesis.md`, asserted at the end of
# Phase 7 and failing closed.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name and
# R18 fixes the count at seven, so this is a standalone script the pipeline invokes, exactly as the
# ICP floor and the divergence ledger are standalone build-blocking lints.
#
# It collects every failure and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is.
#
# `grep` is wrapped to `ugrep` on this machine, where a pattern starting with `--` parses as an
# option, so every pattern below is passed as `grep -e '<pattern>'`.
#
# PRECONDITION: `BRIEF_RUN_DATE`. The fifth assertion compares the sidecar's own `captured:` date
# against the date of the run being checked, so a bare run checks against today and a sidecar from
# any other day is red. That is the point: it is what stops one run's sidecar being read as this
# run's evidence. Checking the committed exemplar, whose sidecar is `captured: 2026-09-02`,
# therefore requires `BRIEF_RUN_DATE=2026-09-02 bash tools/thesis-check.sh`. The comparison is
# exact lexical equality on a bare `YYYY-MM-DD`, the same way `run_cohort()` in `build/build.py`
# picks its cohort.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIDECAR="output/review/thesis.md"
RUN_DATE="${BRIEF_RUN_DATE:-$(date +%F)}"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# check_file populates FAILS for one sidecar path and always returns 0; the caller decides.
# The second parameter is the date of the run being checked; it defaults to $RUN_DATE, so every
# existing one-argument call is unchanged, and the selftest passes it explicitly to stay
# independent of the ambient BRIEF_RUN_DATE.
check_file() {
  local f="$1" run_date="${2:-$RUN_DATE}" openings tlines ncaptured captured
  FAILS=""

  # `test -s` first, and the rest skipped when it fires: an absent or empty sidecar is a different
  # failure from a wrong one, and `grep -c` over nothing prints 0, which would be reported as an
  # ordinary count mismatch. Distinguishing "absent" from "wrong" is what this step asks of the run.
  if [ ! -s "$f" ]; then
    add_fail "FAIL: no thesis sidecar at $f"
    return 0
  fi

  openings="$(grep -c -e '^### Opening [123]' "$f" || true)"
  if [ "$openings" -ne 3 ]; then
    add_fail "FAIL: not three openings in $f (found $openings)"
  fi

  tlines="$(grep -cE -e '^(T1|T2|T3):' "$f" || true)"
  if [ "$tlines" -ne 9 ]; then
    add_fail "FAIL: not nine test results in $f (found $tlines)"
  fi

  if ! grep -q -e 'swap' "$f"; then
    add_fail "FAIL: no swap instruction in $f"
  fi

  # The sidecar must say which run it belongs to. Without this, a sidecar left over from an earlier
  # run passes the four shape checks and is read as this run's evidence.
  #
  # Exactly one line-anchored `^captured:`, counted before it is read. The anchor is load-bearing:
  # this sidecar's prose already names the snapshot field in backticks, and prose that writes that
  # field with its colon is read as the date by an unanchored match. Two anchored lines are a
  # failure rather than a preference for the first, because a sidecar naming two runs does not say
  # which run it is evidence for, and silently taking the top one is how a stale date survives an
  # edit.
  #
  # Four failures, one of which fires: absent, duplicated, malformed, mismatched. They are different
  # repairs — write the line, delete the one that is not this run's, fix its shape, or point the
  # run at the sidecar's own date — so they get different messages, the same reason `test -s` is
  # separated from a wrong count above.
  ncaptured="$(grep -c -e '^captured:' "$f" || true)"
  if [ "$ncaptured" -eq 0 ]; then
    add_fail "FAIL: no captured: date in $f; this run is $run_date, so the sidecar cannot say whose run it is. Add a 'captured: YYYY-MM-DD' line, or set BRIEF_RUN_DATE to the run it belongs to."
  elif [ "$ncaptured" -gt 1 ]; then
    add_fail "FAIL: more than one captured: date in $f (found $ncaptured); the sidecar must name exactly one run."
  else
    captured="$(grep -e '^captured:' "$f" || true)"
    captured="$(printf '%s\n' "${captured#captured:}" \
      | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    # `case` rather than a regex: its patterns are whole-string anchored, so this is exactly
    # ^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$ with no quoting hazard on a wrapped grep.
    case "$captured" in
      [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
        # Exact lexical equality, the comparison run_cohort() makes on the same date form.
        if [ "$captured" != "$run_date" ]; then
          add_fail "FAIL: thesis sidecar is dated $captured but this run is $run_date; if you are checking the exemplar rather than a run, set BRIEF_RUN_DATE=$captured"
        fi
        ;;
      *)
        add_fail "FAIL: captured: date in $f is '$captured', not YYYY-MM-DD; this run is $run_date."
        ;;
    esac
  fi

  return 0
}

# --- selftest -----------------------------------------------------------------------------------
# Proves each of the five assertions goes red against a fixture in $TMPDIR, and leaves no residue.
# A check that has never gone red is an untested assertion.
#
# Every case passes its run date explicitly, so the selftest result does not move with the calendar
# or with an ambient BRIEF_RUN_DATE.

# $5 is the captured value: a YYYY-MM-DD string writes `captured: <value>`, the literal `none`
# writes no captured line at all, and anything else is written verbatim so the malformed branch can
# be exercised.
#
# $6 is optional and, when given, is appended verbatim as a last body line. One parameter covers
# both remaining fixtures because both are just an extra line: prose that mentions `captured:`
# mid-sentence, and a second `captured:` line.
write_fixture() {
  local f="$1" openings="$2" tlines="$3" swap="$4" captured="$5" extra="${6:-}" i j n
  : >"$f"
  if [ "$captured" != "none" ]; then
    printf 'captured: %s\n' "$captured" >>"$f"
  fi
  n=0
  i=1
  while [ "$i" -le "$openings" ]; do
    printf '### Opening %d\n' "$i" >>"$f"
    printf 'A candidate sentence.\n' >>"$f"
    j=1
    while [ "$j" -le 3 ] && [ "$n" -lt "$tlines" ]; do
      printf 'T%d: PASS fixture reason\n' "$j" >>"$f"
      n=$((n + 1))
      j=$((j + 1))
    done
    i=$((i + 1))
  done
  if [ "$swap" = "yes" ]; then
    printf 'The one-line swap edit: replace line 14 of build/briefing.md.\n' >>"$f"
  else
    printf 'No alternate instruction here.\n' >>"$f"
  fi
  if [ -n "$extra" ]; then
    printf '%s\n' "$extra" >>"$f"
  fi
}

# The run date is the LAST parameter on both, so the existing 3-argument and 2-argument calls keep
# their meaning; omitted, it is the same $RUN_DATE default check_file already applies.
expect_red() {
  local label="$1" f="$2" want="$3" run_date="${4:-$RUN_DATE}"
  check_file "$f" "$run_date"
  case "$FAILS" in
    *"$want"*) printf 'SELFTEST red OK   %-22s -> %s' "$label" "$FAILS" ;;
    *) printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "${FAILS:-<no failures>}" >&2
       return 1 ;;
  esac
}

expect_green() {
  local label="$1" f="$2" run_date="${3:-$RUN_DATE}"
  check_file "$f" "$run_date"
  if [ -n "$FAILS" ]; then
    printf 'SELFTEST FAIL: %s went red; got: %s\n' "$label" "$FAILS" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-22s -> no failures\n' "$label"
}

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main()`, its `cd "$ROOT"`, the relative
# sidecar path, the failure printing and the argument dispatch are exercised by nothing. That gap is
# booked in `docs/PLAN.md` section 8, and it is not hypothetical: it was `main()` on the real corpus
# that killed `tools/known-traps.sh` while its twelve in-process cases stayed green, because inside
# `OUT="$( ( f ) 2>&1 )"` bash suspends `set -e` and an in-process case cannot see an abort at all.
# The cases below copy this script into a fixture root and run it as a CHILD, with its own fully
# armed `set -euo pipefail` -- which is the invocation `docs/history/pipeline.md` and
# `tools/ci-gates.sh` actually make. The idiom is `tools/known-traps.sh:617`.
PROC_RC=0
PROC_OUT=""

# make_proc_root builds a fixture that looks like a checkout from this script's point of view: the
# script at tools/, and the sidecar directory main() reads relatively after its cd.
make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/output/review"
  cp "${BASH_SOURCE[0]}" "$root/tools/thesis-check.sh"
}

run_proc() {
  local root="$1" run_date="$2"
  PROC_RC=0
  PROC_OUT="$( BRIEF_RUN_DATE="$run_date" bash "$root/tools/thesis-check.sh" 2>&1 )" || PROC_RC=$?
  return 0
}

expect_proc_green() {
  local label="$1" root="$2" run_date="$3" want="$4"
  run_proc "$root" "$run_date"
  if [ "$PROC_RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: %s exited %s, want 0; got: %s\n' "$label" "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *"$want"*) printf 'SELFTEST proc OK  %-22s -> exit 0, %s\n' "$label" "$PROC_OUT" ;;
    *) printf 'SELFTEST FAIL: %s was green but did not print %s; got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

expect_proc_red() {
  local label="$1" root="$2" run_date="$3" want="$4"
  run_proc "$root" "$run_date"
  if [ "$PROC_RC" -eq 0 ]; then
    printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *"$want"*) printf 'SELFTEST proc red %-22s -> exit %s, %s\n' "$label" "$PROC_RC" "$want" ;;
    *) printf 'SELFTEST FAIL: %s went red with the wrong message; want %s, got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# SELFTEST_TMP is a global, and `tools/follower-counts.sh:316` already does this for the same
# reason: the EXIT trap runs after selftest()'s frame is gone, so a `local tmp` named in the trap is
# unset under `set -u` and the trap itself dies with `tmp: unbound variable`. That fires only on the
# failure path -- the one path where what the reader needs is the diagnosis and not a second error
# on top of it. Measured 2026-09-06, by mutating main() to ignore FAILS: the new child-process case
# below reported the mutation correctly and was then followed by the trap's own error.
SELFTEST_TMP=""

selftest() {
  # RUN and OLDER are fixed, not today: every existing case gets a fixture captured on RUN and is
  # checked against RUN, so the four shape assertions stay exactly as red or green as they were.
  local tmp RUN='2026-09-02' OLDER='2026-08-28'
  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/thesis-check-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  write_fixture "$tmp/good.md" 3 9 yes "$RUN"
  expect_green 'complete sidecar' "$tmp/good.md" "$RUN"

  expect_red 'missing file' "$tmp/absent.md" 'no thesis sidecar' "$RUN"

  : >"$tmp/empty.md"
  expect_red 'empty file' "$tmp/empty.md" 'no thesis sidecar' "$RUN"

  write_fixture "$tmp/two.md" 2 6 yes "$RUN"
  expect_red 'two openings' "$tmp/two.md" 'not three openings' "$RUN"

  write_fixture "$tmp/eight.md" 3 8 yes "$RUN"
  expect_red 'eight test results' "$tmp/eight.md" 'not nine test results' "$RUN"

  write_fixture "$tmp/noswap.md" 3 9 no "$RUN"
  expect_red 'no swap instruction' "$tmp/noswap.md" 'no swap instruction' "$RUN"

  write_fixture "$tmp/dated.md" 3 9 yes "$RUN"
  expect_green 'captured matches run' "$tmp/dated.md" "$RUN"

  write_fixture "$tmp/stale.md" 3 9 yes "$OLDER"
  expect_red 'captured is stale' "$tmp/stale.md" "is dated $OLDER but this run is $RUN" "$RUN"

  write_fixture "$tmp/nodate.md" 3 9 yes none
  expect_red 'captured absent' "$tmp/nodate.md" 'no captured: date' "$RUN"

  write_fixture "$tmp/baddate.md" 3 9 yes '2026-9-2'
  expect_red 'captured malformed' "$tmp/baddate.md" "is '2026-9-2', not YYYY-MM-DD" "$RUN"

  # This one is what makes the `^` anchor testable. The fixture has no captured line and one body
  # line that writes `captured:` mid-sentence, the way this sidecar's own prose names the snapshot
  # field. Drop the anchor and the sentence is read as the date, so the case goes red on the
  # malformed branch instead of the absent one and the selftest fails.
  write_fixture "$tmp/prose.md" 3 9 yes none \
    'The five cohort snapshots each carry a `captured:` field of their own.'
  expect_red 'captured in prose only' "$tmp/prose.md" 'no captured: date' "$RUN"

  # Two captured lines, the first stale and the second this run's: undecidable, not a preference
  # for the top one.
  write_fixture "$tmp/twodates.md" 3 9 yes "$OLDER" "captured: $RUN"
  expect_red 'two captured lines' "$tmp/twodates.md" 'more than one captured: date' "$RUN"

  # The override path: the same stale sidecar is green under its own run date, which is what
  # BRIEF_RUN_DATE=2026-09-02 does for the committed exemplar.
  expect_green 'stale under its own run' "$tmp/stale.md" "$OLDER"

  # P1 the whole script as a child, green. This is the first case in this file that proves the
  # script rather than the checking function: main(), the cd, the relative SIDECAR path, the
  # THESIS-OK line and the zero exit.
  local proc="$tmp/proc-green"
  make_proc_root "$proc"
  write_fixture "$proc/$SIDECAR" 3 9 yes "$RUN"
  expect_proc_green 'child run, good sidecar' "$proc" "$RUN" 'THESIS-OK'

  # P2 the same child on a stale sidecar: exit 1, the failure on the stream, and no THESIS-OK.
  # A script that printed THESIS-OK and then exited 1 anyway is the exact defect the sibling gate
  # shipped with, so the assertion is on the exit AND on the message.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  write_fixture "$proc/$SIDECAR" 3 9 yes "$OLDER"
  expect_proc_red 'child run, stale sidecar' "$proc" "$RUN" "is dated $OLDER but this run is $RUN"
  case "$PROC_OUT" in
    *THESIS-OK*) printf 'SELFTEST FAIL: a red child run printed THESIS-OK: %s\n' "$PROC_OUT" >&2
                 return 1 ;;
  esac

  # P3 the child with no sidecar at all, which is what a fresh clone that has never run Phase 7
  # looks like: red, and naming the relative path main() looked for.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child run, no sidecar' "$proc" "$RUN" "no thesis sidecar at $SIDECAR"

  rm -rf "$tmp"
  trap - EXIT
  if [ -e "$tmp" ]; then
    printf 'SELFTEST FAIL: residue left at %s\n' "$tmp" >&2
    return 1
  fi
  printf 'SELFTEST OK: 5 assertions proved red, complete sidecar green, 3 child-process cases (good sidecar green, stale red with no THESIS-OK, absent red), no residue at %s\n' "$tmp"
}

main() {
  cd "$ROOT"
  check_file "$SIDECAR"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  printf 'THESIS-OK\n'
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
