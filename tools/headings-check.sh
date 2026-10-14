#!/usr/bin/env bash
# The headings gate. It grades the slot catalogue against the two files that must agree with it,
# and then fails closed on any SLOT HEADING TEXT written into executable source anywhere outside
# `references/headings.json`.
#
# WHY THIS EXISTS. D3 split a section into a SLOT ID -- stable, `threat-landscape` -- and the
# HEADING a run writes over it, which the run's own `headings.json` records and which a menu slot's
# run may choose. `build/build.py` was fixed to resolve every section through that record. The fix
# did not travel: three consecutive verification passes went hunting for the copies that were left
# behind, and each pass found one more. `S5T-verify.md` found the renderer's; `S5T-verify-2.md`
# found `tools/gap-test.sh:159` and `:391` -- the FOURTH location, reached by the third search, and
# the same defect word for word: a brief that renders green under a run-written heading gets a
# fail-closed message from the gap ledger naming a heading it deliberately does not carry. A defect
# that survives three targeted searches is not one anybody finds by reading. It wants a detector,
# and this is it, so the hunt ends here and the next copy is found by a gate rather than by a
# reviewer.
#
# `tools/coupling-check.sh` is this gate's sibling and says at its own scan set why it stops where
# it does: "`tools/` and `build/` hold couplings too ... but a script's fixture paths are
# load-bearing code, not text a run applies, and grading them wants a different rule than this
# one." This is that different rule.
#
# WHAT IS GRADED, in three checks, and every one of them is counted in the OK line.
#
#   C1 THE CATALOGUE CONTRACT. `references/headings.json` is the machine-readable slot list;
#      `references/briefing-template.md` carries the same list as numbered prose; `build/build.py`
#      holds the spine as a tuple, because the spine is the decision and not the data. Those three
#      must agree, and `slot_catalogue()` raises where they do not -- inside a renderer CI cannot
#      run, which is why this check exists here. MEASURED, `S5T-verify-2.md` R5: with one default
#      heading mutated in the catalogue and the template untouched, `bash tools/ci-gates.sh` was
#      `CI-GATES OK (32 of 32)` while `python3 build/build.py` was exit 1 on the reconciliation. A
#      contract no repository check can see is a contract proved by hand on one macOS machine.
#      This check reads the same two files by the same rules, so a mutated, truncated or malformed
#      catalogue is red in CI and not only at render time.
#
#   C2 THE ALLOCATION RECORD. `build/headings.json` is the exemplar's own record, and it is graded
#      against the catalogue by `chosen_headings()`'s shape rules: every slot is a catalogue slot,
#      named once, in catalogue order; every spine slot present; a spine heading is its catalogue
#      literal, because the five sections a reader looks for are not the run's to rename. Same
#      reason as C1: those rules are reachable today only through the renderer.
#
#   C3 NO SLOT HEADING TEXT IN SOURCE. Every heading in the catalogue, AND every heading the
#      allocation record writes over a slot, matched as a whole phrase on a word boundary, in the
#      executable source of `build/` and `tools/`. A line that names one is a finding unless it is
#      LABELLED. This gate does not ban the phrase -- a selftest fixture has to write a heading,
#      because a fixture brief is a brief -- it requires the phrase to be labelled, and grades
#      everything the label does not reach. That is `tools/coupling-check.sh`'s ruling applied to
#      source, for the same reason: deleting the fixture loses the test. The record is in the list
#      because a menu slot's heading is the run's words, not the catalogue's: `S5T-verify-3.md` R8
#      measured the exemplar's own `say-do` heading, printed on page 3, green on a live line of
#      `tools/ai-smell.sh`, and that heading is the one an author copying from `build/briefing.md`
#      writes first.
#
#      ADVISORY, same scan, never a finding: a line naming a heading in another CASE or SPACING
#      (`threat landscape`, `Coverage  Notes`, `Threat  *Landscape`) is printed as `ADVISORY` and
#      counted in the OK line. It is advisory because a case-folded heading is also how a slot id
#      and a prose mention are spelled, so it cannot be a finding without reddening correct code.
#      A heading whose lower case IS a slot id (`sources`, `recommendations`) gets no advisory at
#      all: that text is the slot id the gate tells an author to write, and it is indistinguishable
#      from the lower-cased copy `voice-lint.sh` once carried.
#
# WHAT IS NOT GRADED, stated because a gate whose reach is unwritten gets trusted past it. Each is
# a CATEGORY, fixed by the file's syntax, and code written in good faith moves no line into one.
#
#   - COMMENTS. A `#` comment line is not graded. A comment cannot steer a run, and this
#     repository's source documents itself heavily: `build/build.py:467` explains WHY the heading
#     literal was removed and has to quote it to do so, and the paragraph you are reading would red
#     its own gate. A gate that reds its own explanation gets waived rather than obeyed, which is
#     the narrowing `tools/coupling-check.sh` applied to `gate`, `lint` and `G2`. The cost is the
#     bound below: a heading literal commented out and later uncommented is invisible here. What
#     counts as a comment is syntax, per language, so a comment can hide ITS OWN line and never
#     another one:
#       `.py`  a comment is where the tokenizer says one starts -- never inside a string -- and it
#              changes no parser state. `S5T-verify-3.md` R6 route A: two comment lines each
#              carrying `"""` used to toggle the docstring state, and silenced every line between
#              them, unlabelled and unbounded.
#       `.sh`  a line opening with ONE `#`. A line opening `##` IS GRADED: inside a heredoc it is a
#              Markdown heading, and a slot heading is always written `## `. Route C was a
#              `## <heading>` line in a heredoc, skipped as a comment.
#   - DOCSTRINGS, in `.py` only. A triple-quoted string in STATEMENT position -- a docstring, or a
#     bare string statement, at bracket depth 0 with nothing before it on its line and no `\` on
#     the line above -- is not graded; it is inert text. A triple-quoted string that is a VALUE --
#     assigned, passed, returned, inside brackets -- IS graded line by line, `#` lines included,
#     because that is how a Python tool holds a fixture brief (route B, `FIXTURE_BRIEF = """`).
#   - THE BRIEF AND THE TWO JSON FILES. `build/briefing.md`, `build/headings.json` and
#     `references/headings.json` are where a heading legitimately lives in full. They are graded by
#     C1 and C2 for their SHAPE, never for naming a heading.
#   - MARKDOWN. `references/*.md`, `docs/`, `quality-bar/` and `tools/fixtures/*.md` are prose and
#     data, not source. A template that tells an author what a section holds must name it.
#
# THE LABEL, and nothing else labels anything. Every label is a `#` comment carrying the word
# `heading-literal`, so `git grep -n heading-literal` lists every exemption of a graded line in the
# repository in one line, and no edit to a string, an array or a fixture body creates one. Every
# other ungraded line is syntax: a category above, or a construction WHAT IT CANNOT DO names.
#
#   LINE   ` # heading-literal: <reason>` at the END of a line that has content. It exempts that
#          one line. For a single message, label or assertion.
#   BLOCK  a line of its own reading `# heading-literal-block: <reason>`, closed by a line of its
#          own reading `# /heading-literal`. It exempts every line between them. This is the form a
#          fixture needs: a `\`-continued argument list cannot carry a comment between its lines,
#          and a `#` inside a heredoc is a Markdown heading rather than a comment, so the only
#          place a label can stand is outside the construct.
#
# THREE PROPERTIES BIND A LABEL, each one closing a route to a cheap green.
#
#   1. A REASON, of at least three letters after the colon. A bare marker is a label nobody has to
#      justify, and `56-verify.md` D1 measured what that is worth on the sibling gate: a whole
#      normative template exempted by the reason `x`.
#   2. A CLOSER. An unclosed block marker exempts NOTHING and is itself a finding. The alternative
#      -- running to the end of the file -- makes the widest possible exemption the easiest typo.
#   3. A BOUND. A block over REGION_MAX lines is refused and exempts nothing, so a marker cannot
#      swallow a file. MEASURED 2026-09-19, on the tree this gate was made green against: eleven
#      labels, ten of them LINE labels on an `FX_` fixture constant, and ONE block of 6 lines, over
#      the two headings `tools/scan-layer.sh` must write that open on the same word. The bound is
#      three times the only block anybody has needed. Raise it on a measurement, never to make a
#      label fit.
#   4. A CEILING. The labelled lines across the whole scan set may not exceed LABELLED_MAX. A bound
#      on one block does not bound a file: `S5T-verify-3.md` stacked four 19-line blocks in one
#      tool and the only signal was `11 -> 87 labelled line(s)` in an OK line nobody diffs. The
#      ceiling is this repository's own count, so a new label is a one-number edit to this file,
#      made in the same change as the label and reviewed with it.
#
# WHAT IT CANNOT DO. The heading list is the catalogue's defaults plus the committed record's
# headings, so the gate cannot see a heading neither names -- a tool keyed on a section this
# repository retired stays invisible, and that is the correct trade, because the catalogue is the
# definition of a section. It reads `build/headings.json` and never `$BRIEF_ROOT/headings.json`: a
# run writes a record and no source, so a run's headings have no source to be copied into. It
# grades executable lines only, per the categories above. And it is a TEXT gate, which syntax no
# good-faith author writes defeats: `GRADED="Coverage"" Notes"`; code after a docstring's closing
# quotes on the same line; a `\`-newline in a string or a nested-quote f-string, either of which
# makes the value string below read as a docstring; a `# <heading>` h1 in a `.sh` heredoc, which
# is a comment, and no slot is an h1. The gate defends against a copy, never against hiding one.
#
# PRECONDITION: none beyond the scanned tree existing, plus `python3` for the two JSON files. No
# network, no MKT1 call, no env var, no build artefact, no run directory, no browser. It never runs
# the renderer, which is the whole point: `tools/ci-gates.sh` cannot.
#
# Comment edits here follow ~/.claude/skills/writing-for-agents/SKILL.md (rule of 2026-09-18).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The four files of the contract and the two folders of the scan, named once so a diagnostic and
# the thing it grades cannot drift.
CATALOGUE="references/headings.json"
TEMPLATE="references/briefing-template.md"
RENDERER="build/build.py"
RECORD="build/headings.json"
SCAN_DIRS="build tools"
# C3 skips the paths listed here. It skipped two byte-for-byte copies of variant T's legacy build
# and verifier until S9 of the Globex redesign deleted both (no caller, design.md section 6); the
# list is empty, so every file under build/ and tools/ is graded.
C3_EXEMPT=""

# The bound on a labelled block, in lines. Named here and passed to awk as a variable, so the
# refusal message and the rule read the same number.
REGION_MAX=20

# The ceiling on labelled lines across the scan set: property 4 above. MEASURED on the tree R6-R8
# were fixed on: 12 -- the 11 `S5T-verify-3.md` counted, plus `tools/scan-layer.sh:625`, which the
# block there already covered and which names the record's `say-do` heading once C3 reads the
# record. Raise it only in the change that adds the label, never to make a scan pass.
LABELLED_MAX=12

FAILS=""

# Incremented once per check that ACTUALLY RUNS, so the OK line cannot claim three checks while one
# ran. Same intent as `CHECKS_RUN` in `tools/gap-test.sh` and `tools/scan-layer.sh`, derived from
# execution rather than from a table. On a fail-closed path it stays below 3 and main() says so.
CHECKS_RUN=0

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# --- the two JSON files --------------------------------------------------------------------------
# json_rows prints one TAB-separated record per entry and exits 3 with a reason on stderr when the
# file cannot be read as the thing it claims to be. Python and not awk because JSON is not a line
# format, and a hand-rolled parser that half-reads a malformed catalogue is the vacuous pass this
# check exists to end. An empty list is a failure, never zero rows.
json_rows() {
  python3 - "$1" "$2" <<'PY'
import json, sys

path, kind = sys.argv[1], sys.argv[2]
key, fid, fh = (("slots", "id", "default") if kind == "catalogue"
                else ("sections", "slot", "heading"))
try:
    raw = open(path, encoding="utf-8").read()
except OSError as exc:
    sys.stderr.write("cannot read it (%s)" % exc.strerror)
    sys.exit(3)
if not raw.strip():
    sys.stderr.write("it is empty")
    sys.exit(3)
try:
    data = json.loads(raw)
except ValueError as exc:
    sys.stderr.write("it is not JSON (%s)" % exc)
    sys.exit(3)
if not isinstance(data, dict) or not isinstance(data.get(key), list) or not data[key]:
    sys.stderr.write("it carries no non-empty `%s` list" % key)
    sys.exit(3)
out = []
for n, entry in enumerate(data[key], 1):
    if not isinstance(entry, dict):
        sys.stderr.write("entry %d is not an object" % n)
        sys.exit(3)
    fields = [fid, fh] + (["spine"] if kind == "catalogue" else [])
    for f in fields:
        if f not in entry:
            sys.stderr.write("entry %d carries no `%s`" % (n, f))
            sys.exit(3)
    sid, head = entry[fid], entry[fh]
    if not isinstance(sid, str) or not isinstance(head, str):
        sys.stderr.write("entry %d has a non-string `%s` or `%s`" % (n, fid, fh))
        sys.exit(3)
    if "\t" in sid + head or "\n" in sid + head:
        sys.stderr.write("entry %d carries a tab or a newline" % n)
        sys.exit(3)
    if kind == "catalogue":
        out.append("%s\t%s\t%s" % (sid, "spine" if entry["spine"] else "menu", head))
    else:
        out.append("%s\t%s" % (sid, head))
print("\n".join(out))
PY
}

# template_rows prints the same three fields, parsed out of the template's NUMBERED prose by the
# same regex `build/build.py:slot_catalogue()` uses. The numbering is the anchor, not the backticks:
# it is what lets the template name a section by name in its own prose without corrupting the parse.
template_rows() {
  awk '
    match($0, /^[0-9]+\. `[a-z][a-z0-9-]*`, (spine|menu), default heading `## [^`]+`/) {
      line = substr($0, RSTART, RLENGTH)
      n = split(line, part, "`")
      # part[2] is the id, part[4] the heading with its `## ` prefix, and part[3] carries the
      # word between the two backtick pairs.
      kind = (index(part[3], "spine") > 0) ? "spine" : "menu"
      head = part[4]
      sub(/^## /, "", head)
      printf "%s\t%s\t%s\n", part[2], kind, head
    }
  ' "$1"
}

# spine_ids prints the renderer's SPINE tuple, one id per line. Read out of the source rather than
# duplicated here: this gate asserts that three files agree, so a fourth copy of the answer would be
# a fourth thing to keep current.
spine_ids() {
  awk '
    /^SPINE = \(/ {
      n = split($0, part, "\"")
      for (i = 2; i < n + 1; i += 2) if (part[i] != "") print part[i]
      found = 1
    }
    END { if (!found) exit 4 }
  ' "$1"
}

# --- C1, the catalogue contract ------------------------------------------------------------------
check_catalogue() {
  local root="$1" rows err tmpl spine want ids id head kind n dup
  if ! rows="$(json_rows "$root/$CATALOGUE" catalogue 2>/dev/null)"; then
    err="$(json_rows "$root/$CATALOGUE" catalogue 2>&1 >/dev/null || true)"
    add_fail "FAIL: C1 no readable slot catalogue at $CATALOGUE: $err"
    return 0
  fi
  CHECKS_RUN=$((CHECKS_RUN + 1))

  ids=""
  while IFS=$'\t' read -r id kind head; do
    [ -n "$id" ] || continue
    case "$id" in
      *[!a-z0-9-]* | -* | "") add_fail "FAIL: C1 slot id \"$id\" in $CATALOGUE is not lower-case kebab" ;;
    esac
    case "$ids" in
      *" $id "*) add_fail "FAIL: C1 slot id \"$id\" is carried twice in $CATALOGUE" ;;
    esac
    ids="$ids $id "
    if [ -z "$head" ] || [ "$head" != "${head#\#}" ] || [ "$head" != "${head# }" ] \
       || [ "$head" != "${head% }" ] || [ "$head" != "${head//\`/}" ]; then
      add_fail "FAIL: C1 slot \"$id\" in $CATALOGUE carries \"$head\", which is not heading text alone"
    fi
  done <<EOF
$rows
EOF

  # The template's prose list, reconciled field for field. A catalogue and a template that disagree
  # are a contract with two answers, so the disagreement is reported with both sides quoted: the
  # author who mutated one of them is told which one the other expected.
  if [ ! -s "$root/$TEMPLATE" ]; then
    add_fail "FAIL: C1 no template at $TEMPLATE to reconcile $CATALOGUE against"
  else
    tmpl="$(template_rows "$root/$TEMPLATE")"
    if [ -z "$tmpl" ]; then
      add_fail "FAIL: C1 $TEMPLATE lists no numbered slot entry; the catalogue has nothing to reconcile against"
    elif [ "$tmpl" != "$rows" ]; then
      n=1
      while IFS= read -r want; do
        id="$(printf '%s\n' "$rows" | sed -n "${n}p")"
        if [ "$want" != "$id" ]; then
          add_fail "FAIL: C1 slot list entry $n disagrees: $TEMPLATE has \"$(printf '%s' "$want" | tr '\t' ' ')\", $CATALOGUE has \"$(printf '%s' "$id" | tr '\t' ' ')\""
        fi
        n=$((n + 1))
      done <<EOF
$tmpl
EOF
      dup="$(printf '%s\n' "$rows" | wc -l | tr -d ' ')"
      n="$(printf '%s\n' "$tmpl" | wc -l | tr -d ' ')"
      if [ "$dup" != "$n" ]; then
        add_fail "FAIL: C1 slot list length disagrees: $TEMPLATE lists $n, $CATALOGUE lists $dup"
      fi
    fi
  fi

  # The spine, against the renderer's tuple. `build/build.py:SPINE` is the decision (D3); the
  # catalogue's flags are the data. An edit that demotes a spine slot in the JSON alone is the
  # one-character change the tuple exists to disagree with.
  if [ ! -s "$root/$RENDERER" ]; then
    add_fail "FAIL: C1 no renderer at $RENDERER to read the spine from"
  elif ! spine="$(spine_ids "$root/$RENDERER")"; then
    add_fail "FAIL: C1 $RENDERER names no SPINE tuple; the spine has no second opinion"
  else
    want="$(printf '%s\n' "$rows" | awk -F'\t' '$2 == "spine" { print $1 }')"
    if [ "$spine" != "$want" ]; then
      add_fail "FAIL: C1 spine disagrees: $RENDERER fixes [$(printf '%s' "$spine" | tr '\n' ' ')], $CATALOGUE flags [$(printf '%s' "$want" | tr '\n' ' ')]"
    fi
  fi
  return 0
}

# --- C2, the allocation record -------------------------------------------------------------------
# The rules are `chosen_headings()`'s, applied to the committed record. They are re-stated here and
# not imported, because importing means `import markdown` and a macOS Chrome path -- the two
# failures `tools/ci-gates.sh` books for excluding the renderer. Both readers read the same two
# files: if they ever disagree the renderer raises, which is the loud direction.
check_record() {
  local root="$1" rows cat err slot head order pos want got spine id
  if [ ! -e "$root/$RECORD" ]; then
    add_fail "FAIL: C2 no allocation record at $RECORD"
    return 0
  fi
  if ! rows="$(json_rows "$root/$RECORD" record 2>/dev/null)"; then
    err="$(json_rows "$root/$RECORD" record 2>&1 >/dev/null || true)"
    add_fail "FAIL: C2 no readable allocation record at $RECORD: $err"
    return 0
  fi
  if ! cat="$(json_rows "$root/$CATALOGUE" catalogue 2>/dev/null)"; then
    add_fail "FAIL: C2 cannot grade $RECORD without a readable $CATALOGUE"
    return 0
  fi
  CHECKS_RUN=$((CHECKS_RUN + 1))

  order=""
  got=""
  while IFS=$'\t' read -r slot head; do
    [ -n "$slot" ] || continue
    want="$(printf '%s\n' "$cat" | awk -F'\t' -v s="$slot" '$1 == s { print $2 "\t" $3 }')"
    if [ -z "$want" ]; then
      add_fail "FAIL: C2 $RECORD carries slot \"$slot\", which is no slot in $CATALOGUE"
      continue
    fi
    case "$got" in
      *" $slot "*) add_fail "FAIL: C2 $RECORD carries slot \"$slot\" twice" ;;
    esac
    got="$got $slot "
    if [ -z "$head" ] || [ "$head" != "${head#\#}" ] || [ "$head" != "${head# }" ] \
       || [ "$head" != "${head% }" ]; then
      add_fail "FAIL: C2 $RECORD gives slot \"$slot\" the heading \"$head\", which is not heading text alone"
    fi
    if [ "${want%%$'\t'*}" = "spine" ] && [ "$head" != "${want#*$'\t'}" ]; then
      add_fail "FAIL: C2 $RECORD renames the spine slot \"$slot\" to \"$head\"; the spine heading is fixed as \"${want#*$'\t'}\""
    fi
    pos="$(printf '%s\n' "$cat" | awk -F'\t' -v s="$slot" '$1 == s { print NR }')"
    order="$order$pos "
  done <<EOF
$rows
EOF

  # Catalogue ORDER, not merely catalogue membership: a record that lists the sections a brief
  # carries in some other order is a brief whose sections are shuffled, and GATE 2 would grade the
  # page against it and pass.
  if [ -n "$order" ]; then
    want="$(printf '%s\n' $order | sort -n | tr '\n' ' ')"
    if [ "$(printf '%s\n' $order | tr '\n' ' ')" != "$want" ]; then
      add_fail "FAIL: C2 $RECORD lists its slots out of the $CATALOGUE order"
    fi
  fi
  # Every spine slot present. A record that drops one is a brief missing a section every reader
  # looks for, and nothing downstream of GATE 2 would say so.
  spine="$(printf '%s\n' "$cat" | awk -F'\t' '$2 == "spine" { print $1 }')"
  while IFS= read -r id; do
    [ -n "$id" ] || continue
    case "$got" in
      *" $id "*) : ;;
      *) add_fail "FAIL: C2 $RECORD carries no spine slot \"$id\"" ;;
    esac
  done <<EOF
$spine
EOF
  return 0
}

# --- C3, the source scan -------------------------------------------------------------------------
# One awk pass per tree, over every `.sh` and `.py` file in the two scan folders. `find -P` and not
# a glob, so a folder added under `build/` or `tools/` is scanned the day it appears; the sibling
# gate's note applies unchanged, that a symlink and an unscanned extension are outside the model.
check_source() {
  local root="$1" cat rec headfile listfile d line ids p
  if ! cat="$(json_rows "$root/$CATALOGUE" catalogue 2>/dev/null)"; then
    add_fail "FAIL: C3 cannot scan source without a readable $CATALOGUE; a scan with no headings passes on everything"
    return 0
  fi
  # The record's headings join the catalogue's (R8). An unreadable record is C2's finding, already
  # filed; the scan then runs on the catalogue alone rather than on nothing.
  rec="$(json_rows "$root/$RECORD" record 2>/dev/null || true)"
  headfile="$(mktemp "${TMPDIR:-/tmp}/headings-heads.XXXXXX")"
  listfile="$(mktemp "${TMPDIR:-/tmp}/headings-files.XXXXXX")"
  {
    printf '%s\n' "$cat" | awk -F'\t' 'NF >= 3 { print $3 }'
    printf '%s\n' "$rec" | awk -F'\t' 'NF >= 2 { print $2 }'
  } | awk 'NF && !seen[$0]++' >"$headfile"
  ids=" $(printf '%s\n' "$cat" | awk -F'\t' 'NF >= 3 { printf "%s ", $1 }')"
  : >"$listfile"
  for d in $SCAN_DIRS; do
    if [ -d "$root/$d" ]; then
      find -P "$root/$d" -type f \( -name '*.sh' -o -name '*.py' \) -print >>"$listfile"
    fi
  done
  for p in $C3_EXEMPT; do
    grep -vxF -- "$root/$p" "$listfile" >"$listfile.x" || true
    mv "$listfile.x" "$listfile"
  done
  if [ ! -s "$headfile" ] || [ ! -s "$listfile" ]; then
    add_fail "FAIL: C3 nothing to scan: $(wc -l <"$headfile" | tr -d ' ') heading(s) over $(wc -l <"$listfile" | tr -d ' ') file(s)"
    rm -f "$headfile" "$listfile"
    return 0
  fi
  CHECKS_RUN=$((CHECKS_RUN + 1))

  # `set -f` for the argument expansion only: the file list is a file, and a path in it must reach
  # awk as written. Restored immediately, the way `tools/ci-gates.sh` restores it.
  set -f
  # shellcheck disable=SC2046
  SCAN_OUT="$( LC_ALL=C awk -v headfile="$headfile" -v regionmax="$REGION_MAX" -v root="$root/" \
                   -v ids="$ids" -v sq="'" '
    # names() is index()-based and not a regex, so a heading carrying a comma, a bracket or any
    # other metacharacter is matched as the literal phrase it is. The boundary is a LETTER on
    # either side: `Sources` in `Sources 2` is the heading, `Sourcesome` is not.
    function names(line, h,   p, pos, before, after) {
      p = 1
      while (p <= length(line)) {
        pos = index(substr(line, p), h)
        if (pos == 0) return 0
        pos = p + pos - 1
        before = (pos == 1) ? "" : substr(line, pos - 1, 1)
        after = substr(line, pos + length(h), 1)
        if (before !~ /[A-Za-z]/ && after !~ /[A-Za-z]/) return 1
        p = pos + 1
      }
      return 0
    }
    function rel(f) { sub("^" root, "", f); return f }
    # pyscan() TOKENIZES one physical line of python, starting in the string state the line above
    # left, and sets four globals. PYIN: the triple-quote delimiter still open at the end of the
    # line, "" for none. PYOPEN: the column of the last triple quote this line opened, 0 for none,
    # with PYODEPTH the bracket depth there. PYDEPTH: the bracket depth, carried across lines.
    # PYLAST: the last non-blank character of code seen so far, which a comment never updates.
    # A tokenizer and not a count of triple quotes, because a count cannot tell a triple quote in
    # a comment from one in code: that was R6 route A.
    function pyscan(s,   i, n, c, q, t) {
      i = 1; n = length(s); q = ""; PYOPEN = 0
      while (i <= n) {
        c = substr(s, i, 1)
        if (PYIN != "") {
          if (c == "\\") { i += 2; continue }
          if (substr(s, i, 3) == PYIN) { PYIN = ""; PYLAST = c; i += 3; continue }
          i++; continue
        }
        if (q != "") {
          if (c == "\\") { i += 2; continue }
          if (c == q) { q = ""; PYLAST = c }
          i++; continue
        }
        if (c == "#") return
        t = substr(s, i, 3)
        if (t == TDQ || t == TSQ) { PYIN = t; PYOPEN = i; PYODEPTH = PYDEPTH; PYLAST = c; i += 3; continue }
        if (c == "\"" || c == sq) { q = c; PYLAST = c; i++; continue }
        if (c ~ /[(\[{]/) PYDEPTH++
        else if (c ~ /[)\]}]/ && PYDEPTH > 0) PYDEPTH--
        if (c !~ /[ \t]/) PYLAST = c
        i++
      }
    }
    # norm() is the advisory form of a line or a heading: lower case, and a run of blanks -- with
    # any regex quantifier or `\s` in it -- read as one space.
    function norm(s) {
      s = tolower(s)
      gsub(/\\s/, " ", s)
      gsub(/\[\[:space:\]\]/, " ", s)
      gsub(/[ \t][ \t*+?]*/, " ", s)
      return s
    }
    # closefile() is the ONE place an open block dies, and it runs both at the next file and at EOF.
    # MEASURED while building this: reporting the unclosed marker at the file boundary without
    # flushing what it covered lost every line the refused label was hiding, which is the failure
    # the refusal exists to prevent.
    function closefile(f,   j) {
      if (open > 0) {
        printf "HEADINGS  %s:%d: block label is never closed; it exempts nothing\n", rel(f), openline
        nfind++
        for (j = 1; j <= nheld; j++) { print HELD[j]; nfind++ }
      }
      nheld = 0
      open = 0
    }
    BEGIN {
      nh = 0; nn = 0
      TDQ = "\"\"\""; TSQ = sq sq sq
      while ((getline h < headfile) > 0) if (h != "") {
        HEAD[++nh] = h
        # A heading whose lower case is a slot id gets no advisory: see the header.
        if (index(ids, " " tolower(h) " ") == 0) NHEAD[++nn] = norm(h)
      }
      close(headfile)
    }
    FNR == 1 {
      # Per-file state. PYIN/PYKIND track a python triple-quoted string and whether it is a
      # docstring; `open` a block label; `nfiles` the files actually opened, so an empty scan
      # cannot read as a clean one. A label never reaches past the file it opens in.
      closefile(prevfile)
      if (PYIN != "") {
        printf "HEADINGS  %s: unbalanced \"\"\" quoting; the file cannot be classified\n", rel(prevfile)
        nfind++
      }
      open = 0; PYIN = ""; PYKIND = ""; PYDEPTH = 0; PYLAST = ""
      ispy = (FILENAME ~ /\.py$/); nfiles++
      prevfile = FILENAME
    }
    {
      line = $0
      prevfile = FILENAME
      bare = line
      sub(/^[ \t]+/, "", bare)

      # The two labels, read BEFORE anything is graded, and read on comment lines only -- a label
      # is a comment and nothing else is a label.
      if (bare ~ /^#[ \t]*heading-literal-block:/) {
        reason = bare
        sub(/^#[ \t]*heading-literal-block:[ \t]*/, "", reason)
        gsub(/[^A-Za-z]/, "", reason)
        if (length(reason) < 3) {
          printf "HEADINGS  %s:%d: block label carries no reason; it exempts nothing\n", rel(FILENAME), FNR
          nfind++
          next
        }
        if (open > 0) {
          printf "HEADINGS  %s:%d: block label opens inside the label opened at line %d\n", rel(FILENAME), FNR, openline
          nfind++
          next
        }
        open = 1; openline = FNR
        next
      }
      if (bare ~ /^#[ \t]*\/heading-literal[ \t]*$/) {
        if (open > 0 && FNR - openline > regionmax) {
          printf "HEADINGS  %s:%d: labelled block runs %d lines, over the bound of %d; it exempts nothing\n", rel(FILENAME), openline, FNR - openline, regionmax
          nfind++
          for (i = 1; i <= nheld; i++) { print HELD[i]; nfind++ }
        } else {
          # Counted as exempt only HERE, where the label is known to have been accepted: a line
          # under a refused label is a finding, and counting it as an opt-out would report the
          # exemption twice and the finding once.
          nexlines += nheld
        }
        nheld = 0
        open = 0
        next
      }

      # The categories of the header, WHAT IS NOT GRADED. In `.py`: a docstring line is skipped, a
      # value-string line is graded whole, and a comment line is skipped only OUTSIDE a string. A
      # one-line docstring opens and closes on its own line and is graded like code; an unbalanced
      # file is reported above rather than silently exempted from its typo to its end.
      if (ispy) {
        wasin = PYIN; waskind = PYKIND; prevlast = PYLAST
        pyscan($0)
        if (PYOPEN > 0 && PYIN != "") {
          PYKIND = (substr($0, 1, PYOPEN - 1) ~ /^[ \t]*[rRbBuUfF]*$/ && PYODEPTH == 0 \
                    && prevlast != "\\") ? "doc" : "str"
        }
        if ((wasin != "" && waskind == "doc") || (PYIN != "" && PYKIND == "doc")) next
        if (wasin == "" && bare ~ /^#/) next
      } else if (bare ~ /^#([^#]|$)/) next
      if (bare == "") next

      # The line label, at the end of a line with content. Its reason is graded WHERE IT WOULD DO
      # WORK and not before: a label on a line that names no heading exempts nothing already, and
      # grading it there reds this script own selftest fixtures, which write the grammar as data.
      labelled = 0
      reason = line
      if (line ~ /#[ \t]*heading-literal:/) {
        sub(/^.*#[ \t]*heading-literal:[ \t]*/, "", reason)
        gsub(/[^A-Za-z]/, "", reason)
        labelled = (length(reason) >= 3) ? 1 : -1
      }

      hit = 0
      for (i = 1; i <= nh; i++) {
        if (names(line, HEAD[i])) {
          hit = 1
          if (labelled == -1) {
            printf "HEADINGS  %s:%d: line label carries no reason; it exempts nothing\n", rel(FILENAME), FNR
            nfind++
            break
          }
          if (labelled == 1 && open == 0) { nexlines++; break }
          if (open > 0) {
            HELD[++nheld] = sprintf("HEADINGS  %s:%d: names the slot heading \"%s\", inside the block label above", rel(FILENAME), FNR, HEAD[i])
            break
          }
          printf "HEADINGS  %s:%d: names the slot heading \"%s\"; resolve the section by slot id through the run allocation record, or label the line\n", rel(FILENAME), FNR, HEAD[i]
          nfind++
          break
        }
      }
      # The advisory pass, on a line the exact pass found nothing on and no label covers.
      if (!hit && labelled == 0 && open == 0 && nn > 0) {
        low = norm(line)
        for (i = 1; i <= nn; i++) {
          if (names(low, NHEAD[i])) {
            printf "ADVISORY  %s:%d: names \"%s\" in another case or spacing; if it grades a section, resolve it by slot id\n", rel(FILENAME), FNR, NHEAD[i]
            nadv++
            break
          }
        }
      }
    }
    END {
      closefile(prevfile)
      if (PYIN != "") {
        printf "HEADINGS  %s: unbalanced \"\"\" quoting; the file cannot be classified\n", rel(prevfile)
        nfind++
      }
      if (nh == 0)     { printf "HEADINGS  (catalogue): no heading to look for; a scan with no headings passes on everything\n"; nfind++ }
      if (nfiles == 0) { printf "HEADINGS  (scan): no source file scanned; a gate that read nothing cannot pass\n"; nfind++ }
      printf "C3 %d %d %d %d\n", nfiles, nexlines, nfind, nadv
    }
  ' $(cat "$listfile") </dev/null )"
  set +f
  rm -f "$headfile" "$listfile"

  SCAN_FILES="$(printf '%s\n' "$SCAN_OUT" | awk '$1 == "C3" { print $2 }')"
  SCAN_EXEMPT="$(printf '%s\n' "$SCAN_OUT" | awk '$1 == "C3" { print $3 }')"
  SCAN_ADVISORY="$(printf '%s\n' "$SCAN_OUT" | awk '$1 == "C3" { print $5 }')"
  while IFS= read -r line; do
    case "$line" in
      "HEADINGS  "*) add_fail "FAIL: C3 ${line#HEADINGS  }" ;;
      "ADVISORY  "*) ADVISORIES="${ADVISORIES}${line}"$'\n' ;;
    esac
  done <<EOF
$SCAN_OUT
EOF
  if [ "${SCAN_EXEMPT:-0}" -gt "$LABELLED_MAX" ]; then
    add_fail "FAIL: C3 $SCAN_EXEMPT labelled line(s) across the scan set, over the ceiling of $LABELLED_MAX; a new label raises LABELLED_MAX in this file in the same change, with the reason"
  fi
  return 0
}

# --- the check -----------------------------------------------------------------------------------
SCAN_OUT=""
SCAN_FILES=0
SCAN_EXEMPT=0
SCAN_ADVISORY=0
ADVISORIES=""

check_all() {
  local root="$1"
  FAILS=""
  CHECKS_RUN=0
  SCAN_FILES=0
  SCAN_EXEMPT=0
  SCAN_ADVISORY=0
  ADVISORIES=""
  if [ ! -d "$root" ]; then
    add_fail "FAIL: no tree to grade at $root"
    return 0
  fi
  check_catalogue "$root"
  check_record "$root"
  check_source "$root"
  return 0
}

scan() {
  local root="$1" n
  check_all "$root"
  # THREE CHECKS OR IT IS NOT A PASS. An assertion and not a printed number, for the reason
  # `tools/coverage-notes.sh` measured: interpolating the counter into the OK line does not on its
  # own earn the claim, because the OK line is reached only when FAILS is empty.
  if [ -z "$FAILS" ] && [ "$CHECKS_RUN" -ne 3 ]; then
    add_fail "FAIL: $CHECKS_RUN of 3 checks ran; a partial grade is not a pass"
  fi
  printf '%s' "$ADVISORIES"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS"
    n="$(printf '%s' "$FAILS" | grep -c . || true)"
    printf 'HEADINGS-CHECK RED (%s finding(s); %s checks ran, %s source file(s) scanned, %s labelled line(s))\n' \
      "$n" "$CHECKS_RUN" "$SCAN_FILES" "$SCAN_EXEMPT"
    return 1
  fi
  printf 'HEADINGS-CHECK-OK (%s checks, %s source file(s) scanned, %s labelled line(s), 0 findings, %s advisory)\n' \
    "$CHECKS_RUN" "$SCAN_FILES" "$SCAN_EXEMPT" "${SCAN_ADVISORY:-0}"
  return 0
}

# --- selftest ------------------------------------------------------------------------------------
# EVERY CASE RUNS THIS SCRIPT FILE AS A CHILD against a fixture tree of its own, for the reason
# `tools/coupling-check.sh` and `tools/ci-gates.sh` both book: inside `OUT="$( f )"` bash suspends
# `set -e`, so an in-process case is blind to an abort by construction. A fixture tree also means no
# case reads the repository, so no case can be turned green by an edit somewhere else.
SELFTEST_TMP=""
NRED=0
NGREEN=0
RC=0
OUT=""

write_lines() {
  local f="$1" line
  shift
  mkdir -p "$(dirname "$f")"
  : >"$f"
  for line in "$@"; do
    printf '%s\n' "$line" >>"$f"
  done
}

# new_root builds the smallest tree that passes all three checks: a two-slot catalogue, a template
# whose prose agrees with it, a renderer holding the matching SPINE tuple, a record that allocates
# both slots, and one clean script in the scan set. Every red case below is this tree with ONE
# thing changed, so a case cannot go red for two reasons at once.
#
# The fixture headings are deliberately NOT this repository's: `Section One` and `Section Two` are
# what make the catalogue the source of the heading list. A fixture built from the real catalogue
# would pass a gate whose heading list was hardcoded.
new_root() {
  local root="$1"
  write_lines "$root/$CATALOGUE" \
    '{' \
    '  "slots": [' \
    '    { "id": "alpha", "spine": true,  "default": "Section One" },' \
    '    { "id": "beta",  "spine": false, "default": "Section Two" }' \
    '  ]' \
    '}'
  write_lines "$root/$TEMPLATE" \
    '# Template' '' \
    '1. `alpha`, spine, default heading `## Section One`: the first thing.' \
    '2. `beta`, menu, default heading `## Section Two`: the second thing.'
  write_lines "$root/$RENDERER" \
    '#!/usr/bin/env python3' \
    '"""A stub renderer."""' \
    'SPINE = ("alpha",)'
  write_lines "$root/$RECORD" \
    '{' \
    '  "sections": [' \
    '    { "slot": "alpha", "heading": "Section One" },' \
    '    { "slot": "beta",  "heading": "Whatever The Run Chose" }' \
    '  ]' \
    '}'
  write_lines "$root/tools/clean.sh" \
    '#!/usr/bin/env bash' \
    '# A comment may name Section One, because a comment cannot steer a run.' \
    'slot_heading alpha'
}

run_child() {
  local arg1="${1:-}" arg2="${2:-}"
  RC=0
  if [ -n "$arg2" ]; then
    OUT="$( bash "${BASH_SOURCE[0]}" "$arg1" "$arg2" 2>&1 )" || RC=$?
  elif [ -n "$arg1" ]; then
    OUT="$( bash "${BASH_SOURCE[0]}" "$arg1" 2>&1 )" || RC=$?
  else
    OUT="$( bash "${BASH_SOURCE[0]}" 2>&1 )" || RC=$?
  fi
  return 0
}

expect_green() {
  local label="$1" root="$2"
  run_child --check "$root"
  if [ "$RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: %s exited %s, want 0; got: %s\n' "$label" "$RC" "$OUT" >&2
    return 1
  fi
  case "$OUT" in
    *"HEADINGS-CHECK-OK"*) NGREEN=$((NGREEN + 1)); printf 'SELFTEST green OK %-44s\n' "$label" ;;
    *) printf 'SELFTEST FAIL: %s was green without the OK line; got: %s\n' "$label" "$OUT" >&2
       return 1 ;;
  esac
}

expect_red() {
  local label="$1" root="$2" want="$3"
  run_child --check "$root"
  if [ "$RC" -eq 0 ]; then
    printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "$OUT" >&2
    return 1
  fi
  case "$OUT" in
    *"$want"*) NRED=$((NRED + 1))
               printf 'SELFTEST red OK   %-44s -> exit %s\n' "$label" "$RC" ;;
    *) printf 'SELFTEST FAIL: %s went red with the wrong message; want %s, got: %s\n' \
         "$label" "$want" "$OUT" >&2
       return 1 ;;
  esac
}

selftest() {
  local tmp root i line
  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/headings-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # G1 the fixture tree is green. The working tree is graded by its own row in `tools/ci-gates.sh`,
  # `headings-check on the working tree`, and never here, so this selftest stays a statement about
  # the gate and a red repository reds that row alone.
  root="$tmp/green"; new_root "$root"
  expect_green 'the fixture tree' "$root"

  # --- C1, the catalogue contract ----------------------------------------------------------------
  # C1a a MUTATED default heading, the mutation `S5T-verify-2.md` R5 measured invisible to CI.
  root="$tmp/c1-mutated"; new_root "$root"
  sed 's/"Section Two"/"Section The Second"/' "$root/$CATALOGUE" >"$root/$CATALOGUE.x"
  mv "$root/$CATALOGUE.x" "$root/$CATALOGUE"
  expect_red 'C1 catalogue default mutated' "$root" 'C1 slot list entry 2 disagrees'

  # C1b a TRUNCATED catalogue: the template still lists both.
  root="$tmp/c1-truncated"; new_root "$root"
  write_lines "$root/$CATALOGUE" \
    '{' \
    '  "slots": [' \
    '    { "id": "alpha", "spine": true,  "default": "Section One" }' \
    '  ]' \
    '}'
  expect_red 'C1 catalogue truncated' "$root" 'C1 slot list length disagrees'

  # C1c MALFORMED JSON. Fail closed and say which file, never a vacuous zero rows.
  root="$tmp/c1-malformed"; new_root "$root"
  write_lines "$root/$CATALOGUE" '{ "slots": [ { "id": "alpha",'
  expect_red 'C1 catalogue malformed' "$root" 'C1 no readable slot catalogue'

  # C1d an EMPTY catalogue file, and C1e a catalogue whose list is empty. Two different ways to read
  # nothing, both of which a scan would otherwise pass on.
  root="$tmp/c1-empty"; new_root "$root"; : >"$root/$CATALOGUE"
  expect_red 'C1 catalogue empty' "$root" 'it is empty'
  root="$tmp/c1-nolist"; new_root "$root"; write_lines "$root/$CATALOGUE" '{ "slots": [] }'
  expect_red 'C1 catalogue lists no slot' "$root" 'carries no non-empty `slots` list'

  # C1f the SPINE flipped in the JSON alone -- the one-character edit `build/build.py`'s tuple
  # exists to disagree with.
  root="$tmp/c1-spine"; new_root "$root"
  sed 's/"id": "beta",  "spine": false/"id": "beta",  "spine": true/' "$root/$CATALOGUE" >"$root/x"
  mv "$root/x" "$root/$CATALOGUE"
  expect_red 'C1 spine flipped in the catalogue' "$root" 'C1 spine disagrees'

  # C1g the template carrying no numbered list at all, which is how a reformat silently retires the
  # reconciliation.
  root="$tmp/c1-noprose"; new_root "$root"
  write_lines "$root/$TEMPLATE" '# Template' '' 'The slots are described in prose somewhere else.'
  expect_red 'C1 template lists no slot' "$root" 'lists no numbered slot entry'

  # C1h a slot id that is not an id, and C1i a heading carrying its own `##` marker.
  root="$tmp/c1-badid"; new_root "$root"
  sed 's/"id": "beta"/"id": "Beta Two"/' "$root/$CATALOGUE" >"$root/x"; mv "$root/x" "$root/$CATALOGUE"
  expect_red 'C1 slot id is not kebab' "$root" 'is not lower-case kebab'
  root="$tmp/c1-badhead"; new_root "$root"
  sed 's/"default": "Section Two"/"default": "## Section Two"/' "$root/$CATALOGUE" >"$root/x"
  mv "$root/x" "$root/$CATALOGUE"
  expect_red 'C1 heading carries its own marker' "$root" 'which is not heading text alone'

  # --- C2, the allocation record -----------------------------------------------------------------
  # C2a an unknown slot, C2b a renamed SPINE heading, C2c a missing spine slot, C2d slots out of
  # catalogue order, C2e a slot twice, C2f no record at all.
  root="$tmp/c2-unknown"; new_root "$root"
  sed 's/"slot": "beta"/"slot": "betas"/' "$root/$RECORD" >"$root/x"; mv "$root/x" "$root/$RECORD"
  expect_red 'C2 record names an unknown slot' "$root" 'which is no slot in'

  root="$tmp/c2-rename"; new_root "$root"
  sed 's/"slot": "alpha", "heading": "Section One"/"slot": "alpha", "heading": "My Own Words"/' \
    "$root/$RECORD" >"$root/x"; mv "$root/x" "$root/$RECORD"
  expect_red 'C2 record renames a spine heading' "$root" 'renames the spine slot'

  root="$tmp/c2-nospine"; new_root "$root"
  write_lines "$root/$RECORD" '{ "sections": [ { "slot": "beta", "heading": "Section Two" } ] }'
  expect_red 'C2 record drops a spine slot' "$root" 'carries no spine slot "alpha"'

  root="$tmp/c2-order"; new_root "$root"
  write_lines "$root/$RECORD" \
    '{ "sections": [ { "slot": "beta", "heading": "Section Two" },' \
    '                { "slot": "alpha", "heading": "Section One" } ] }'
  expect_red 'C2 record is out of catalogue order' "$root" 'out of the references/headings.json order'

  root="$tmp/c2-twice"; new_root "$root"
  write_lines "$root/$RECORD" \
    '{ "sections": [ { "slot": "alpha", "heading": "Section One" },' \
    '                { "slot": "alpha", "heading": "Section One" } ] }'
  expect_red 'C2 record carries a slot twice' "$root" 'twice'

  root="$tmp/c2-absent"; new_root "$root"; rm -f "$root/$RECORD"
  expect_red 'C2 no record at all' "$root" 'C2 no allocation record'

  # --- C3, the source scan -----------------------------------------------------------------------
  # C3a the defect itself: a heading literal in an executable line. This is `tools/gap-test.sh:159`
  # in one line -- a section resolved by the words on the page rather than by its slot id.
  root="$tmp/c3-literal"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' \
    'GRADED_SECTION="Section One"'
  expect_red 'C3 a heading literal in source' "$root" 'tools/grader.sh:2: names the slot heading "Section One"'

  # C3b the SECOND heading, so a gate keyed on one slot cannot pass the case.
  root="$tmp/c3-second"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'awk "/^## Section Two/ { print }"'
  expect_red 'C3 the other heading in source' "$root" 'names the slot heading "Section Two"'

  # C3c a heading in a `.py` file, and C3d the same phrase inside a python DOCSTRING, which is the
  # exemption the renderer's own `WHY A SLOT AND NOT A HEADING LITERAL` paragraph needs.
  root="$tmp/c3-py"; new_root "$root"
  write_lines "$root/build/grade.py" 'head = "Section One"'
  expect_red 'C3 a heading literal in python' "$root" 'build/grade.py:1: names the slot heading'
  root="$tmp/c3-docstring"; new_root "$root"
  write_lines "$root/build/grade.py" \
    'def f():' \
    '    """Searching for Section One is what this stopped doing.' \
    '' \
    '    Section One is named twice on purpose, across a blank line."""' \
    '    return 1'
  expect_green 'C3 a python docstring is not graded' "$root"

  # C3e an UNBALANCED `"""`, which would otherwise exempt a file from its typo to its end.
  root="$tmp/c3-unbalanced"; new_root "$root"
  write_lines "$root/build/grade.py" 'x = """open' 'head = "Section One"'
  expect_red 'C3 unbalanced triple quotes' "$root" 'unbalanced'

  # C3f the word boundary, both directions: a LONGER word carrying the heading is not the heading,
  # and a heading followed by punctuation is.
  root="$tmp/c3-boundary"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'x="Section Ones"' 'y="SubSection One"'
  expect_green 'C3 a longer word is not the heading' "$root"
  root="$tmp/c3-punct"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'x="## Section One, the first"'
  expect_red 'C3 a heading closed by punctuation' "$root" 'names the slot heading "Section One"'

  # C3g a comment is not graded; C3h a commented-out literal is not graded either, which is the
  # bound this gate states rather than hides.
  root="$tmp/c3-comment"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' '# GRADED_SECTION="Section One"' 'true'
  expect_green 'C3 a comment naming a heading' "$root"

  # --- R6, a comment hides its own line and never another ----------------------------------------
  # R6a route A: two comment lines carrying `"""` bracket a live literal. Before the tokenizer they
  # toggled the docstring state and the literal between them was never read.
  root="$tmp/r6-comment-fence"; new_root "$root"
  write_lines "$root/build/grade.py" \
    '# Matching is by """ fences, per the parser note.' \
    'SECTION = "Section One"' \
    '# Close the """ fence note above.'
  expect_red 'R6 comment lines cannot open a docstring' "$root" 'build/grade.py:2: names the slot heading "Section One"'
  # R6b the same fence carried in TRAILING comments on code lines.
  root="$tmp/r6-trailing-fence"; new_root "$root"
  write_lines "$root/build/grade.py" \
    'N = 1  # parser note: """ fences' \
    'SECTION = "Section One"' \
    'M = 2  # close the """ note'
  expect_red 'R6 a trailing comment cannot open one' "$root" 'build/grade.py:2: names the slot heading "Section One"'
  # R6b2 ONE comment carrying `"""` opens nothing either. Without it the two cases above stay red
  # under a scanner that reads a comment as a string opener, since a string is graded too; this is
  # the case that goes red on it, as an unbalanced file.
  root="$tmp/r6-lone-fence"; new_root "$root"
  write_lines "$root/build/grade.py" '# a docstring opens with """ and so on' 'X = 1'
  expect_green 'R6 a lone comment fence opens nothing' "$root"
  # R6c route B: a triple-quoted VALUE is graded, `##` lines included -- the ordinary way a python
  # tool holds a fixture brief. R6d the same value passed as an argument, where the `"""` opens the
  # line and only the bracket depth says it is not a docstring.
  root="$tmp/r6-value-string"; new_root "$root"
  write_lines "$root/build/grade.py" 'FIXTURE_BRIEF = """' '## Section One' 'Rows follow.' '"""'
  expect_red 'R6 a triple-quoted value is graded' "$root" 'build/grade.py:2: names the slot heading "Section One"'
  root="$tmp/r6-argument-string"; new_root "$root"
  write_lines "$root/build/grade.py" 'MSG = check(' '    """' '    no Section Two in the brief' '    """)'
  expect_red 'R6 a triple-quoted argument is graded' "$root" 'build/grade.py:3: names the slot heading "Section Two"'
  # R6e a MODULE docstring with a string prefix is still a docstring, so the tokenizer did not buy
  # route B by grading every triple quote.
  root="$tmp/r6-module-doc"; new_root "$root"
  write_lines "$root/build/grade.py" '#!/usr/bin/env python3' 'r"""The Section One grader.' '' 'Section Two too."""' 'X = 1'
  expect_green 'R6 a prefixed module docstring' "$root"
  # R6f route C: a `## <heading>` line inside a shell heredoc is Markdown, not a comment.
  root="$tmp/r6-heredoc"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' "cat <<'MD' >\"\$f\"" '## Section One' 'MD'
  expect_red 'R6 a heredoc heading line is graded' "$root" 'tools/grader.sh:3: names the slot heading "Section One"'
  # R6g-R6j one case per tokenizer rule `S5T-verify-4.md` found untested; each goes red on the mutant
  # that drops its rule. R6g a `\` on the line above: the triple quote continues an assignment.
  root="$tmp/r6-continued"; new_root "$root"
  write_lines "$root/build/grade.py" 'FIXTURE_BRIEF = \' '    """' '## Section One' '"""'
  expect_red 'R6 a continued triple quote is a value' "$root" 'build/grade.py:3: names the slot heading "Section One"'
  # R6h `'''` is a triple quote too, and opens a value the same way.
  root="$tmp/r6-single-triple"; new_root "$root"
  write_lines "$root/build/grade.py" "FIXTURE_BRIEF = '''" '## Section One' "'''"
  expect_red "R6 a ''' value is graded" "$root" 'build/grade.py:2: names the slot heading "Section One"'
  # R6i a bracket inside a one-line string moves no depth, so the argument below stays a value.
  root="$tmp/r6-string-bracket"; new_root "$root"
  write_lines "$root/build/grade.py" 'MSG = check(")",' '    """' '## Section One' '    """)'
  expect_red 'R6 a bracket in a string is not code' "$root" 'build/grade.py:3: names the slot heading "Section One"'
  # R6j a `\`-escaped triple quote inside a docstring does not close it.
  root="$tmp/r6-escaped-fence"; new_root "$root"
  write_lines "$root/build/grade.py" '"""A note: \""" is an escaped fence."""' 'X = 1'
  expect_green 'R6 an escaped fence closes nothing' "$root"

  # --- R9, non-ASCII source is read as bytes -----------------------------------------------------
  # macOS awk aborts a regex test on half a UTF-8 character (`towc: multibyte conversion failure`,
  # exit 2), so without `LC_ALL=C` on the scan an accented identifier, or an advisory-only line in
  # curly quotes, reds the gate through a message that names no rule.
  root="$tmp/r9-non-ascii"; new_root "$root"
  write_lines "$root/build/grade.py" 'café = 1'
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'X="see “section one” here"'
  expect_green 'R9 non-ASCII source exits 0' "$root"
  case "$OUT" in
    *'ADVISORY  tools/grader.sh:2: names "section one"'*) : ;;
    *) printf 'SELFTEST FAIL: a curly-quoted heading drew no advisory; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  # --- R8, the record's headings are on the list -------------------------------------------------
  # The fixture record heads `beta` with words no catalogue default carries.
  root="$tmp/r8-record"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'GRADED="Whatever The Run Chose"'
  expect_red 'R8 a heading only the record carries' "$root" 'names the slot heading "Whatever The Run Chose"'

  # --- the advisory ------------------------------------------------------------------------------
  # ADV-a another case and another spacing: exit 0, printed, counted. ADV-b a heading whose lower
  # case is a slot id draws no advisory from that id.
  root="$tmp/adv-case"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'a="section one"' 'b="Section  *Two"'
  expect_green 'advisory: case and spacing are not findings' "$root"
  case "$OUT" in
    *'ADVISORY  tools/grader.sh:2: names "section one"'*'ADVISORY  tools/grader.sh:3: names "section two"'*'2 advisory)'*) : ;;
    *) printf 'SELFTEST FAIL: case and spacing variants drew no advisory; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac
  root="$tmp/adv-slot-id"; new_root "$root"
  sed 's/"heading": "Whatever The Run Chose"/"heading": "Beta"/' "$root/$RECORD" >"$root/x"
  mv "$root/x" "$root/$RECORD"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'slot_heading beta'
  expect_green 'advisory: a slot id is not a heading copy' "$root"
  case "$OUT" in
    *ADVISORY*) printf 'SELFTEST FAIL: a slot id drew an advisory; got: %s\n' "$OUT" >&2
                return 1 ;;
  esac

  # --- the label ---------------------------------------------------------------------------------
  # C3i the LINE label exempts its own line and nothing else.
  root="$tmp/lab-line"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' \
    'fixture="## Section One"  # heading-literal: a fixture brief carries headings' \
    'true'
  expect_green 'label: a line label exempts its line' "$root"
  root="$tmp/lab-line-next"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' \
    'a="## Section One"  # heading-literal: a fixture brief carries headings' \
    'b="## Section Two"'
  expect_red 'label: a line label reaches one line' "$root" 'tools/grader.sh:3: names the slot heading "Section Two"'

  # C3j a line label with NO REASON exempts nothing and is itself a finding.
  root="$tmp/lab-noreason"; new_root "$root"
  write_lines "$root/tools/grader.sh" '#!/usr/bin/env bash' 'a="## Section One"  # heading-literal: x'
  expect_red 'label: a line label with no reason' "$root" 'line label carries no reason'

  # C3k the BLOCK label, which is the only form a `\`-continued fixture can carry.
  root="$tmp/lab-block"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' \
    '# heading-literal-block: the fixture brief below is this test own input' \
    'write_lines "$f" \' \
    '  "## Section One" \' \
    '  "## Section Two"' \
    '# /heading-literal' \
    'true'
  expect_green 'label: a block label exempts its region' "$root"

  # C3l a block label with no CLOSER exempts nothing, and every line it covered is still reported.
  root="$tmp/lab-noclose"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' \
    '# heading-literal-block: the fixture brief below is this test own input' \
    'a="## Section One"'
  expect_red 'label: an unclosed block exempts nothing' "$root" 'block label is never closed'
  case "$OUT" in
    *'tools/grader.sh:3: names the slot heading "Section One"'*) : ;;
    *) printf 'SELFTEST FAIL: an unclosed block hid the line it covered; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  # C3m a block label with no reason, and C3n a block over the bound. Both exempt nothing, and the
  # over-bound case must still report the lines it covered, or the bound is a way to hide them.
  root="$tmp/lab-block-noreason"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' '# heading-literal-block: x' 'a="## Section One"' '# /heading-literal'
  expect_red 'label: a block label with no reason' "$root" 'block label carries no reason'

  root="$tmp/lab-bound"; new_root "$root"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# heading-literal-block: a region far wider than any fixture needs\n'
    printf 'a="## Section One"\n'
    for i in $(seq 1 "$((REGION_MAX + 2))"); do printf 'filler_%s=1\n' "$i"; done
    printf '# /heading-literal\n'
  } >"$root/tools/grader.sh"
  expect_red 'label: a block over the bound' "$root" 'over the bound of'
  case "$OUT" in
    *'names the slot heading "Section One"'*) : ;;
    *) printf 'SELFTEST FAIL: an over-bound block hid the line it covered; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  # C3o a block label exactly AT the bound is still a label: a bound proved only from the outside is
  # a bound nobody measured at its edge.
  root="$tmp/lab-atbound"; new_root "$root"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# heading-literal-block: a region at the bound exactly\n'
    printf 'a="## Section One"\n'
    for i in $(seq 1 "$((REGION_MAX - 2))"); do printf 'filler_%s=1\n' "$i"; done
    printf '# /heading-literal\n'
  } >"$root/tools/grader.sh"
  expect_green 'label: a block at the bound exactly' "$root"

  # C3p a label inside a SINGLE-QUOTED awk program is still a comment to this scanner, and that is
  # deliberate: an awk `#` comment is a comment an author reads, and the awk body is where a section
  # finder keyed on a heading actually lives.
  root="$tmp/lab-awk"; new_root "$root"
  write_lines "$root/tools/grader.sh" \
    '#!/usr/bin/env bash' \
    "awk '" \
    '  # heading-literal-block: the fixture section finder below is the test own input' \
    '  /^## Section One/ { print }' \
    '  # /heading-literal' \
    "' \"\$1\""
  expect_green 'label: a label inside an awk program' "$root"

  # --- the scan set and the counters -------------------------------------------------------------
  # C3q a tree with no source at all is a FAILURE, never a vacuous pass.
  root="$tmp/c3-nofiles"; new_root "$root"; rm -rf "$root/tools" "$root/build"
  expect_red 'C3 nothing scanned' "$root" 'nothing to scan'

  # C3r the file COUNT and the labelled-line count are derived and printed, so an opt-out that grows
  # is visible in the gate own output. The green fixture tree scans two files -- the stub renderer
  # and the clean script -- and labels none.
  root="$tmp/count"; new_root "$root"
  run_child --check "$root"
  case "$OUT" in
    *'2 source file(s) scanned, 0 labelled line(s)'*) : ;;
    *) printf 'SELFTEST FAIL: the OK line does not report 2 files and 0 labels; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac
  write_lines "$root/tools/labelled.sh" \
    '#!/usr/bin/env bash' \
    'a="## Section One"  # heading-literal: a fixture brief carries headings'
  run_child --check "$root"
  case "$OUT" in
    *'3 source file(s) scanned, 1 labelled line(s)'*) : ;;
    *) printf 'SELFTEST FAIL: the counters did not move with the label; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  # C3t the CEILING, at its edge from both sides: LABELLED_MAX line labels pass, one more reds.
  root="$tmp/ceiling"; new_root "$root"
  {
    printf '#!/usr/bin/env bash\n'
    for i in $(seq 1 "$LABELLED_MAX"); do
      printf 'a%s="## Section One"  # heading-literal: fixture line %s of the ceiling case\n' "$i" "$i"
    done
  } >"$root/tools/labelled.sh"
  expect_green 'ceiling: labels at the ceiling exactly' "$root"
  printf 'z="## Section One"  # heading-literal: the one label over the ceiling\n' >>"$root/tools/labelled.sh"
  expect_red 'ceiling: one label over it' "$root" "over the ceiling of $LABELLED_MAX"

  # C3s a tree with no catalogue fails ALL THREE checks and says so; the checks-ran assertion is
  # what stops a partial grade from printing an OK line.
  root="$tmp/nocat"; new_root "$root"; rm -f "$root/$CATALOGUE"
  expect_red 'no catalogue: C3 refuses to scan' "$root" 'C3 cannot scan source without a readable'
  case "$OUT" in
    *'C2 cannot grade'*) : ;;
    *) printf 'SELFTEST FAIL: C2 did not fail closed without a catalogue; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  # C5 THE CHECKS-RAN ASSERTION, proved on a CHILD COPY WITH ONE INCREMENT DELETED. No fixture can
  # reach it from the outside -- every path that skips a check also files a finding, so a partial
  # grade always carries a reason and the assertion never fires on its own. That makes the obvious
  # mutant (delete the assertion) an EQUIVALENT one, and a guard nothing can kill is decoration.
  # The mutant that discriminates is on the INCREMENT: a check that runs and forgets to count
  # itself. Same shape `tools/coverage-notes.sh` uses for its own counter.
  root="$tmp/count-assert"; new_root "$root"
  cp "${BASH_SOURCE[0]}" "$tmp/one-less.sh"
  perl -0pi -e 's/CHECKS_RUN=\$\(\(CHECKS_RUN \+ 1\)\)\n\n  order=""/order=""/' "$tmp/one-less.sh"
  if ! grep -q 'CHECKS_RUN' "$tmp/one-less.sh"; then
    printf 'SELFTEST FAIL: the mutant copy lost every counter; the case would prove nothing\n' >&2
    return 1
  fi
  RC=0
  OUT="$( bash "$tmp/one-less.sh" --check "$root" 2>&1 )" || RC=$?
  if [ "$RC" -eq 0 ]; then
    printf 'SELFTEST FAIL: a copy with one increment deleted reported a clean grade; got: %s\n' "$OUT" >&2
    return 1
  fi
  case "$OUT" in
    *'2 of 3 checks ran; a partial grade is not a pass'*)
      NRED=$((NRED + 1))
      printf 'SELFTEST red OK   %-44s -> exit %s\n' 'C5 one check forgot to count itself' "$RC" ;;
    *) printf 'SELFTEST FAIL: the uncounted check went red with the wrong message; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  # C4 the argument contract: an unrecognised argument is exit 2 with a usage line, never a silent
  # pass, and a bare run is `--check` on this checkout.
  run_child --self-test
  if [ "$RC" -ne 2 ]; then
    printf 'SELFTEST FAIL: an unrecognised argument exited %s, want 2; got: %s\n' "$RC" "$OUT" >&2
    return 1
  fi
  case "$OUT" in
    *'unrecognised argument: --self-test'*'usage:'*) NRED=$((NRED + 1)) ;;
    *) printf 'SELFTEST FAIL: an unrecognised argument printed no usage; got: %s\n' "$OUT" >&2
       return 1 ;;
  esac

  printf 'SELFTEST OK: %s red and %s green cases over 3 checks (C1 catalogue, C2 record, C3 source)\n' \
    "$NRED" "$NGREEN"
  return 0
}

usage() {
  printf 'usage: %s [--check [ROOT]] | --selftest\n' "${BASH_SOURCE[0]}" >&2
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  case "$#:${1:-}" in
    "0:")           scan "$ROOT" ;;
    "1:--check")    scan "$ROOT" ;;
    "2:--check")    scan "$2" ;;
    "1:--selftest") selftest ;;
    *)              printf 'unrecognised argument: %s\n' "${1:-}" >&2
                    usage
                    exit 2 ;;
  esac
fi
