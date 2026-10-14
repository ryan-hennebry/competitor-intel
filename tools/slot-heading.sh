#!/usr/bin/env bash
# THE SHELL SIDE OF slot_html(). Sourced, never run: it defines one function, `slot_heading`, which
# answers the question every gate downstream of the renderer has to ask -- what words did THIS run
# write over the section I grade?
#
# WHY IT IS A FILE AND NOT THREE COPIES. D3 made a section a stable slot id plus a heading the run
# chooses, and `build/build.py:slot_html()` resolves one through the other. Three gates outside the
# renderer ask the same question -- `tools/gap-test.sh` for the threat table, `tools/coverage-notes.sh`
# for its two sections, `tools/voice-lint.sh` for the same two -- and each one answered it with a
# literal until `S5T-verify-2.md` R3 measured the third search still finding another copy. One
# resolver means the record's shape, the BRIEF_ROOT fallback and the absent case are known in one
# place, which is the APOSD move `build/build.py` already made on its own side of the line.
#
# THREE ANSWERS, because a caller has three different things to say, and they are the states
# `slot_html()` names:
#
#   0  the record carries the slot; the heading is on stdout.
#   1  ABSENT -- the record does not carry the slot. NOT a failure. A menu slot nobody chose is not
#      a missing section, and a gate that grades it must say so and pass, never fail closed on a
#      section the brief was free not to carry.
#   2  NO READABLE RECORD -- there is no allocation record, or it is not JSON, or it carries no
#      `sections` list. This IS a failure for every caller: a gate that cannot find out which
#      section it grades must not report a pass.
#
# The caller decides. `unknown slot id` is deliberately not a state here: the catalogue, and so the
# set of legal slot ids, is graded by `tools/headings-check.sh`, and a caller passing an id no
# catalogue books gets the absent answer plus a red headings gate.
#
# WHERE THE RECORD IS, and it is the same fallback `run_cohort()` and `chosen_headings()` take:
# `$BRIEF_ROOT/headings.json` for a run, and `build/headings.json` when BRIEF_ROOT is unset, which
# is the build-session case of checking the exemplar in a checkout. A relative BRIEF_ROOT resolves
# against the repository root, the way `AGENTS.md` writes it.
#
# PRECONDITION: `python3`, for the JSON. The record is written by a run and its whitespace is not
# this repository's to assume, so it is parsed rather than grepped: a `sed` that half-reads a record
# hands a gate the wrong section and the gate then passes on it.

# SLOT_HEADING_ROOT lets a caller name the repository root; without it the root is this file's
# parent's parent, which is what a sourced-from-tools/ caller wants.
slot_heading_record() {
  local root="${SLOT_HEADING_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
  if [ -n "${BRIEF_ROOT:-}" ]; then
    case "$BRIEF_ROOT" in
      /*) printf '%s/headings.json\n' "$BRIEF_ROOT" ;;
      *)  printf '%s/%s/headings.json\n' "$root" "$BRIEF_ROOT" ;;
    esac
    return 0
  fi
  printf '%s/build/headings.json\n' "$root"
}

slot_heading() {
  local slot="$1" path out rc
  path="$(slot_heading_record)"
  out="$(SLOT_HEADING_WANT="$slot" python3 - "$path" <<'PY'
import json, os, sys

path, want = sys.argv[1], os.environ["SLOT_HEADING_WANT"]
try:
    data = json.loads(open(path, encoding="utf-8").read())
except OSError:
    sys.exit(2)
except ValueError:
    sys.exit(2)
if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
    sys.exit(2)
for entry in data["sections"]:
    if isinstance(entry, dict) and entry.get("slot") == want:
        head = entry.get("heading")
        if not isinstance(head, str) or not head.strip():
            sys.exit(2)
        sys.stdout.write(head)
        sys.exit(0)
sys.exit(1)
PY
  )" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    printf '%s\n' "$out"
  fi
  return "$rc"
}
