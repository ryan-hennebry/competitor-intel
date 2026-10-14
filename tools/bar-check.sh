#!/usr/bin/env bash
# The bar gate. It grades one `00-bar.md` against the format `references/stages/00-bar-loader.md`
# hands the stage-0 agent, collects every violation, and fails closed.
#
# WHY IT EXISTS. `46-spec.md` S2 Done asks that "the loader returns <=15 lines". The loader is a
# model call, so the template asking for 15 lines asserts nothing on its own: every stage after
# stage 0 reads that file first, the orchestrator reads it and nothing else in `quality-bar/`, and a
# bar that quietly grew to forty lines would put thirty lines of unread summary into every prompt of
# the run while the context budget -- goal 2, under 150k -- is spent on it. The cap is the whole
# point of the artefact, so it is a check and not a sentence in a template.
#
# WHAT IT GRADES, and why each is mechanical rather than left to the agent.
#
#   1. AT MOST 15 NON-EMPTY LINES. The cap.
#   2. NO PREAMBLE. The first non-empty line begins `BAR v`. A model asked for "no preamble" writes
#      "Here is the session bar:" often enough that the first line is worth pinning, and a bar
#      quoted into a prompt carries its preamble into every stage.
#   3. EVERY REQUIRED LABEL PRESENT. READER, GATE, TRUTH, REFUSE, BLOCKING, EXEMPLAR, and P1 to P8.
#      A bar missing a pillar is a bar that silently retires a rule for one run.
#
# WHAT IT DELIBERATELY DOES NOT GRADE. A fourth check was written and then dropped: no tool, file or
# stage name in the body, reusing `04-banned-patterns.tsv`'s `tool_name` row, on the argument that
# the bar is quoted into prompts that reach agents writing prose so RF7 travels with it. MEASURED
# 2026-09-18 against `quality-bar/fixtures/bar-green.md`, which is `21-quality-bar-system.md` §8's
# own example content: RED on `voice-lint` and `claims-check`, both in the BLOCKING line, where the
# design put them. The argument was wrong. RF7 governs the PAGE, and the bar is an internal artefact
# whose whole job is to tell agents which checks block. A row that reds the reference does not land,
# which is the same discipline D-001 and D-002 applied to three rows of the rule table.
#
# The green reference is `quality-bar/fixtures/bar-green.md`, which is the design's own example
# content. The red artefacts are built in the selftest, one defect each.
#
# `grep` is wrapped to `ugrep` on this machine, where a pattern starting with `--` parses as an
# option, so every pattern is passed after `-e`.
#
# PRECONDITION: the target file and `quality-bar/04-banned-patterns.tsv`. No network, no model call,
# no run directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAXLINES=15
# The default is the run's own bar. `BRIEF_ROOT` is `build/build.py:256`'s variable and the one the
# runbook sets, so this reads the same place the run writes. Unset, the target is the committed
# green reference, which is what makes a bare `bash tools/bar-check.sh` a gate CI can run.
DEFAULT_TARGET="${BRIEF_ROOT:+$BRIEF_ROOT/}00-bar.md"
[ -n "${BRIEF_ROOT:-}" ] || DEFAULT_TARGET="quality-bar/fixtures/bar-green.md"

REQUIRED_LABELS="READER GATE TRUTH REFUSE BLOCKING EXEMPLAR"
REQUIRED_PILLARS="P1 P2 P3 P4 P5 P6 P7 P8"

FAILS=""
NLINES=0
add_fail() { FAILS="${FAILS}$1"$'\n'; }

# check_file populates FAILS for one target and ALWAYS returns 0; the caller decides.
check_file() {
  local f="$1" first="" lbl
  FAILS=""; NLINES=0

  if [ ! -s "$f" ]; then
    add_fail "FAIL: no bar to grade at $f (missing or empty)"
    return 0
  fi

  NLINES="$(grep -c -e '[^[:space:]]' "$f" || true)"
  if [ "$NLINES" -gt "$MAXLINES" ]; then
    add_fail "FAIL: the bar runs $NLINES non-empty lines at $f, cap is $MAXLINES"
  fi

  first="$(grep -m1 -e '[^[:space:]]' "$f" || true)"
  case "$first" in
    'BAR v'*) : ;;
    *) add_fail "FAIL: the bar opens with a preamble at $f: $first" ;;
  esac

  for lbl in $REQUIRED_LABELS; do
    grep -q -e "^${lbl}" "$f" || add_fail "FAIL: the bar has no $lbl line at $f"
  done
  for lbl in $REQUIRED_PILLARS; do
    grep -q -e "\b${lbl}\b" "$f" || add_fail "FAIL: the bar never names pillar $lbl at $f"
  done

  return 0
}

# --- selftest -------------------------------------------------------------------------------------
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

expect_red() {
  local label="$1" f="$2" want="$3"
  check_file "$f"
  case "$FAILS" in
    *"$want"*) printf 'SELFTEST red OK   %-28s -> %s' "$label" "$FAILS" ;;
    *) printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "${FAILS:-<no findings>}" >&2
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
  printf 'SELFTEST green OK %-28s -> %s lines, no findings\n' "$label" "$NLINES"
}

SELFTEST_TMP=""

selftest() {
  local tmp cases=0 green line n

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/bar-check-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  green="$ROOT/quality-bar/fixtures/bar-green.md"
  if [ ! -s "$green" ]; then
    printf 'SELFTEST FAIL: no green reference at %s\n' "$green" >&2
    return 1
  fi

  # THE GREEN REFERENCE, and the assertion that must never be weakened to reach green. It is the
  # design's own example content; if it reds, the finding is the answer.
  expect_green 'committed bar-green.md' "$green"
  cases=$((cases + 1))

  # Every red case below is the green file plus ONE defect, so a red case proves the defect and not
  # the scaffolding.

  # 1. One line over the cap. Built by appending to the green file, so the defect is the COUNT and
  # nothing else: every label, the opener and the tool rule are untouched.
  cp "$green" "$tmp/over.md"
  n="$(grep -c -e '[^[:space:]]' "$green" || true)"
  while [ "$n" -le "$MAXLINES" ]; do
    printf 'NOTE  one more line of bar.\n' >>"$tmp/over.md"
    n=$((n + 1))
  done
  expect_red 'one line over the cap' "$tmp/over.md" 'cap is 15'
  cases=$((cases + 1))

  # The boundary from below: exactly at the cap is GREEN. Without this case the rule could be `<15`
  # and the suite would not notice.
  cp "$green" "$tmp/at-cap.md"
  n="$(grep -c -e '[^[:space:]]' "$green" || true)"
  while [ "$n" -lt "$MAXLINES" ]; do
    printf 'P1 P2 P3 P4 P5 P6 P7 padding line.\n' >>"$tmp/at-cap.md"
    n=$((n + 1))
  done
  expect_green 'exactly at the cap' "$tmp/at-cap.md"
  cases=$((cases + 1))

  # 2. A preamble line. One line added at the top, nothing else changed.
  : >"$tmp/preamble.md"
  printf 'Here is the session bar:\n' >>"$tmp/preamble.md"
  cat "$green" >>"$tmp/preamble.md"
  expect_red 'preamble before the stamp' "$tmp/preamble.md" 'opens with a preamble'
  cases=$((cases + 1))

  # 3. A missing label, and separately a missing pillar. Two different failures and two cases: a
  # single "something is missing" case cannot tell which loop is dead.
  grep -v -e '^TRUTH' "$green" >"$tmp/no-truth.md"
  expect_red 'missing TRUTH line' "$tmp/no-truth.md" 'has no TRUTH line'
  cases=$((cases + 1))

  grep -v -e '^P6 exact' "$green" >"$tmp/no-p6.md"
  expect_red 'missing pillar P6' "$tmp/no-p6.md" 'never names pillar P6'
  cases=$((cases + 1))

  # P8 is the pillar a cap once deferred (D-026); this case reds if REQUIRED_PILLARS drops it.
  grep -v -e '^P8 complete' "$green" >"$tmp/no-p8.md"
  expect_red 'missing pillar P8' "$tmp/no-p8.md" 'never names pillar P8'
  cases=$((cases + 1))

  # 4. An absent and an empty target are FAILURES, never a vacuous pass.
  expect_red 'absent bar' "$tmp/absent.md" 'no bar to grade'
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty bar' "$tmp/empty.md" 'no bar to grade'
  cases=$((cases + 1))

  # --- child-process cases ------------------------------------------------------------------------
  # `main()`, its `cd "$ROOT"`, the default target, the BAR-OK line and the non-zero exit are
  # exercised by nothing above: inside a command substitution bash suspends `set -e`.
  local proc="$tmp/proc" rc out
  mkdir -p "$proc/tools" "$proc/quality-bar/fixtures"
  cp "${BASH_SOURCE[0]}" "$proc/tools/bar-check.sh"
  cp "$green" "$proc/quality-bar/fixtures/bar-green.md"

  rc=0
  out="$( cd "$proc" && env -u BRIEF_ROOT bash "$proc/tools/bar-check.sh" 2>&1 )" || rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'SELFTEST FAIL: child on the default target exited %s; got: %s\n' "$rc" "$out" >&2
    return 1
  fi
  case "$out" in
    *BAR-OK*) printf 'SELFTEST proc OK  %-28s -> exit 0\n' 'child, default target' ;;
    *) printf 'SELFTEST FAIL: child was green but printed no token; got: %s\n' "$out" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))

  rc=0
  out="$( cd "$proc" && env -u BRIEF_ROOT bash "$proc/tools/bar-check.sh" "$tmp/over.md" 2>&1 )" || rc=$?
  if [ "$rc" -eq 0 ]; then
    printf 'SELFTEST FAIL: child on an over-cap bar exited 0; got: %s\n' "$out" >&2
    return 1
  fi
  case "$out" in
    *BAR-OK*) printf 'SELFTEST FAIL: a red child printed BAR-OK: %s\n' "$out" >&2
              return 1 ;;
  esac
  printf 'SELFTEST proc red %-28s -> exit %s\n' 'child, over-cap argument' "$rc"
  cases=$((cases + 1))

  # BRIEF_ROOT decides the default target, and a gate that reads the wrong directory is the failure
  # `build/build.py`'s GATE 4 had. Proved by pointing BRIEF_ROOT at a directory holding a BAD bar
  # while the green reference stays in place: red names the BRIEF_ROOT file, so it cannot be reading
  # the fallback.
  mkdir -p "$proc/run"
  cp "$tmp/over.md" "$proc/run/00-bar.md"
  rc=0
  out="$( cd "$proc" && BRIEF_ROOT=run bash "$proc/tools/bar-check.sh" 2>&1 )" || rc=$?
  if [ "$rc" -eq 0 ]; then
    printf 'SELFTEST FAIL: BRIEF_ROOT bar was over cap and the child exited 0; got: %s\n' "$out" >&2
    return 1
  fi
  case "$out" in
    *run/00-bar.md*) printf 'SELFTEST proc red %-28s -> exit %s, read run/00-bar.md\n' \
                       'child, BRIEF_ROOT redirect' "$rc" ;;
    *) printf 'SELFTEST FAIL: BRIEF_ROOT did not redirect the default target; got: %s\n' "$out" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  if [ -e "$tmp" ]; then
    printf 'SELFTEST FAIL: residue left at %s\n' "$tmp" >&2
    return 1
  fi
  printf 'SELFTEST OK: %s cases, the cap proved red at 16 and green at 15, the preamble, a missing label and a missing pillar each proved red on the green file plus one defect, absent and empty red, 3 child-process cases including the BRIEF_ROOT redirect naming the file it read, no residue at %s\n' \
    "$cases" "$tmp"
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
  printf 'BAR-OK (%s of %s lines in %s)\n' "$NLINES" "$MAXLINES" "$target"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
