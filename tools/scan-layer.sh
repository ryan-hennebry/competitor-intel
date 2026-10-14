#!/usr/bin/env bash
# The scan layer. It extracts every heading and every bold run from one markdown brief, in document
# order, prints them as a document of their own, and grades that document.
#
# THE ABSTRACTION. A brief is read twice. The first read is a SCAN: the eye lands on the headings
# and the bold runs and on nothing else, in document order, and whatever those units say alone is
# what the reader takes away before deciding whether to read the prose at all. The second read is
# linear. Every other lint in this repository grades the linear read. This one grades the first: it
# builds the artefact the scanner actually sees -- `output/research/round-run/22-scannability-rulebook.md:253`,
# verbatim, "extract every heading and every bold run from the source markdown in document order,
# concatenate them into a single document, and read it cold" -- and then asks two questions of it.
# S1 asks whether sibling rows and sibling bullets START ON DIFFERENT WORDS, so a scanning eye can
# tell them apart at the left edge. S2 asks whether a unit OPENS ON A CONNECTIVE OR A PRONOUN, which
# reads fine in place and dissolves when the layer is read alone, because the antecedent is in prose
# the scanner skipped.
#
# WHY IT EXISTS. Nothing downstream reads the brief that way. `build/build.py`'s `audit()` grades
# structure, `tools/thesis-check.sh` grades the sidecar, `tools/date-stamp.sh` grades how the brief
# stamps time, `tools/ai-smell.sh` grades voice -- and a brief whose five table rows all opened on
# the same word, or whose Quick Take claim-header opened "This", rendered green through all four.
# The scan layer is not any one of those files' business, and it was nobody's.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name, so
# this is a standalone script the pipeline invokes, exactly as `tools/thesis-check.sh`,
# `tools/ai-smell.sh`, `tools/date-stamp.sh` and the ICP floor are standalone build-blocking lints.
#
# It runs BEFORE the first build and reads the MARKDOWN target only -- never the HTML and never the
# PDF. Every finding it raises is a prose edit, and after the build a prose edit costs a rebuild.
#
# It collects every finding and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is.
#
# WHAT THE SOURCE RULE SAYS AND WHERE THIS REPOSITORY LEAVES IT. Rule 6 of the rulebook carries its
# own tag, verbatim: `[S] bypassing pattern; NNG bullets rule 4`. The cited source covers BULLETS.
# The extension of the same rule to TABLE COLUMNS is the rulebook's own extrapolation, and this
# repository's exemplar falsifies it for value columns -- see exclusion 1 below, which is the
# measurement. So S1 grades the bullet case the source actually supports, plus the table columns
# whose header is on the ALLOWLIST at `S1_LABEL_COLUMNS`, which today holds the single label
# `capability`.
#
# THE PRINCIPLE, and the reason the boundary sits exactly there: THIS CHECK GRADES WHAT THE RUN
# AUTHORS AND NEVER WHAT IT RECORDS. Company names, threat verdicts and capability answers are
# RECORDED. `AGENTS.md` Provenance requires company names "verbatim as written on the company's own
# site", so a run can neither rename nor drop nor reorder out of a collision between two of them,
# and an unattended run "has nobody to ask". The Competitive Matrix's `Capability` row labels and
# the Open Questions items are AUTHORED, so every finding on them has a one-edit fix. MEASURED
# 2026-09-07: grading every table's first column halts the build on a legal market with no legal
# fix -- a two-row fixture holding `Bank of London` and `Bank of America`, or `Round Treasury` and
# `Round Capital`, exits 1 on `FAIL: S1 sibling leading word "Bank" repeats 2 times ... first
# column` -- and four of the exemplar's five tables carry an entity roster in column one (`Company`
# at `build/briefing.md:30,56,80`, `Competitor` at `:41`); only the Competitive Matrix's
# `Capability` at `:67` holds authored labels. The list is an ALLOWLIST and never a denylist of
# entity headers, because a denylist fails OPEN: the next brief's `Vendor`, `Rival`, `Firm` or
# `Name` column would still be graded and still halt, and it would surface only on a live
# unattended run. An UNKNOWN HEADER IS UNGRADED, so the check fails green on text the run did not
# author. Exclusion 1 below already drew this line for value columns and called it "the repetition
# IS the information the table exists to carry"; the allowlist makes that distinction the actual
# rule instead of using column position as a proxy for it. S1's LIST half is unchanged and stays
# blocking, because every list item in the brief is authored prose.
#
# `grep` is wrapped to `ugrep` in the interactive shell, where a pattern starting with `--` parses as
# an option, so every pattern below is passed after `-e`. Inside this script `grep` is /usr/bin/grep
# (BSD). The parsing itself is `awk`, not `grep`: the units are positional (a table's FIRST column, a
# list's CONTIGUOUS run at ONE indent depth) and a line-matching tool cannot express position.
#
# WHAT IT DELIBERATELY DOES NOT CHECK, and why each one is absent rather than forgotten:
#
#   1. EVERY TABLE COLUMN BUT THE FIRST. MEASURED 2026-09-07 on `build/briefing.md`: grading all
#      columns reds 12 times across four of the five tables, and in 10 of the 12 the repeated word
#      is the cell's entire answer or a closed-vocabulary token -- `WATCH` x4 and `rising` x3 and
#      `steady` x2 in Threat Landscape, `Yes` x5 in the Round column, `No` x4, x4, x3 and x3 and
#      `Not` x2 in the rival columns of the Competitive Matrix, `No` x3 in Runs unattended? --
#      where the repetition IS the information the table exists to carry. Nothing mechanical here
#      separates those from the two that are genuine prose collisions, Threat Landscape's Key Gap
#      You Exploit (`No` x4 at :43,44,46,47) and Stage and Reach's UK entity (`Office` x2 at
#      :84,85, where the two cells are identical). Both are booked in `docs/PLAN.md` section 8
#      rather than graded. The exclusion is live, not assumed: mutating `record("T" tstart, ...,
#      norm(cell[2]), NR)` into a loop over every cell reds the exemplar on those same four tables,
#      measured 2026-09-07 on a scratch copy with the real tree unmutated.
#   2. BOLD CLAIM-HEADERS, for S1. Rule 6 governs "sibling bullets or rows" and a claim-header is
#      neither. MEASURED red anyway: `build/briefing.md:16` and `:18` both open `The`. Claim-headers
#      ARE graded by S2, which is a different question -- whether the unit stands alone.
#   3. THE TEN `h2` SECTION HEADINGS, for S1. MEASURED red: `## What Changed` at :28 and
#      `## What Each Company Says Its AI Does` at :54 both open `What`, and both names are fixed by
#      that run's own `headings.json`, which `audit()` GATE 2 grades, so the check would grade a
#      contract another file owns. Headings ARE graded by S2, for the same reason as item 2.
#   4. THE SCAN LAYER'S WORD BUDGET. `22-scannability-rulebook.md:258` calls its own 150-word figure
#      "[Y] and arbitrary -- no source supports it". The extraction prints the count and asserts no
#      threshold on it. The count is of the PRINTED unit lines, so a heading's `##` prefix is one
#      token in it: the rulebook says concatenate the units and read them, and the printed document
#      is what is counted, not a cleaned-up version of it.
#   5. THE `## Sources` LINK LINES. They are `<br>`-separated links inside one `<p>`, not list items.
#      MEASURED: extracting their link text collides `build/briefing.md:110` `[atlar.com]` with
#      `:111` `[Atlar human-in-the-loop explainer]` on `Atlar`, which is one company's two sources
#      and not a scan defect.
#   6. THE RENDERED PDF. The check reads the source markdown, as `22-scannability-rulebook.md:253`
#      specifies. A collision the renderer introduces is invisible to it.
#
# Two smaller boundaries, stated so they are not mistaken for oversights. A HEADING LINE emits one
# unit, the heading, and its bold runs are not emitted a second time -- MEASURED: no heading in the
# exemplar carries bold, so the two spellings agree there, and emitting both would double-count a
# unit the eye lands on once. A BLANK LINE does not break a list, so a loose list is one group; any
# other non-item line does, which also means an indented continuation line ends its list.
#
# FIVE PARSING BOUNDARIES, each MEASURED, named here so none is rediscovered as a bug. The first
# four are false-GREEN surfaces in S1; the fifth is a false-RED surface in S2.
#
#   A. A GFM TABLE WITHOUT LEADING PIPES IS INVISIBLE TO S1. `s1_findings()` enters table state
#      only on `/^[ \t]*\|/`, so a row written `Capability | Round | Hooli` with no opening pipe is
#      never graded at all. LATENT, not live: MEASURED that `build/briefing.md` and
#      `references/briefing-template.md` both write every row with a leading pipe.
#   B. A PIPE INSIDE INLINE CODE TRUNCATES THE FIRST CELL. The row is split on `|` with no
#      awareness of backticks, so `` | `a|b` Round | `` grades `a`, and a collision with a `Round`
#      label in a sibling row is missed.
#   C. A TAB-INDENTED ITEM AND A SPACE-INDENTED ITEM AT THE SAME VISUAL DEPTH ARE NOT SIBLINGS.
#      `indent = match($0, /[^ \t]/) - 1` counts one tab as ONE column, so a tab-indented child and
#      a four-space-indented child land in different groups and a collision between them is missed.
#   D. TWO TABLES WITH NO BLANK LINE BETWEEN THEM MERGE. Table state ends on the first non-pipe
#      line, so table B's header row is read as a body row of table A. B's delimiter row normalises
#      to empty and `record()` skips it, so the only exposure is a spurious collision between A's
#      row labels and B's header word -- and only when A's own header is on the allowlist.
#   E. S2 CAN RED ON A UNIT THAT OPENS ON A COMPANY NAME WHICH IS ITSELF A TRIGGER WORD.
#      `**Also Energy shipped an agent.**` reds on `Also`. Remediable wherever the author chooses
#      the sentence, and NOT remediable for the client's standalone bolded name in a table cell
#      (`**Round**` at `build/briefing.md:32,58,67,82`): a client literally named `It` or `Also`
#      would red there with no fix available to the run.
#
# PRECONDITION: none beyond the target file existing. No network, no MKT1 call, no env var, no build
# artefact, no run directory, no browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_TARGET="build/briefing.md"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

# Incremented once per check that ACTUALLY RUNS, so the success line cannot claim two checks while
# one runs. Same intent as `rule_count()` in `tools/ai-smell.sh` and `CHECKS_RUN` in
# `tools/date-stamp.sh`, derived from execution rather than from a table. On the empty/absent path it
# stays 0 and the caller exits 1, so the OK line is never printed with a count of zero.
CHECKS_RUN=0

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# THE S1 TABLE ALLOWLIST, and the only place it is written. These are the header labels whose first
# column holds text THIS RUN AUTHORS, and therefore the only table columns S1 grades; see THE
# PRINCIPLE in the header. Semicolon-delimited and matched against the WHOLE normalised header
# (inline HTML, emphasis and link syntax stripped, ends trimmed, internal whitespace collapsed,
# case-folded), so a multi-word label is expressible and no substring can match. Today it is exactly
# one entry: the Competitive Matrix's `Capability` column, whose cells are row labels the run
# writes. `references/briefing-template.md` owns the section list and the tables inside it, so a new
# authored first column arrives there first and is added here second -- one line, and nothing else
# in this file changes.
S1_LABEL_COLUMNS="capability"

# The S2 vocabulary: connectives and pronouns whose antecedent is in prose a scanner skipped. Source
# is the rulebook's failure signal 2 at `22-scannability-rulebook.md:254-256`. Space-delimited and
# matched with a bash `case` on `" $list "`, so the test is whole-word by construction and no regex
# is in the path -- MEASURED elsewhere in this repository that an unanchored alternation matches
# inside ordinary English (`event` inside `prevent`).
S2_WORDS="this that these those they them it its there however therefore additionally furthermore \
moreover also thus hence"

# --- the extraction -------------------------------------------------------------------------------
# units() prints one TAB-separated record per scan-layer unit, in document order:
#   line <TAB> kind (H|B) <TAB> normalised first word <TAB> printed text
# The printed text is the heading VERBATIM including its `#` prefix, or a bold run's inner text with
# the `**` markers stripped. Bold runs inside table cells count (`**Round**` at
# `build/briefing.md:32,58,67,82`) and so do bold runs inside `<p class="rec" markdown="1">` blocks
# (`:22,24,26,89`): the eye lands on both.
#
# The bold scan walks the line with index()/substr() rather than a regex, because the run's inner
# text may itself contain a single `*` and a greedy or a non-greedy ERE both mis-split that. It also
# means a single-asterisk italic span is never mistaken for bold: `build/briefing.md:14` carries
# `*"Round only moves money..."*` on the same line as a real bold run, and only the bold run is
# emitted.
units() {
  awk -v OFS='\t' '
    function norm(s,   t, n, arr) {
      gsub(/<[^>]*>/, "", s)            # inline HTML tags
      gsub(/\]\([^)]*\)/, "", s)        # the (url) half of [text](url)
      gsub(/[][]/, "", s)               # and its brackets
      gsub(/[*_]/, "", s)               # emphasis markers
      sub(/^[^A-Za-z0-9]+/, "", s)      # leading punctuation, quotes, currency, brackets
      n = split(s, arr, /[ \t]+/)
      if (n == 0) return ""
      t = arr[1]
      sub(/[.,;:!?)]+$/, "", t)
      return t
    }
    {
      if ($0 ~ /^#+[ \t]/) { print NR, "H", norm($0), $0; next }
      rest = $0
      while ((i = index(rest, "**")) > 0) {
        after = substr(rest, i + 2)
        j = index(after, "**")
        if (j == 0) break
        inner = substr(after, 1, j - 1)
        print NR, "B", norm(inner), inner
        rest = substr(after, j + 2)
      }
    }
  ' "$1"
}

# --- S1 -------------------------------------------------------------------------------------------
# s1_findings() prints one ready-made finding per line, sorted by the group's first source line so
# the output is deterministic: awk array iteration order is not.
#
# Graded units, and ONLY these: every markdown list item at the same indent depth inside one
# contiguous list, and the FIRST COLUMN body cells of a table WHOSE HEADER IS ON `S1_LABEL_COLUMNS`
# -- header row and `|---|` delimiter row excluded, and every table with any other header ungraded
# entirely. See THE PRINCIPLE and exclusions 1, 2 and 3 above for everything else.
s1_findings() {
  awk -v f="$1" -v allow="$S1_LABEL_COLUMNS" '
    function norm(s,   t, n, arr) {
      gsub(/<[^>]*>/, "", s)
      gsub(/\]\([^)]*\)/, "", s)
      gsub(/[][]/, "", s)
      gsub(/[*_]/, "", s)
      sub(/^[^A-Za-z0-9]+/, "", s)
      n = split(s, arr, /[ \t]+/)
      if (n == 0) return ""
      t = arr[1]
      sub(/[.,;:!?)]+$/, "", t)
      return t
    }
    # normhdr() reduces a header cell to its comparable form: the same strips as norm(), then ends
    # trimmed, internal whitespace collapsed to one space, and case-folded. It returns the WHOLE
    # label, not the first word, because the allowlist is a set of labels and not of openers.
    function normhdr(s) {
      gsub(/<[^>]*>/, "", s)
      gsub(/\]\([^)]*\)/, "", s)
      gsub(/[][]/, "", s)
      gsub(/[*_]/, "", s)
      sub(/^[ \t]+/, "", s)
      sub(/[ \t]+$/, "", s)
      gsub(/[ \t]+/, " ", s)
      return tolower(s)
    }
    # graded_column() is the allowlist test, whole-label by construction: the list and the candidate
    # are both wrapped in the `;` delimiter, so no label can match inside a longer one.
    function graded_column(h) {
      if (h == "") return 0
      return index(";" allow ";", ";" h ";") > 0
    }
    # record() files one graded sibling under its group, keyed by group and case-folded word, and
    # keeps the word AS IT APPEARED for the report.
    function record(key, desc, word, ln,   k, lw) {
      if (word == "") return              # an empty first token is skipped, never a collision
      lw = tolower(word)
      k = key SUBSEP lw
      if (!(k in cnt)) {
        cnt[k] = 0; first[k] = ln; shown[k] = word; gdesc[k] = desc; lines[k] = ""
      }
      cnt[k]++
      if (cnt[k] == 1)      lines[k] = ln
      else if (cnt[k] == 2) lines[k] = lines[k] ":" ln
      else                  lines[k] = lines[k] "," ln
    }
    {
      # --- tables ---
      if ($0 ~ /^[ \t]*\|/) {
        if (tphase == "") {
          tphase = "header"; tstart = NR
          # The allowlist decision is taken ONCE, on the header row, and held for the table. A
          # table whose first-column header is not an authored label is ungraded from here on.
          n = split($0, cell, "|")
          tgraded = (n >= 3) ? graded_column(normhdr(cell[2])) : 0
        }
        else if (tphase == "header") {
          if ($0 ~ /^[ \t]*\|[-: \t|]+$/) tphase = "body"
        }
        else if (tphase == "body" && tgraded) {
          n = split($0, cell, "|")
          if (n >= 3) {
            record("T" tstart, "the table starting at line " tstart ", first column", \
                   norm(cell[2]), NR)
          }
        }
      } else {
        tphase = ""
        tgraded = 0
      }

      # --- lists ---
      if ($0 ~ /^[ \t]*([-*+]|[0-9]+\.)[ \t]+/) {
        indent = match($0, /[^ \t]/) - 1
        if (!inlist) { inlist = 1; lid++; lstart = NR }
        # The marker is stripped by the SAME pattern that matched it, so the graded word is the one
        # at the left edge whatever whitespace follows the marker. Finding the first SPACE instead
        # graded the SECOND word of a tab-separated item -- MEASURED: `-<TAB>Can tabbed one` and
        # `-<TAB>Can tabbed two` reported `tabbed` and missed the real `Can` collision.
        item = $0
        sub(/^[ \t]*([-*+]|[0-9]+\.)[ \t]+/, "", item)
        record("L" lid ":" indent, \
               "the list starting at line " lstart " at indent depth " indent, \
               norm(item), NR)
      } else if ($0 !~ /^[ \t]*$/) {
        inlist = 0
      }
    }
    END {
      for (k in cnt) {
        if (cnt[k] < 2) continue
        printf "%d\tFAIL: S1 sibling leading word \"%s\" repeats %d times in %s at %s:%s\n", \
          first[k], shown[k], cnt[k], gdesc[k], f, lines[k]
      }
    }
  ' "$1" | sort -n | cut -f2-
}

# --- the check ------------------------------------------------------------------------------------
# check_file populates FAILS for one target path and ALWAYS returns 0; the caller decides. Same
# contract as `check_file` in `tools/date-stamp.sh`, `tools/ai-smell.sh` and `tools/thesis-check.sh`,
# and it is what lets the selftest run every case in this shell without `set -e` ending the run at
# the first red.
check_file() {
  local f="$1" hits rec ln kind word oldifs lw

  FAILS=""
  CHECKS_RUN=0

  # `test -s` first, and every check skipped when it fires. An absent or empty brief is a FAILURE and
  # never a vacuous pass: a scan layer extracted from nothing has no collisions and no connectives,
  # and two checks reporting no findings on a file that does not exist is precisely the shape of
  # green this repository treats as a lie.
  if [ ! -s "$f" ]; then
    add_fail "FAIL: no brief to grade at $f (missing or empty)"
    return 0
  fi

  # --- S1: no two sibling row labels or list items begin with the same word --------------------
  CHECKS_RUN=$((CHECKS_RUN + 1))
  hits="$(s1_findings "$f")"
  if [ -n "$hits" ]; then
    oldifs="$IFS"
    set -f
    IFS=$'\n'
    for rec in $hits; do
      add_fail "$rec"
    done
    IFS="$oldifs"
    set +f
  fi

  # --- S2: no scan-layer unit opens with a connective or an antecedent-free pronoun ------------
  # Graded on the SAME units the extraction prints, which is the whole point: the failure is only
  # visible when the layer is read alone.
  CHECKS_RUN=$((CHECKS_RUN + 1))
  hits="$(units "$f")"
  if [ -n "$hits" ]; then
    oldifs="$IFS"
    set -f
    IFS=$'\n'
    for rec in $hits; do
      ln="${rec%%$'\t'*}"
      kind="${rec#*$'\t'}"
      word="${kind#*$'\t'}"
      kind="${kind%%$'\t'*}"
      word="${word%%$'\t'*}"
      [ -n "$word" ] || continue
      lw="$(printf '%s' "$word" | tr 'A-Z' 'a-z')"
      case " $S2_WORDS " in
        *" $lw "*)
          add_fail "FAIL: S2 scan-layer unit opens with \"$word\", which has no antecedent read \
alone, at $f:$ln" ;;
      esac
    done
    IFS="$oldifs"
    set +f
  fi

  return 0
}

# --- selftest -------------------------------------------------------------------------------------
# Proves each failure mode red on its own minimal fixture, proves S1 in BOTH directions on the same
# words, proves each exclusion by a green case that would be red without it, proves the exemplar
# green, proves the red artefact red on BOTH checks, and runs the script as a child process so
# `main_check()`, `main_extract()`, the default target, the argument dispatch, the OK line, the
# header line and the non-zero exit are exercised by the run and not by prose. A check that has
# never gone red is an untested assertion.

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

# THE FIXTURE HEADINGS, NAMED ONCE AND LABELLED. Every fixture brief below and the one extraction
# assertion derive from these two names, so `git grep -n heading-literal` finds every place this
# file writes a section heading. They are real catalogue defaults deliberately: a fixture heading no
# brief ships would exercise the extraction against a shape no run produces.
FX_FIRST="Quick Take"     # heading-literal: the opening heading of every fixture scan layer below
FX_SECOND="Open Questions"  # heading-literal: the closing heading of the clean fixture scan layer

# A clean scan layer -- one heading, one bold claim-header, one ALLOWLISTED table with distinct
# first-column labels, one list with distinct openers -- reused by every fixture below, so a red
# case proves the tell and not the scaffolding. The table is Competitive-Matrix-shaped on purpose:
# `Capability` is the only header S1 grades, so a first-column case has to be written under it.
write_clean() {
  local f="$1"
  write_lines "$f" \
    '# Competitor Intel Briefing' \
    '' \
    "## $FX_FIRST" \
    '' \
    '**Nobody in this category has published a control model.** One page per agent would do it.' \
    '' \
    '| Capability | Round | Acme |' \
    '|---|---|---|' \
    '| Idle-cash sweep | Yes | No |' \
    '| Payroll rails | Yes | Not published |' \
    '| Agent bounds | Published | Unknown |' \
    '' \
    "## $FX_SECOND" \
    '' \
    '1. Can the approval rule gate the agent, or only payables?' \
    '2. Is the reference still referenceable, given the investor overlap?'
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
# Every case above calls check_file IN THIS SHELL, so `main_check()`, `main_extract()`, the
# `cd "$ROOT"`, the default target, the argument dispatch, the SCAN-LAYER-OK line, the extraction
# header and the non-zero exit would be exercised by nothing. That gap is load-bearing and not
# hypothetical: inside `OUT="$( (f) 2>&1 )"` bash suspends `set -e`, so an in-process case cannot see
# an abort at all, and it was `main()` on the real corpus that killed `tools/known-traps.sh` while
# its twelve in-process cases stayed green. The cases below copy this script into a fixture root and
# run it as a CHILD with its own fully armed `set -euo pipefail`, which is the invocation a run
# actually makes. The idiom is `tools/date-stamp.sh:313-376`.
PROC_RC=0
PROC_OUT=""

make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/build"
  cp "${BASH_SOURCE[0]}" "$root/tools/scan-layer.sh"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/scan-layer.sh" "$@" 2>&1 )" || PROC_RC=$?
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
    *"$want"*) printf 'SELFTEST proc OK  %-30s -> exit 0, %s\n' "$label" "$want" ;;
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
    *SCAN-LAYER-OK*)
      printf 'SELFTEST FAIL: a red child run printed SCAN-LAYER-OK: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  printf 'SELFTEST proc red %-30s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp fixture cases=0 id missing proc w sw nw s2vocab

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/scan-layer-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # The scaffolding itself, green. Every red fixture below is this file plus one defect.
  write_clean "$tmp/clean.md"
  expect_green 'clean brief fragment' "$tmp/clean.md"
  cases=$((cases + 1))

  # S1 on an ALLOWLISTED table's FIRST column: two rows opening on the same authored label. The
  # green half is the clean fixture above, which carries the same table with distinct labels, so the
  # pair fails if either the collision test or the first-column extraction stops working.
  sed -e 's/^| Payroll rails |/| Idle-cash ledger |/' "$tmp/clean.md" >"$tmp/s1-table.md"
  expect_red 'S1 repeated first-column label' "$tmp/s1-table.md" \
    'FAIL: S1 sibling leading word "Idle-cash" repeats 2 times in the table starting at line 7'
  cases=$((cases + 1))

  # THE ALLOWLIST, live and in both directions. A first column whose header is NOT an authored label
  # is ungraded ENTIRELY, so two real rivals that share a leading word are green -- there is no edit
  # a run could make, because `AGENTS.md` Provenance pins company names to the company's own site
  # and an unattended run has nobody to ask. Grade every first column instead and both of these red.
  write_lines "$tmp/s1-roster.md" \
    '| Company | Change |' \
    '|---|---|' \
    '| Bank of London | Seed raise, nothing since. |' \
    '| Bank of America | Office opened, no licence. |'
  expect_green 'S1 entity roster ungraded' "$tmp/s1-roster.md"
  cases=$((cases + 1))

  # The same, under a header the denylist form would have missed. This is the case that makes the
  # allowlist an allowlist: `Vendor` is not `Company` or `Competitor`, and it is still ungraded.
  write_lines "$tmp/s1-vendor.md" \
    '| Vendor | Change |' \
    '|---|---|' \
    '| Round Treasury | Seed raise, nothing since. |' \
    '| Round Capital | Office opened, no licence. |'
  expect_green 'S1 unknown header ungraded' "$tmp/s1-vendor.md"
  cases=$((cases + 1))

  # S1 on LIST ITEMS, the case the source rule actually covers.
  sed -e 's/^2\. Is the reference/2. Can the reference/' "$tmp/clean.md" >"$tmp/s1-list.md"
  expect_red 'S1 repeated list opener' "$tmp/s1-list.md" \
    'FAIL: S1 sibling leading word "Can" repeats 2 times in the list starting at line 15'
  cases=$((cases + 1))

  # The same two items made distinct again. Without this the check could be "any two list items are
  # a finding" and the suite would not notice.
  expect_green 'S1 distinct list openers' "$tmp/clean.md"
  cases=$((cases + 1))

  # EXCLUSION 1, live: the repeat is in a NON-first column, which is where the exemplar's closed
  # vocabularies live (`WATCH`, `rising`, `No`). Delete the `cell[2]` restriction and this reds.
  write_lines "$tmp/s1-othercol.md" \
    '| Capability | Threat | Trend |' \
    '|---|---|---|' \
    '| Idle-cash | WATCH | rising |' \
    '| Payroll | WATCH | rising |' \
    '| Agents | WATCH | rising |'
  expect_green 'S1 repeat in a later column' "$tmp/s1-othercol.md"
  cases=$((cases + 1))

  # DEPTH GROUPING: two items sharing a first word at DIFFERENT indent depths are not siblings. A
  # nested item is a child, not a peer, and the eye reads it at a different left edge.
  write_lines "$tmp/s1-depth.md" \
    '1. Can the approval rule gate the agent?' \
    '    - Can it reach payroll, or is payroll a file pass-through?' \
    '2. Is the reference still referenceable?'
  expect_green 'S1 same word, other depth' "$tmp/s1-depth.md"
  cases=$((cases + 1))

  # A LIST MARKER FOLLOWED BY A TAB. The matcher accepts `[ \t]+` after the marker, so the graded
  # word must be found the same way. MEASURED before the fix: finding the first SPACE instead
  # reported the SECOND word (`the`), which is both a false green on the real `Can` collision and a
  # false red naming a word that is not at the left edge. The assertion names `Can` for that reason.
  write_lines "$tmp/s1-tab.md" \
    "$(printf -- '-\tCan the approval rule gate the agent?')" \
    "$(printf -- '-\tCan the same rule reach payroll?')"
  expect_red 'S1 tab after the list marker' "$tmp/s1-tab.md" \
    'FAIL: S1 sibling leading word "Can" repeats 2 times in the list starting at line 1'
  cases=$((cases + 1))

  # EXCLUSION 2, live: two bold claim-headers opening on the same word. Rule 6 governs sibling
  # bullets and rows, and MEASURED, `build/briefing.md:16` and `:18` both open `The`.
  write_lines "$tmp/s1-bold.md" \
    '**The unclaimed ground is publishing the boundary.** Answering that costs a page.' \
    '' \
    '**The yield is rented and one reference is conflicted.** Rate parity follows in a quarter.'
  expect_green 'S1 repeated bold opener' "$tmp/s1-bold.md"
  cases=$((cases + 1))

  # EXCLUSION 3, live: two `h2` headings opening on the same word, which the exemplar's own fixed
  # section list does at `:28` and `:54`.
  # heading-literal-block: the two fixture headings below must OPEN ON THE SAME WORD, which is the
  # exclusion under test, so neither can be derived from the two named at the top of this suite
  write_lines "$tmp/s1-heading.md" \
    '## What Changed' \
    '' \
    '## What Each Company Says Its AI Does'
  # /heading-literal
  expect_green 'S1 repeated heading opener' "$tmp/s1-heading.md"
  cases=$((cases + 1))

  # NORMALISATION, three shapes, each proving one strip. Without them a bolded, quoted or linked
  # label would read as a different word from the bare one and the collision would be missed. The
  # quote case opens on `“` and does not close on `”`, and that is MEASURED rather than tidy: the
  # normalisation strips LEADING non-alphanumerics and only `.,;:!?)` from the tail, so `“Round”`
  # normalises to `Round”` and does NOT collide with `Round`. A closing curly quote is not in the
  # trailing set, and this case would be green if it were written that way.
  write_lines "$tmp/n-bold.md" \
    '| Capability | Change |' \
    '|---|---|' \
    '| **Round** | Seed raise. |' \
    '| Round Capital | Office opened. |'
  expect_red 'norm: **Round** vs Round' "$tmp/n-bold.md" \
    'FAIL: S1 sibling leading word "Round" repeats 2 times'
  cases=$((cases + 1))

  write_lines "$tmp/n-quote.md" \
    '| Capability | Change |' \
    '|---|---|' \
    '| “Round moves money on your rules | Seed raise. |' \
    '| Round Capital | Office opened. |'
  expect_red 'norm: curly quote vs bare' "$tmp/n-quote.md" \
    'FAIL: S1 sibling leading word "Round" repeats 2 times'
  cases=$((cases + 1))

  write_lines "$tmp/n-link.md" \
    '| Capability | Change |' \
    '|---|---|' \
    '| [Round](https://example.com/round) | Seed raise. |' \
    '| Round Capital | Office opened. |'
  expect_red 'norm: [Round](url) vs Round' "$tmp/n-link.md" \
    'FAIL: S1 sibling leading word "Round" repeats 2 times'
  cases=$((cases + 1))

  # The fourth strip, TRAILING PUNCTUATION, which the comment above discusses and no case measured:
  # commenting `sub(/[.,;:!?)]+$/, "", t)` out of both copies of norm() left the suite green while
  # changing behaviour, so a one-word cell ending in a full stop stopped colliding with the bare
  # word. This is that collision.
  write_lines "$tmp/n-trail.md" \
    '| Capability | Change |' \
    '|---|---|' \
    '| Round. | Seed raise. |' \
    '| Round Capital | Office opened. |'
  expect_red 'norm: trailing stop vs bare' "$tmp/n-trail.md" \
    'FAIL: S1 sibling leading word "Round" repeats 2 times'
  cases=$((cases + 1))

  # S2 on each of three trigger shapes -- a demonstrative, a pronoun and a connective adverb -- in
  # both of the unit kinds the extraction prints.
  write_lines "$tmp/s2-this.md" \
    '**This is the line nobody has published.** Every rival bounds its agent and none says where.'
  expect_red 'S2 bold opens "This"' "$tmp/s2-this.md" \
    'FAIL: S2 scan-layer unit opens with "This"'
  cases=$((cases + 1))

  write_lines "$tmp/s2-they.md" \
    '**They rent the yield from two supplier banks.** Rate parity follows in a quarter.'
  expect_red 'S2 bold opens "They"' "$tmp/s2-they.md" \
    'FAIL: S2 scan-layer unit opens with "They"'
  cases=$((cases + 1))

  write_lines "$tmp/s2-however.md" \
    '## However The Yield Is Rented'
  expect_red 'S2 heading opens "However"' "$tmp/s2-however.md" \
    'FAIL: S2 scan-layer unit opens with "However"'
  cases=$((cases + 1))

  # THE WHOLE S2 VOCABULARY, one fixture per word. The three shapes above pin `this`, `they` and
  # `however` and nothing else, so deleting any of the other fourteen from `S2_WORDS` left the suite
  # green. The closed list IS the check's whole substance -- `references/briefing-template.md`
  # explicitly declines to enumerate it, so this script is the only place the vocabulary exists and
  # the suite has to hold all of it.
  #
  # The list is pinned by the LITERAL below and NOT by iterating `S2_WORDS`, which would be a
  # tautology: a loop reading the list under test cannot see a word deleted from it. MEASURED
  # 2026-09-07 on a scratch copy, with the real tree unmutated -- written as `for sw in $S2_WORDS`,
  # deleting `therefore` from `S2_WORDS` left `--selftest` at exit 0. Read from this literal, the
  # same deletion reds on the `therefore` fixture. The second loop closes the other direction: a
  # word ADDED to `S2_WORDS` and not pinned here reds too, so the two lists cannot drift apart. ONE
  # case for both loops, because it is one assertion made N times.
  s2vocab="this that these those they them it its there however therefore additionally furthermore \
moreover also thus hence"
  nw=0
  for sw in $s2vocab; do
    nw=$((nw + 1))
    write_lines "$tmp/s2-word.md" "**$sw the yield is rented.**"
    check_file "$tmp/s2-word.md"
    case "$FAILS" in
      *"FAIL: S2 scan-layer unit opens with \"$sw\""*) : ;;
      *) printf 'SELFTEST FAIL: S2 vocabulary word "%s" did not go red; got: %s\n' \
           "$sw" "${FAILS:-<no findings>}" >&2
         return 1 ;;
    esac
  done
  for sw in $S2_WORDS; do
    case " $s2vocab " in
      *" $sw "*) : ;;
      *) printf 'SELFTEST FAIL: S2_WORDS carries "%s", which no selftest case pins\n' "$sw" >&2
         return 1 ;;
    esac
  done
  if [ "$nw" -lt 2 ]; then
    printf 'SELFTEST FAIL: the pinned S2 vocabulary holds %s words; the loop proved nothing\n' \
      "$nw" >&2
    return 1
  fi
  printf 'SELFTEST red OK   %-30s -> all %s pinned S2 words red\n' 'S2 whole vocabulary' "$nw"
  cases=$((cases + 1))

  # S2 GREEN on two openers the exemplar actually uses, which is the other half of the rule: a unit
  # that names its own subject stands alone. `The` and `Not` are one edit away from the trigger list
  # and must stay off it -- MEASURED, `build/briefing.md:14,16,18` open `Not`, `The`, `The`.
  write_lines "$tmp/s2-the.md" \
    '**The yield is rented and one reference is conflicted.** Rate parity follows in a quarter.' \
    '' \
    '**Not one of the six says where its agent stops.** All six bound an agent that touches money.'
  expect_green 'S2 green on "The" and "Not"' "$tmp/s2-the.md"
  cases=$((cases + 1))

  # An absent and an empty target are FAILURES. Without these two the whole script could be pointed
  # at nothing and report two clean checks.
  expect_red 'absent file' "$tmp/absent.md" 'no brief to grade'
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty file' "$tmp/empty.md" 'no brief to grade'
  cases=$((cases + 1))

  # THE RED ARTEFACT. It must red BOTH checks, because a fixture that reds one leaves the other
  # proved by this file's own minimal strings alone. It is a committed artefact: if it is absent, say
  # so by path and fail, rather than stubbing it here and grading this script against its own idea of
  # a scan-blind brief.
  fixture="$ROOT/tools/fixtures/scan-blind-brief.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no scan-blind red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  check_file "$fixture"
  missing=""
  for id in S1 S2; do
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
  printf 'SELFTEST red OK   %-30s -> both checks red\n' 'scan-blind-brief.md'
  cases=$((cases + 1))

  # THE EXEMPLAR ASSERTION, and the one that must never be weakened to reach green. If
  # `build/briefing.md` goes red here, the finding is the answer: report it and stop. Editing a
  # pattern until the accepted brief passes is how a sibling rule ended up running backwards against
  # the artefact it was meant to grade -- and `build/check_exemplar.sh` pins the brief's SHA256, so
  # the other direction is not available either.
  expect_green 'exemplar build/briefing.md' "$ROOT/$DEFAULT_TARGET"
  cases=$((cases + 1))

  # P1: the whole script as a child, green, in --check mode with NO target, so the default target is
  # the thing under test and the documented default is exercised by the run rather than by prose.
  proc="$tmp/proc-green"
  make_proc_root "$proc"
  cp "$tmp/clean.md" "$proc/$DEFAULT_TARGET"
  expect_proc_green 'child, clean default target' "$proc" 'SCAN-LAYER-OK' '--check'
  cases=$((cases + 1))

  # The OK line's check count must be derived, not asserted. Two checks ran, so it must say 2.
  case "$PROC_OUT" in
    *'SCAN-LAYER-OK (2 checks, 0 findings in build/briefing.md)'*) : ;;
    *) printf 'SELFTEST FAIL: OK line did not report 2 checks; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-29s -> "%s"\n' 'OK line check count' "$PROC_OUT"
  cases=$((cases + 1))

  # P2: the same child on a SCAN-BLIND default target. Exit non-zero, the finding on the stream, and
  # an explicit guard inside expect_proc_red that SCAN-LAYER-OK was NOT printed.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  cp "$fixture" "$proc/$DEFAULT_TARGET"
  expect_proc_red 'child, scan-blind default' "$proc" 'FAIL: S1 sibling leading word' '--check'
  cases=$((cases + 1))

  # P3: the child with a path ARGUMENT naming a file that does not exist, which is both the argument
  # dispatch and the missing-file failure, proved in the process that actually exits.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child, absent path argument' "$proc" 'no brief to grade' '--check' 'build/nope.md'
  cases=$((cases + 1))

  # P4: EXTRACTION MODE on the exemplar, as a child, with NO argument at all -- the default mode and
  # the default target together. Exit 0, and the header line asserted with the exemplar's MEASURED
  # counts: 11 headings (the h1 plus the ordered ten of references/briefing-template.md) and 13 bold
  # runs (9 claim-headers plus `**Round**` in four table cells). The word count is printed and
  # asserted only as a NUMBER, never against a threshold -- see exclusion 4.
  proc="$tmp/proc-extract"
  make_proc_root "$proc"
  cp "$ROOT/$DEFAULT_TARGET" "$proc/$DEFAULT_TARGET"
  expect_proc_green 'child, extraction on exemplar' "$proc" \
    'SCAN-LAYER (build/briefing.md): 11 headings, 13 bold runs,'
  cases=$((cases + 1))

  # The word count, measured from the printed units themselves rather than asserted as a constant a
  # second time: the header must report exactly what the unit lines contain.
  w="$(printf '%s\n' "$PROC_OUT" | sed -e '1d' | wc -w | tr -d ' ')"
  case "$PROC_OUT" in
    *"bold runs, $w words"*) : ;;
    *) printf 'SELFTEST FAIL: header word count is not the printed units word count (%s); got: %s\n' \
         "$w" "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-29s -> %s words in the printed units\n' 'extraction word count' "$w"
  cases=$((cases + 1))

  # The extraction must print the units themselves, headings WITH their `#` prefix and bold runs
  # WITHOUT their `**` markers, in document order.
  case "$PROC_OUT" in
    *"## $FX_FIRST"*) : ;;
    *) printf 'SELFTEST FAIL: extraction dropped a heading; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *'**Round**'*)
      printf 'SELFTEST FAIL: extraction kept the ** markers; got: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  printf 'SELFTEST detail OK %-29s -> headings keep #, bold runs lose **\n' 'extraction shape'
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  printf 'SELFTEST OK: %s cases, S1 red on a repeated first-column label under the allowlisted `Capability` header and on a repeated list opener and on a list marker followed by a TAB, green on the same words made distinct, green on an entity roster under `Company` and on an unknown `Vendor` header (the allowlist proved live in both directions), green on a repeat in a later column and at another indent depth and in a bold claim-header and in a heading (exclusions 1, 2 and 3 each proved live), four normalisation shapes collided (bold, curly quote, link, trailing stop), S2 red on a demonstrative and a pronoun and a connective and on every one of the %s pinned S2 vocabulary words and green on "The" and "Not", absent and empty red, %s red on both checks, exemplar green, 4 child-process cases (clean default green with the token and a derived count of 2, scan-blind default red with no token, absent argument red, extraction on the exemplar green at 11 headings and 13 bold runs with a word count derived from the printed units)\n' \
    "$cases" "$nw" "tools/fixtures/scan-blind-brief.md"
}

# --- main -----------------------------------------------------------------------------------------
# require_target is the one place the missing/empty message is written, so extraction mode and check
# mode fail identically on a target that is not there.
require_target() {
  if [ ! -s "$1" ]; then
    printf 'FAIL: no brief to grade at %s (missing or empty)\n' "$1" >&2
    exit 1
  fi
}

main_extract() {
  local target recs body h b w
  cd "$ROOT"
  target="${1:-$DEFAULT_TARGET}"
  require_target "$target"

  recs="$(units "$target")"
  if [ -z "$recs" ]; then
    h=0
    b=0
    w=0
    body=""
  else
    h="$(printf '%s\n' "$recs" | awk -F'\t' '$2 == "H"' | wc -l | tr -d ' ')"
    b="$(printf '%s\n' "$recs" | awk -F'\t' '$2 == "B"' | wc -l | tr -d ' ')"
    body="$(printf '%s\n' "$recs" | cut -f4-)"
    w="$(printf '%s\n' "$body" | wc -w | tr -d ' ')"
  fi

  printf 'SCAN-LAYER (%s): %s headings, %s bold runs, %s words\n' "$target" "$h" "$b" "$w"
  if [ -n "$body" ]; then
    printf '%s\n' "$body"
  fi
}

main_check() {
  local target
  cd "$ROOT"
  target="${1:-$DEFAULT_TARGET}"
  check_file "$target"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  printf 'SCAN-LAYER-OK (%s checks, 0 findings in %s)\n' "$CHECKS_RUN" "$target"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  elif [ "${1:-}" = "--check" ]; then
    shift
    main_check "${1:-}"
  else
    main_extract "${1:-}"
  fi
fi
