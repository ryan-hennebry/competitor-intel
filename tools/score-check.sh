#!/usr/bin/env bash
# The candidate score lint. It grades one run-authored selection record, `output/review/selection.md`,
# collects every finding, and fails closed.
#
# THE ABSTRACTION. Phase 1 of `docs/history/pipeline.md` scores a pool of candidates down to the final
# N the brief profiles. That scoring is the single decision the whole brief rests on: every later
# phase spends its budget on the companies this step kept, and a rival scored out here is invisible
# to every downstream gate. `build/build.py`'s `audit()` grades the rendered artefact, so it can see
# what the brief SAYS about the eight companies in it and nothing at all about the sixth that should
# have been the third. The selection record is where the run shows its rubric -- the axes, the scale,
# the per-candidate scores, the arithmetic, and the two proof lines Phase 1 requires -- and this
# script grades that record.
#
# WHY IT EXISTS. `docs/history/pipeline.md`, in the paragraph headed "Both rules block the Phase 2
# fan-out", states that "The selection record carries two proof lines: each held candidate with its
# measured values, the registry consulted and the outcome, excluded or unknown and scored; and the
# incumbent in the final N, or the slot recorded absent with the scores or blocked with the fetch
# failure." Nothing has ever enforced that sentence. A run that scored nothing, ranked nothing and
# recorded neither proof line rendered green through `audit()`, `tools/thesis-check.sh`,
# `tools/gap-test.sh`, `tools/scan-layer.sh`, `tools/ai-smell.sh` and `tools/date-stamp.sh` alike,
# because none of them reads the selection step at all. `docs/DESIGN.md` names that shape by name: an
# absolute claim in a governing file wants a check that goes red when the claim stops holding, or the
# claim goes. Q4 is that check, and Q1 to Q3 are what make Q4 mean something -- a proof line under a
# rubric nobody declared, on scores that do not add up, proves nothing.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name, so
# this is a standalone script the pipeline invokes, exactly as `tools/thesis-check.sh`,
# `tools/gap-test.sh`, `tools/ai-smell.sh`, `tools/date-stamp.sh`, `tools/scan-layer.sh` and the ICP
# floor are standalone build-blocking lints. NOT a review pass either: `docs/history/review/` holds one
# file per pass and every pass there is a JUDGEMENT dispatched to a subagent, while this is a
# mechanical grade of one file that a run executes and reads the exit code of.
#
# It runs at the END OF PHASE 1, before the Phase 2 extraction fan-out, which is the moment the
# decision it grades is still cheap to change: after the fan-out a re-scored pool costs every
# extraction subagent again.
#
# It collects every finding and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is. A record that breaks all four checks
# reports all four.
#
# THE RECORD FORMAT, and why it is this shape. Six header keys at column 0, each exactly once, before
# the first `### ` -- `captured`, `pool`, `scored`, `selected`, `axes`, `scale`. Then free prose, then
# `---`, then one `### <Name>` block per candidate carrying `axes:`, `total:` and `outcome:`, then the
# two mandatory singleton blocks `### Shell hold` and `### Incumbent slot` carrying `hold:` and
# `incumbent:`. Every field value sits WHOLLY ON ONE LINE and every field line starts at column 0, so
# the format is greppable and a wrap cannot hide a field -- the same discipline `output/review/gaps.md`
# and `tools/gap-test.sh` hold. A `key: value` line whose key is not one of the recognised names is
# skipped as prose, and so is any line whose text before the colon carries whitespace: the record is a
# document a person reads, and the failure of an unknown key surfaces as the field it was meant to be
# going missing, which the check reports by name.
#
# FOUR CLOSED VOCABULARIES, written once each at `S_HEADER_KEYS`, `S_OUTCOME_TAGS`, `S_HOLD_TAGS` and
# `S_INCUMBENT_TAGS`. The three tag vocabularies are matched by a WHOLE-TOKEN prefix test against
# `TAG. `, never by a substring search, so neither a tag word sitting mid-sentence nor a tag's letters
# opening a longer word can pass as a classification. A value that is exactly the tag, with or without
# its full stop and with no sentence after it, is reported as its own defect: a classification with no
# reason attached is the paperwork this lint exists to stop.
#
# `grep` is wrapped to `ugrep` in the interactive shell, where a pattern starting with `--` parses as
# an option. Inside this script the parsing is `awk` and not `grep`: the units are positional (a field
# line's block, a block's position in the ranking, a header key's position relative to the first
# block) and a line-matching tool cannot express position.
#
# WHAT IT DELIBERATELY DOES NOT CHECK, and why each one is absent rather than forgotten:
#
#   1. WHETHER A SCORE IS RIGHT. Whether Hooli really rates 5 on substitution is the judgement the
#      run is paid for and no shell script can grade it. What is mechanical is whether the axes were
#      declared, whether the scores are on the declared scale, whether they add up, whether the
#      ranking is a ranking, and whether the two proof lines carry the evidence Phase 1 names.
#   2. THE POOL ITSELF. `pool:` is the run's own count of what it considered. Nothing here can see the
#      candidates that were never written down; the check asserts only that the three counts are
#      consistent with each other and with the blocks present.
#   3. THE SNAPSHOTS. Whether a selected candidate later got a snapshot is `build/build.py`'s cohort
#      work. Grading it here would need the run directory, which this lint deliberately does not
#      require, because it runs BEFORE the fan-out that produces one.
#   4. THE BRIEF. This lint reads the selection record alone. Whether the final N reached the Threat
#      Landscape is `tools/gap-test.sh`'s G1, which grades the ledger against the rendered table.
#   5. THE REGISTRY NAME'S TRUTH. Q4 requires a hold other than `none` to NAME the registry consulted
#      -- the word `registry` or a capitalised proper noun after the sentence's first word. Whether
#      Companies House actually says what the sentence claims is a review-pass judgement.
#
# PRECONDITION: none beyond the record existing. No network, no MKT1 call, no env var, no build
# artefact, no run directory, no browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_RECORD="output/review/selection.md"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

# Incremented once per check that ACTUALLY RUNS, so the success line cannot claim four checks while
# two run. Same intent as `CHECKS_RUN` in `tools/gap-test.sh`, `tools/scan-layer.sh` and
# `tools/date-stamp.sh`, derived from execution rather than from a table. On the fail-closed path it
# stays 0 and the caller exits 1, so the OK line is never printed with a count of zero.
CHECKS_RUN=0

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# THE FOUR CLOSED VOCABULARIES, and the only place any of them is written.
#
# The six header keys. Together they are the RUBRIC: what was scored (`pool`, `scored`, `selected`),
# on what axes and what scale (`axes`, `scale`), and for which run (`captured`).
S_HEADER_KEYS="captured pool scored selected axes scale"

# The three candidate outcomes. A candidate is in the final N (`selected`), out of it (`cut`), or
# waiting on evidence that had not arrived when the pool was scored (`held`). `held` is the state the
# Phase 1 shell rule produces and is why `### Shell hold` exists.
S_OUTCOME_TAGS="selected cut held"

# The three shell-hold states. `none` means no candidate was held. `excluded` and `unknown` are the
# two outcomes `docs/history/pipeline.md` names for a held candidate after the registry was consulted.
S_HOLD_TAGS="none excluded unknown"

# The five incumbent-slot states. `filled` is an incumbent in the final N. `absent` is the slot
# recorded absent WITH THE SCORES that decided it. `blocked` is a page that could not be fetched, the
# state `references/provenance.md` reserves for a 403, 401, 429 or LinkedIn 999. `not-opened` is the
# run whose job description never triggered the incumbent rule at all. `unknown` is the state the
# exemplar's own record is in: the trigger was never recorded either way, so the slot cannot be read
# off the run's retained evidence in either direction. That is NOT `not-opened`, which claims the
# trigger demonstrably did not fire; `S_HOLD_TAGS` has carried `unknown` for exactly this since it
# was written, and the incumbent line needs it for the same reason. A durable change to this
# vocabulary belongs in `docs/history/pipeline.md` under `AGENTS.md`'s routing rule, not here.
S_INCUMBENT_TAGS="filled absent blocked not-opened unknown"

# The two mandatory singleton blocks, by name. Every other `### ` block is a candidate.
SHELL_BLOCK="Shell hold"
INCUMBENT_BLOCK="Incumbent slot"

# THE AXIS COUNT IS THE RECORD'S OWN, never a number written here.
# `references/stages/02-questions.md` has each run derive THREE TO FIVE selection axes from its own
# locked questions, so four is one legal shape and not the shape. The three rules that read a count
# take it from the record: Q1 asserts the header's `axes:` line names S_AXES_MIN to S_AXES_MAX
# distinct axes; Q2 asserts every candidate block scores exactly the count THAT header declares; Q3
# derives the total ceiling from the same count. A literal 4 here deadlocked any run that locked
# three or five axes -- the author's only exits were inventing an axis or dropping a real one, and
# both corrupt the one decision this record exists to show.
#
# When the header's count is unusable -- the key missing, duplicated, or outside the range -- Q1
# reports it and the count-derived rules in Q2 and Q3 DO NOT RUN, the same discipline `wscored` and
# `wselected` already follow: a comparison against a count the record never validly declared is one
# defect reported twice, and it sends the author to the wrong repair.
S_AXES_MIN=3
S_AXES_MAX=5

# The scale, written once and read by three rules. Q1 asserts `scale:` is exactly S_SCALE; Q2 grades
# every axis score against S_SCALE_MIN and S_SCALE_MAX; Q3 derives the ceiling as the record's axis
# count times S_SCALE_MAX, which is 20 on a four-axis record and 15 on a three-axis one. Widening
# the scale is one edit here, not four literals scattered through the awk.
S_SCALE="1-5"
S_SCALE_MIN=1
S_SCALE_MAX=5

# --- the emitter ----------------------------------------------------------------------------------
# record_fields() prints one TAB-separated record per unit, in document order:
#   line <TAB> block <TAB> key <TAB> value
# where block is `HEADER` for everything before the first `### `, key is `BLOCK` for a `### <Name>`
# heading, and every other record is a `key: value` line whose key is a single token at column 0. A
# key carrying whitespace is prose with a colon in it and is skipped, which is what makes the record's
# human header free text.
record_fields() {
  awk -v OFS='\t' '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    /^###[ \t]/ { blk = trim(substr($0, 4)); if (blk != "") print NR, blk, "BLOCK", blk; next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1)
      if (k ~ /[ \t]/) next
      print NR, (blk == "" ? "HEADER" : blk), k, trim(substr($0, i + 1))
    }
  ' "$1"
}

# header_value() prints the value of the FIRST header record for one key, or nothing. WHICH one it
# takes is unobservable, and deliberately so: every call site below is guarded by
# `header_count "$recs" <key>` being exactly 1, so the key it reads carries one record and
# first-vs-last cannot differ. A duplicated key is a Q1 finding in its own right, reported by the
# count rule, and the value rules do not run on it at all -- grading the first of two duplicates
# would pick a winner the record does not name.
header_value() {
  printf '%s\n' "$1" | awk -F'\t' -v k="$2" '$2 == "HEADER" && $3 == k { print $4; exit }'
}

header_count() {
  printf '%s\n' "$1" | awk -F'\t' -v k="$2" '$2 == "HEADER" && $3 == k { n++ } END { print n + 0 }'
}

# is_uint tests for a non-negative decimal integer with a bash `case`, whose patterns are
# whole-string anchored, so no regex quoting hazard reaches a wrapped grep.
is_uint() {
  case "$1" in
    '' | *[!0-9]*) return 1 ;;
  esac
  return 0
}

# --- Q2 -------------------------------------------------------------------------------------------
# q2_findings() prints one ready-made finding per line, sorted by source line so the output is
# deterministic. The rules are PER BLOCK -- how many of each field the block carries, and whether each
# value has the shape the rubric needs -- which is why this is awk and not a grep: a count is a
# property of a block, and a line-matching tool cannot see a block.
q2_findings() {
  awk -v f="$1" -v tags="$S_OUTCOME_TAGS" -v shellb="$SHELL_BLOCK" -v incb="$INCUMBENT_BLOCK" \
      -v want="$2" -v scale="$S_SCALE" -v smin="$S_SCALE_MIN" -v smax="$S_SCALE_MAX" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    # opens() returns the vocabulary token the value opens with, as `TOKEN. `, or "" for none. The
    # test is a WHOLE-TOKEN prefix: the tag must sit at position 1 and be followed by ". ", so a tag
    # word mid-sentence and a tag whose letters open a longer word both fail it.
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (substr(v, 1, length(arr[i]) + 2) == arr[i] ". ") return arr[i]
      return ""
    }
    # bare() returns the tag a value consists of ENTIRELY, with or without its full stop. That is a
    # classification with no reason attached, and it gets its own message: "not a tag" would send the
    # author to the vocabulary when the missing thing is the sentence.
    function bare(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (v == arr[i] "." || v == arr[i]) return arr[i]
      return ""
    }
    function flush() {
      if (blk == "" || !iscand) return
      if (naxes != 1)
        printf "%d\tFAIL: Q2 candidate \"%s\" carries %d axes: lines, want exactly 1, at %s:%d\n", \
          bline, blk, naxes, f, bline
      if (ntotal != 1)
        printf "%d\tFAIL: Q2 candidate \"%s\" carries %d total: lines, want exactly 1, at %s:%d\n", \
          bline, blk, ntotal, f, bline
      if (nout != 1)
        printf "%d\tFAIL: Q2 candidate \"%s\" carries %d outcome: lines, want exactly 1, at %s:%d\n", \
          bline, blk, nout, f, bline
    }
    /^###[ \t]/ {
      flush()
      blk = trim(substr($0, 4)); bline = NR
      iscand = (blk != "" && blk != shellb && blk != incb)
      naxes = 0; ntotal = 0; nout = 0
      next
    }
    blk == "" { next }
    !iscand { next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1); v = trim(substr($0, i + 1))
      if (k ~ /[ \t]/) next
      if (k == "axes") {
        naxes++
        n = split(v, a, /[ \t]+/)
        # `want` is the count the header declared, or -1 when Q1 already reported that the axes: line
        # in the header is missing, duplicated or out of range. At -1 the arity rule is skipped and
        # the scores present are still graded: a score off the scale is a defect whatever the count.
        # No apostrophe survives in here -- the whole awk program is one single-quoted shell string.
        if (want >= 0 && n != want) {
          printf "%d\tFAIL: Q2 candidate \"%s\" scores %d axes, want the %d integers the header declares, on the declared %s scale, at %s:%d: \"%s\"\n", \
            NR, blk, n, want, scale, f, NR, substr(v, 1, 40)
        } else {
          for (i = 1; i <= n; i++) {
            if (a[i] !~ /^[0-9]+$/)
              printf "%d\tFAIL: Q2 candidate \"%s\" scores \"%s\" on axis %d, which is not an integer, at %s:%d\n", \
                NR, blk, a[i], i, f, NR
            else if (a[i] + 0 < smin || a[i] + 0 > smax)
              printf "%d\tFAIL: Q2 candidate \"%s\" scores %s on axis %d, which is off the %s scale, at %s:%d\n", \
                NR, blk, a[i], i, scale, f, NR
          }
        }
      } else if (k == "total") {
        ntotal++
        if (v !~ /^[0-9]+$/)
          printf "%d\tFAIL: Q2 candidate \"%s\" carries total: \"%s\", which is not a single integer, at %s:%d\n", \
            NR, blk, substr(v, 1, 24), f, NR
      } else if (k == "outcome") {
        nout++
        t = opens(v, tags)
        if (t == "") {
          b = bare(v, tags)
          if (b != "")
            printf "%d\tFAIL: Q2 candidate \"%s\" carries outcome: %s with no sentence after it; every outcome states why, at %s:%d\n", \
              NR, blk, b, f, NR
          else
            printf "%d\tFAIL: Q2 candidate \"%s\" opens its outcome \"%s\", which is not one of %s followed by \". \", at %s:%d\n", \
              NR, blk, substr(v, 1, 28), tags, f, NR
        }
        # There is no "opens() matched but carries no sentence" arm, because that state cannot be
        # reached: `v` is trimmed above, so a value opening `TAG. ` has a non-space character after
        # the space, and a value that IS the bare tag never matches opens() at all -- bare() catches
        # it and reports it by name.
      }
    }
    END { flush() }
  ' "$1" | sort -n | cut -f2-
}

# --- Q3 -------------------------------------------------------------------------------------------
# q3_findings() grades the arithmetic and the ranking. `want_scored` and `want_selected` are the
# header's own counts, or -1 when Q1 already reported that the key is missing or malformed -- a
# comparison against a number that is not a number is a second report of one defect.
#
# A block whose axes or total did not parse is skipped by the sum rule and by the order rule rather
# than guessed at: Q2 reported the shape, and inventing an arithmetic finding on top of it sends the
# author to the wrong repair. A block scoring a count the header did not declare is skipped by the
# same rule for the same reason -- summing four integers against a three-axis rubric grades a block
# whose shape Q2 has already rejected.
#
# `waxes` is the header's axis count and `cap` is that count times the top of the declared scale,
# both -1 when Q1 reported the header's axes: line unusable.
q3_findings() {
  awk -v f="$1" -v shellb="$SHELL_BLOCK" -v incb="$INCUMBENT_BLOCK" -v tags="$S_OUTCOME_TAGS" \
      -v wscored="$2" -v wselected="$3" -v waxes="$4" -v cap="$5" -v scale="$S_SCALE" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (substr(v, 1, length(arr[i]) + 2) == arr[i] ". ") return arr[i]
      return ""
    }
    function flush(   i) {
      if (blk == "" || !iscand) return
      ncand++
      if (havetotal && havesum && tot != sum)
        printf "%d\tFAIL: Q3 candidate \"%s\" totals %d, but its axes sum to %d, at %s:%d\n", \
          totline, blk, tot, sum, f, totline
      # The ceiling is the axis count this record declares times the top of the declared scale,
      # passed in as `cap`, and skipped at -1 for the same reason Q2 skips its arity rule: a header
      # that never validly declared a count cannot ground a ceiling.
      if (havetotal && cap >= 0 && tot > cap)
        printf "%d\tFAIL: Q3 candidate \"%s\" totals %d, above the %d its %d axes on the %s scale allow, at %s:%d\n", \
          totline, blk, tot, cap, waxes, scale, f, totline
      if (havetotal) {
        if (prevname != "" && tot > prevtotal)
          printf "%d\tFAIL: Q3 candidate \"%s\" totals %d and appears after \"%s\", which totals %d; candidate blocks run in non-increasing total order, at %s:%d\n", \
            bline, blk, tot, prevname, prevtotal, f, bline
        prevname = blk; prevtotal = tot
      }
      if (tag == "selected") nsel++
    }
    /^###[ \t]/ {
      flush()
      blk = trim(substr($0, 4)); bline = NR
      iscand = (blk != "" && blk != shellb && blk != incb)
      havetotal = 0; havesum = 0; tot = 0; sum = 0; totline = bline; tag = ""
      next
    }
    blk == "" { next }
    !iscand { next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1); v = trim(substr($0, i + 1))
      if (k ~ /[ \t]/) next
      if (k == "axes") {
        n = split(v, a, /[ \t]+/)
        if (n > 0 && (waxes < 0 || n == waxes)) {
          ok = 1
          s = 0
          for (i = 1; i <= n; i++) {
            if (a[i] !~ /^[0-9]+$/) ok = 0
            else s += a[i] + 0
          }
          if (ok && !havesum) { havesum = 1; sum = s }
        }
      } else if (k == "total") {
        if (v ~ /^[0-9]+$/ && !havetotal) { havetotal = 1; tot = v + 0; totline = NR }
      } else if (k == "outcome") {
        if (tag == "") tag = opens(v, tags)
      }
    }
    END {
      flush()
      if (wscored >= 0 && ncand + 0 != wscored)
        printf "0\tFAIL: Q3 %s carries %d candidate blocks but its header says scored: %d\n", \
          f, ncand + 0, wscored
      if (wselected >= 0 && nsel + 0 != wselected)
        printf "0\tFAIL: Q3 %s carries %d candidates whose outcome tag is selected, but its header says selected: %d\n", \
          f, nsel + 0, wselected
    }
  ' "$1" | sort -n | cut -f2-
}

# --- Q4 -------------------------------------------------------------------------------------------
# q4_findings() grades the two proof lines `docs/history/pipeline.md` Phase 1 requires, and the
# CONSEQUENCE RULE each tag carries. A tag with no evidence behind it is the paperwork this check
# exists to stop: `incumbent: absent.` with no scores in the sentence is exactly the claim the
# pipeline says must be shown, recorded without showing it.
#
# Each rule fires only INSIDE a block that exists. A missing `### Shell hold` or `### Incumbent slot`
# is Q2's finding, and reporting it again here would send the author to two repairs for one defect.
# The field counts are per BLOCK INSTANCE, for the same reason.
q4_findings() {
  awk -v f="$1" -v shellb="$SHELL_BLOCK" -v incb="$INCUMBENT_BLOCK" \
      -v holdtags="$S_HOLD_TAGS" -v inctags="$S_INCUMBENT_TAGS" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (substr(v, 1, length(arr[i]) + 2) == arr[i] ". ") return arr[i]
      return ""
    }
    function bare(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (v == arr[i] "." || v == arr[i]) return arr[i]
      return ""
    }
    # names_registry() is the mechanical half of "the registry consulted": the sentence carries the
    # word `registry`, or a capitalised word somewhere after its first word. The first word is
    # excluded because every sentence starts capitalised, so counting it would make the rule vacuous.
    function names_registry(s,   n, i, w) {
      if (tolower(s) ~ /(^|[^a-z])registry([^a-z]|$)/) return 1
      n = split(s, w, /[ \t]+/)
      for (i = 2; i <= n; i++) if (w[i] ~ /^[A-Z]/) return 1
      return 0
    }
    function flush() {
      if (isshell && nhold != 1)
        printf "%d\tFAIL: Q4 block \"%s\" carries %d hold: lines, want exactly 1; the shell-hold proof line is one line, at %s:%d\n", \
          bline, shellb, nhold, f, bline
      if (isinc && ninc != 1)
        printf "%d\tFAIL: Q4 block \"%s\" carries %d incumbent: lines, want exactly 1; the incumbent proof line is one line, at %s:%d\n", \
          bline, incb, ninc, f, bline
    }
    /^###[ \t]/ {
      flush()
      blk = trim(substr($0, 4)); bline = NR
      isshell = (blk == shellb); isinc = (blk == incb)
      nhold = 0; ninc = 0
      next
    }
    blk == "" { next }
    !isshell && !isinc { next }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1); v = trim(substr($0, i + 1))
      if (k ~ /[ \t]/) next
      if (isshell && k == "hold") {
        nhold++
        t = opens(v, holdtags)
        if (t == "") {
          b = bare(v, holdtags)
          if (b != "")
            printf "%d\tFAIL: Q4 hold: %s carries no sentence after its tag; the shell-hold proof line states the outcome and its evidence, at %s:%d\n", \
              NR, b, f, NR
          else
            printf "%d\tFAIL: Q4 hold opens \"%s\", which is not one of %s followed by \". \", at %s:%d\n", \
              NR, substr(v, 1, 28), holdtags, f, NR
        } else {
          # opens() matched, so the value carries `TAG. ` and a non-space character after it: the
          # sentence cannot be empty here, and a value that is the bare tag was reported by bare().
          s = substr(v, length(t) + 3)
          if (t != "none" && !names_registry(s))
            printf "%d\tFAIL: Q4 hold: %s does not name the registry consulted in \"%s\"; a hold other than none was settled against a registry, so the sentence must carry the word \"registry\" or a capitalised proper noun after its first word, at %s:%d\n", \
              NR, t, substr(s, 1, 48), f, NR
        }
      } else if (isinc && k == "incumbent") {
        ninc++
        t = opens(v, inctags)
        if (t == "") {
          b = bare(v, inctags)
          if (b != "")
            printf "%d\tFAIL: Q4 incumbent: %s carries no sentence after its tag; the incumbent proof line states the outcome and its evidence, at %s:%d\n", \
              NR, b, f, NR
          else
            printf "%d\tFAIL: Q4 incumbent opens \"%s\", which is not one of %s followed by \". \", at %s:%d\n", \
              NR, substr(v, 1, 28), inctags, f, NR
        } else {
          # Same as the hold line above: opens() matched, so there is a sentence, and a value that is
          # the bare tag was already reported by bare() rather than by a second arm here.
          s = substr(v, length(t) + 3)
          if (t == "absent" && s !~ /[0-9]/)
            printf "%d\tFAIL: Q4 incumbent: absent carries no score in \"%s\"; a slot recorded absent is recorded WITH THE SCORES that decided it, so the sentence must carry at least one digit, at %s:%d\n", \
              NR, substr(s, 1, 48), f, NR
          else if (t == "blocked" && s !~ /[0-9]/ && tolower(s) !~ /fetch/)
            printf "%d\tFAIL: Q4 incumbent: blocked does not name the fetch failure in \"%s\"; blocked is reserved for a page that could not be fetched, so the sentence must carry an HTTP status (a digit) or the word \"fetch\", at %s:%d\n", \
              NR, substr(s, 1, 48), f, NR
          else if (t == "not-opened" && length(s) < 20)
            printf "%d\tFAIL: Q4 incumbent: not-opened says why in %d characters (\"%s\"); the sentence must say why the trigger did not fire, in at least 20, at %s:%d\n", \
              NR, length(s), s, f, NR
          else if (t == "unknown" && (length(s) < 20 || tolower(s) !~ /(retain|record|evidence)/))
            printf "%d\tFAIL: Q4 incumbent: unknown does not name what was not retained in \"%s\"; unknown means the slot was never recorded either way, so the sentence must say WHAT evidence is missing, in at least 20 characters and carrying the word \"retain\", \"record\" or \"evidence\", at %s:%d\n", \
              NR, substr(s, 1, 48), f, NR
        }
      }
    }
    END { flush() }
  ' "$1" | sort -n | cut -f2-
}

# --- the check ------------------------------------------------------------------------------------
# check_file populates FAILS for one record and ALWAYS returns 0; the caller decides. Same contract as
# `check_file` in `tools/gap-test.sh`, `tools/scan-layer.sh`, `tools/date-stamp.sh` and
# `tools/ai-smell.sh`, and it is what lets the selftest run every case in this shell without `set -e`
# ending the run at the first red.
check_file() {
  local rec="$1" recs blocks cands key n v tok dups rc oldifs \
    npool nscored nselected wscored wselected waxes wcap nhdr hkeys \
    ckeys=$'pool\nscored\nselected'

  FAILS=""
  CHECKS_RUN=0
  waxes=-1

  # FAIL CLOSED, four readings, four distinct messages, every check skipped when any of them fires. A
  # vacuous pass is the failure mode this whole file exists to prevent: four checks reporting no
  # findings on a record that does not exist is precisely the shape of green this repository treats as
  # a lie.
  if [ ! -e "$rec" ]; then
    add_fail "FAIL: no selection record to grade at $rec (missing)"
    return 0
  fi
  if [ ! -s "$rec" ]; then
    add_fail "FAIL: no selection record to grade at $rec (empty)"
    return 0
  fi

  recs="$(record_fields "$rec")"
  blocks="$(printf '%s\n' "$recs" | awk -F'\t' '$3 == "BLOCK" { print $2 }')"
  if [ -z "$blocks" ]; then
    add_fail "FAIL: no ### block in $rec; a selection record scores candidates in blocks"
  fi
  nhdr=0
  for key in $S_HEADER_KEYS; do
    n="$(header_count "$recs" "$key")"
    nhdr=$((nhdr + n))
  done
  if [ "$nhdr" -eq 0 ]; then
    add_fail "FAIL: no rubric header key in $rec; the rubric is declared by $S_HEADER_KEYS at column 0 before the first ### block"
  fi
  if [ -n "$FAILS" ]; then
    return 0
  fi

  # Every loop below runs under `IFS=$'\n'`, because a finding, a block name and a candidate name can
  # all carry a space. The header keys are a SPACE-delimited list, so they are converted to lines
  # here, before the split character changes, rather than being iterated as one token.
  hkeys="$(printf '%s\n' "$S_HEADER_KEYS" | tr ' ' '\n' | sed -e '/^$/d')"

  oldifs="$IFS"
  set -f
  IFS=$'\n'

  # --- Q1: the rubric is declared ----------------------------------------------------------------
  # Presence first, then shape, then the three counts and the order between them. Each key's value
  # rules are guarded by that key appearing exactly once: grading the value of a key reported missing
  # is one defect reported twice, and grading the first of two duplicates picks a winner the record
  # does not name.
  CHECKS_RUN=$((CHECKS_RUN + 1))
  for key in $hkeys; do
    n="$(header_count "$recs" "$key")"
    if [ "$n" -eq 0 ]; then
      add_fail "FAIL: Q1 header key \"$key:\" is missing from $rec; the rubric is declared by \
$S_HEADER_KEYS at column 0 before the first ### block"
    elif [ "$n" -gt 1 ]; then
      add_fail "FAIL: Q1 header key \"$key:\" appears $n times in $rec, want exactly 1"
    fi
  done

  # `docs/history/pipeline.md` names the value's form as well as the key: `captured: YYYY-MM-DD`. The
  # SHAPE alone is graded here and never the date itself -- comparing it to a run date is
  # `tools/thesis-check.sh`'s job, on a run directory this lint deliberately does not require. The
  # test is a `case`, copied from that script, whose patterns are whole-string anchored, so this is
  # exactly ^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$ with no quoting hazard on a wrapped grep.
  if [ "$(header_count "$recs" captured)" -eq 1 ]; then
    v="$(header_value "$recs" captured)"
    case "$v" in
      [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) : ;;
      *) add_fail "FAIL: Q1 header declares captured: \"$v\" in $rec, which is not a YYYY-MM-DD \
date; the record is dated in the one form every other artefact in this repository is dated in" ;;
    esac
  fi

  # THE SEPARATOR. `docs/history/pipeline.md` gives the record's shape as the header keys, then prose,
  # then a `---` line, then the candidate blocks, and the `---` is what makes the free prose above it
  # unambiguously prose. Counted before the first `### ` heading, because a `---` after the blocks
  # have started is not the separator between the header and the blocks at all.
  n="$(awk '/^###[ \t]/ { exit } /^---[ \t]*$/ { n++ } END { print n + 0 }' "$rec")"
  if [ "$n" -ne 1 ]; then
    add_fail "FAIL: Q1 $rec carries $n \"---\" lines at column 0 before the first ### block, want \
exactly 1; the record is the header keys, then prose, then a --- line, then the candidate blocks"
  fi

  # THE AXIS COUNT, read off the record and carried to Q2 and Q3 in `waxes`. The range is the one
  # `references/stages/02-questions.md` has the run derive; the count inside it is the run's own.
  if [ "$(header_count "$recs" axes)" -eq 1 ]; then
    v="$(header_value "$recs" axes)"
    rc="$(printf '%s\n' "$v" | awk '{ print NF }')"
    if [ "$rc" -lt "$S_AXES_MIN" ] || [ "$rc" -gt "$S_AXES_MAX" ]; then
      add_fail "FAIL: Q1 header names $rc scoring axes in $rec, want $S_AXES_MIN to $S_AXES_MAX, \
the range the run derives its selection axes in: \"$v\""
    else
      waxes="$rc"
    fi
    dups="$(printf '%s\n' "$v" | tr -s ' \t' '\n\n' | sed -e '/^$/d' | sort | uniq -d)"
    for tok in $dups; do
      [ -n "$tok" ] || continue
      add_fail "FAIL: Q1 header names the scoring axis \"$tok\" more than once in $rec; the \
axes are distinct or the scale means nothing"
    done
  fi

  if [ "$(header_count "$recs" scale)" -eq 1 ]; then
    v="$(header_value "$recs" scale)"
    if [ "$v" != "$S_SCALE" ]; then
      add_fail "FAIL: Q1 header declares scale: \"$v\" in $rec, want exactly $S_SCALE"
    fi
  fi

  npool=""
  nscored=""
  nselected=""
  for key in $ckeys; do
    if [ "$(header_count "$recs" "$key")" -ne 1 ]; then
      continue
    fi
    v="$(header_value "$recs" "$key")"
    if is_uint "$v"; then
      case "$key" in
        pool) npool="$v" ;;
        scored) nscored="$v" ;;
        selected) nselected="$v" ;;
      esac
    else
      add_fail "FAIL: Q1 header declares $key: \"$v\" in $rec, which is not a non-negative integer"
    fi
  done
  if [ -n "$npool" ] && [ -n "$nscored" ] && [ "$npool" -lt "$nscored" ]; then
    add_fail "FAIL: Q1 header declares pool: $npool and scored: $nscored in $rec; the pool is \
everything considered, so pool >= scored >= selected >= 1"
  fi
  if [ -n "$nscored" ] && [ -n "$nselected" ] && [ "$nscored" -lt "$nselected" ]; then
    add_fail "FAIL: Q1 header declares scored: $nscored and selected: $nselected in $rec; nothing \
can be selected that was not scored, so pool >= scored >= selected >= 1"
  fi
  if [ -n "$nselected" ] && [ "$nselected" -lt 1 ]; then
    add_fail "FAIL: Q1 header declares selected: $nselected in $rec; a selection record that selects \
nothing has no final N, so pool >= scored >= selected >= 1"
  fi

  # --- Q2: block shape ---------------------------------------------------------------------------
  CHECKS_RUN=$((CHECKS_RUN + 1))
  for rc in $(q2_findings "$rec" "$waxes"); do
    add_fail "$rc"
  done

  n="$(printf '%s\n' "$blocks" | awk -v b="$SHELL_BLOCK" '$0 == b { n++ } END { print n + 0 }')"
  if [ "$n" -ne 1 ]; then
    add_fail "FAIL: Q2 $rec carries $n \"### $SHELL_BLOCK\" blocks, want exactly 1"
  fi
  n="$(printf '%s\n' "$blocks" | awk -v b="$INCUMBENT_BLOCK" '$0 == b { n++ } END { print n + 0 }')"
  if [ "$n" -ne 1 ]; then
    add_fail "FAIL: Q2 $rec carries $n \"### $INCUMBENT_BLOCK\" blocks, want exactly 1"
  fi

  cands="$(printf '%s\n' "$blocks" \
    | awk -v s="$SHELL_BLOCK" -v i="$INCUMBENT_BLOCK" '$0 != s && $0 != i')"
  dups="$(printf '%s\n' "$cands" | sed -e '/^$/d' | sort | uniq -d)"
  for tok in $dups; do
    [ -n "$tok" ] || continue
    add_fail "FAIL: Q2 $rec carries more than one candidate block named \"$tok\"; want exactly one \
per candidate"
  done
  if [ -z "$cands" ]; then
    add_fail "FAIL: Q2 $rec carries no candidate block at all; the two singleton blocks are the \
proof lines, not the scoring"
  fi

  # --- Q3: the arithmetic and the ranking --------------------------------------------------------
  CHECKS_RUN=$((CHECKS_RUN + 1))
  wscored=-1
  wselected=-1
  [ -n "$nscored" ] && wscored="$nscored"
  [ -n "$nselected" ] && wselected="$nselected"
  wcap=-1
  if [ "$waxes" -ge 0 ]; then
    wcap=$((waxes * S_SCALE_MAX))
  fi
  for rc in $(q3_findings "$rec" "$wscored" "$wselected" "$waxes" "$wcap"); do
    add_fail "$rc"
  done

  # --- Q4: the two proof lines -------------------------------------------------------------------
  # The check with teeth. `docs/history/pipeline.md` Phase 1 has claimed these two lines since it was
  # written and nothing has ever read them.
  CHECKS_RUN=$((CHECKS_RUN + 1))
  for rc in $(q4_findings "$rec"); do
    add_fail "$rc"
  done

  IFS="$oldifs"
  set +f
  return 0
}

# --- the record -----------------------------------------------------------------------------------
# record_lines() prints the scoring record for one file: the derived counts, the rubric, then the
# candidates in document order with their per-axis breakdown, total and outcome tag, then the
# selected and cut split, then the two proof lines verbatim. Plain text, readable cold, and every
# number derived from the file.
record_lines() {
  awk -v f="$1" -v tags="$S_OUTCOME_TAGS" -v shellb="$SHELL_BLOCK" -v incb="$INCUMBENT_BLOCK" '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
    function opens(v, list,   n, i, arr) {
      n = split(list, arr, " ")
      for (i = 1; i <= n; i++) if (substr(v, 1, length(arr[i]) + 2) == arr[i] ". ") return arr[i]
      return ""
    }
    function flush() {
      if (blk == "" || !iscand) return
      nc++
      # Every ternary below is parenthesised: BSD awk, which is the awk on this machine, rejects a
      # bare `a == b ? x : y` in a printf argument list with "illegal statement".
      body = body sprintf("  %2d. %-22s %-14s total %-4s [%s]\n", nc, blk, \
        (ax == "" ? "(no axes)" : ax), (tot == "" ? "?" : tot), (tag == "" ? "no outcome" : tag))
      if (tag == "selected") { nsel++; sel = sel (sel == "" ? "" : ", ") blk }
      else if (tag == "cut") { ncut++; cut = cut (cut == "" ? "" : ", ") blk }
    }
    /^###[ \t]/ {
      flush()
      blk = trim(substr($0, 4)); iscand = (blk != "" && blk != shellb && blk != incb)
      ax = ""; tot = ""; tag = ""
      next
    }
    {
      i = index($0, ":")
      if (i < 2) next
      k = substr($0, 1, i - 1); v = trim(substr($0, i + 1))
      if (k ~ /[ \t]/) next
      if (blk == "") {
        if (k == "axes") rubric = v
        else if (k == "scale") scale = v
        next
      }
      if (blk == shellb) { if (k == "hold") hold = v; next }
      if (blk == incb) { if (k == "incumbent") inc = v; next }
      if (!iscand) next
      if (k == "axes") ax = v
      else if (k == "total") tot = v
      else if (k == "outcome") { tag = opens(v, tags); if (tag == "") tag = substr(v, 1, 16) }
    }
    END {
      flush()
      printf "SCORE-CHECK (%s): %d scored, %d selected, %d cut\n", f, nc + 0, nsel + 0, ncut + 0
      printf "rubric: %s, scale %s\n", \
        (rubric == "" ? "(no axes: line)" : rubric), (scale == "" ? "(no scale: line)" : scale)
      printf "\n%s", body
      printf "\nselected: %s\n", (sel == "" ? "(none)" : sel)
      printf "cut: %s\n", (cut == "" ? "(none)" : cut)
      printf "hold: %s\n", (hold == "" ? "(no hold: line)" : hold)
      printf "incumbent: %s\n", (inc == "" ? "(no incumbent: line)" : inc)
    }
  ' "$1"
}

# --- selftest -------------------------------------------------------------------------------------
# Proves each failure mode red on its own minimal fixture, proves all four vocabularies accepted in
# full from INDEPENDENT literals with a reverse membership check, proves each fail-closed path red
# with its own message, and runs the script as a child process so `main_check()`, `main_record()`, the
# defaults, the argument dispatch, the OK line and the non-zero exit are exercised by the run and not
# by prose. A check that has never gone red is an untested assertion.

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

# The clean record. FOUR candidates, so a defect can be planted in a block that is not the first, and
# an "always grade block 1" implementation cannot pass. Every red fixture below is this file plus
# exactly ONE defect, so a rule that stops working surfaces as a missing finding rather than as a
# fixture that was red for another reason all along.
write_clean_record() {
  local f="$1"
  write_lines "$f" \
    '# Candidate selection -- Northwind brief' \
    '' \
    'captured: 2026-09-02' \
    'pool: 14' \
    'scored: 4' \
    'selected: 2' \
    'axes: icp-fit substitution ai-claim reachability' \
    'scale: 1-5' \
    '' \
    'This header is prose and is ignored: everything between the keys and the first block is free text.' \
    '' \
    '---' \
    '' \
    '### Acme' \
    '' \
    'axes: 5 4 5 4' \
    'total: 18' \
    'outcome: selected. Same buyer, and the nearest substitute in the pool.' \
    '' \
    '### Borealis' \
    '' \
    'axes: 4 4 4 3' \
    'total: 15' \
    'outcome: selected. Ships the same workflow to the same buyer.' \
    '' \
    '### Vantor' \
    '' \
    'axes: 3 3 2 2' \
    'total: 10' \
    'outcome: cut. Sells to enterprise treasury teams and not to this buyer.' \
    '' \
    '### Meridian' \
    '' \
    'axes: 2 2 2 1' \
    'total: 7' \
    'outcome: held. Private and unscored on reach, held for the registry check.' \
    '' \
    '### Shell hold' \
    '' \
    'hold: excluded. Companies House shows the entity dissolved in 2024.' \
    '' \
    '### Incumbent slot' \
    '' \
    'incumbent: absent. The best-scoring incumbent reached 9 of 20 and lost the eighth slot.'
}

# THE SAME RECORD ON THREE AXES, and the only fixture here that is not the clean record plus one
# defect. It is a whole legal record in a shape the old fixed-4 rule could not express at all: three
# axis names in the header, three integers in every block, every total the sum of its own three, and
# a ceiling of 15 rather than 20. Written out in full rather than sed-derived from the clean record,
# because a fixture that is a transformation of another cannot show what the count changes.
write_three_axis_record() {
  local f="$1"
  write_lines "$f" \
    '# Candidate selection -- Northwind brief' \
    '' \
    'captured: 2026-09-02' \
    'pool: 14' \
    'scored: 4' \
    'selected: 2' \
    'axes: icp-fit substitution reachability' \
    'scale: 1-5' \
    '' \
    'Three axes, because this run locked three questions. The record declares its own rubric.' \
    '' \
    '---' \
    '' \
    '### Acme' \
    '' \
    'axes: 5 4 5' \
    'total: 14' \
    'outcome: selected. Same buyer, and the nearest substitute in the pool.' \
    '' \
    '### Borealis' \
    '' \
    'axes: 4 4 4' \
    'total: 12' \
    'outcome: selected. Ships the same workflow to the same buyer.' \
    '' \
    '### Vantor' \
    '' \
    'axes: 3 3 2' \
    'total: 8' \
    'outcome: cut. Sells to enterprise treasury teams and not to this buyer.' \
    '' \
    '### Meridian' \
    '' \
    'axes: 2 2 2' \
    'total: 6' \
    'outcome: held. Private and unscored on reach, held for the registry check.' \
    '' \
    '### Shell hold' \
    '' \
    'hold: excluded. Companies House shows the entity dissolved in 2024.' \
    '' \
    '### Incumbent slot' \
    '' \
    'incumbent: absent. The best-scoring incumbent reached 7 of 15 and lost the eighth slot.'
}

expect_red() {
  local label="$1" rec="$2" want="$3"
  check_file "$rec"
  case "$FAILS" in
    *"$want"*) printf 'SELFTEST red OK   %-34s -> %s' "$label" "$FAILS" ;;
    *) printf 'SELFTEST FAIL: %s did not go red on %s; got: %s\n' \
         "$label" "$want" "${FAILS:-<no findings>}" >&2
       return 1 ;;
  esac
}

expect_green() {
  local label="$1" rec="$2"
  check_file "$rec"
  if [ -n "$FAILS" ]; then
    printf 'SELFTEST FAIL: %s went red; got: %s\n' "$label" "$FAILS" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-34s -> no findings\n' "$label"
}

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main_check()`, `main_record()`, the
# `cd "$ROOT"`, the default record, the argument dispatch, the SCORE-CHECK-OK line, the record header
# and the non-zero exit would be exercised by nothing. That gap is load-bearing and not hypothetical:
# inside `OUT="$( (f) 2>&1 )"` bash suspends `set -e`, so an in-process case cannot see an abort at
# all, and it was `main()` on the real corpus that killed `tools/known-traps.sh` while its twelve
# in-process cases stayed green. The cases below copy this script into a fixture root and run it as a
# CHILD with its own fully armed `set -euo pipefail`, which is the invocation a run actually makes.
PROC_RC=0
PROC_OUT=""

make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/output/review"
  cp "${BASH_SOURCE[0]}" "$root/tools/score-check.sh"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/score-check.sh" "$@" 2>&1 )" || PROC_RC=$?
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
    *"$want"*) printf 'SELFTEST proc OK  %-34s -> exit 0, %s\n' "$label" "$want" ;;
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
    *SCORE-CHECK-OK*)
      printf 'SELFTEST FAIL: a red child run printed SCORE-CHECK-OK: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  printf 'SELFTEST proc red %-34s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named in
# the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure path
# -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp r r3 cases=0 key tag st it want proc nkey ntag nhold ninc fixture \
    rkeys rtags rholds rincs es esel ecut

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/score-check-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  r="$tmp/selection.md"
  write_clean_record "$r"

  # The scaffolding itself, green.
  expect_green 'clean record' "$r"
  cases=$((cases + 1))

  # --- Q1 ----------------------------------------------------------------------------------------
  # EVERY header key proved red by its own absence, one fixture per key, from an INDEPENDENT literal
  # and not by iterating `S_HEADER_KEYS`: a loop reading the list under test cannot see a key deleted
  # from it, and deleting a key would delete its own test case at the same time and mutate green. The
  # reverse loop closes the other direction, so a key ADDED to `S_HEADER_KEYS` and not pinned here is
  # a failure too.
  rkeys="captured pool scored selected axes scale"
  nkey=0
  for key in $rkeys; do
    nkey=$((nkey + 1))
    sed -e "/^$key:/d" "$r" >"$tmp/q1-nokey.md"
    check_file "$tmp/q1-nokey.md"
    case "$FAILS" in
      *"FAIL: Q1 header key \"$key:\" is missing"*) : ;;
      *) printf 'SELFTEST FAIL: deleting header key "%s" did not go red; got: %s\n' \
           "$key" "${FAILS:-<no findings>}" >&2
         return 1 ;;
    esac
  done
  for key in $S_HEADER_KEYS; do
    case " $rkeys " in
      *" $key "*) : ;;
      *) printf 'SELFTEST FAIL: S_HEADER_KEYS carries "%s", which no selftest case pins\n' \
           "$key" >&2
         return 1 ;;
    esac
  done
  if [ "$nkey" -ne 6 ]; then
    printf 'SELFTEST FAIL: the pinned header vocabulary holds %s keys, want 6\n' "$nkey" >&2
    return 1
  fi
  printf 'SELFTEST red OK   %-34s -> each of the %s pinned header keys red by its own absence\n' \
    'Q1 header key missing' "$nkey"
  cases=$((cases + 1))

  awk '{ print } /^pool: 14/ { print "pool: 14" }' "$r" >"$tmp/q1-dup.md"
  expect_red 'Q1 duplicated header key' "$tmp/q1-dup.md" \
    'FAIL: Q1 header key "pool:" appears 2 times'
  cases=$((cases + 1))

  # THE POSITION RULE. The key is present, spelled right and at column 0 -- and it sits INSIDE the
  # first candidate block, where it is not a rubric declaration at all. Without this case a checker
  # that grepped the whole file would pass.
  awk '/^scale: 1-5/ { next } /^### Acme/ { print; print "scale: 1-5"; next } { print }' "$r" \
    >"$tmp/q1-late.md"
  expect_red 'Q1 header key after the first ###' "$tmp/q1-late.md" \
    'FAIL: Q1 header key "scale:" is missing'
  cases=$((cases + 1))

  # THE COLUMN-0 FIELD RULE, header half. `record_fields()` has its own copy of the rule and it is
  # the copy every header lookup runs through, so the Q2 case below -- which reads the file directly
  # -- cannot reach it. Indented, `scale:` is prose, and the rubric is undeclared.
  sed -e 's/^scale: 1-5$/  scale: 1-5/' "$r" >"$tmp/q1-indented.md"
  expect_red 'Q1 indented header key' "$tmp/q1-indented.md" \
    'FAIL: Q1 header key "scale:" is missing'
  cases=$((cases + 1))

  # THE RANGE, red at BOTH ENDS and one axis outside each. Three, four and five axis names are all
  # legal shapes -- `write_three_axis_record()` below proves the three-axis end green end to end --
  # so the only counts that can red here are two and six.
  sed -e 's/^axes: icp-fit substitution ai-claim reachability$/axes: icp-fit substitution/' \
    "$r" >"$tmp/q1-axes2.md"
  expect_red 'Q1 two axes named' "$tmp/q1-axes2.md" \
    'FAIL: Q1 header names 2 scoring axes'
  cases=$((cases + 1))

  sed -e 's/^axes: icp-fit substitution ai-claim reachability$/axes: icp-fit substitution ai-claim reachability spend tenure/' \
    "$r" >"$tmp/q1-axes6.md"
  expect_red 'Q1 six axes named' "$tmp/q1-axes6.md" \
    'FAIL: Q1 header names 6 scoring axes'
  cases=$((cases + 1))

  # AND THE COUNT-DERIVED RULES ARE OFF on both, so an out-of-range header is ONE finding and not
  # five. Every candidate block still scores four, which a header declaring two or six axes does not
  # match; if Q2's arity rule ran against an unusable count the author would be sent to repair four
  # blocks that are fine.
  for fixture in "$tmp/q1-axes2.md" "$tmp/q1-axes6.md"; do
    check_file "$fixture"
    case "$FAILS" in
      *'scores 4 axes'*)
        printf 'SELFTEST FAIL: %s graded block arity against an out-of-range header; got: %s\n' \
          "$fixture" "$FAILS" >&2
        return 1 ;;
    esac
  done
  printf 'SELFTEST green OK %-34s -> Q2 arity and Q3 cap both skipped\n' 'Q1 out-of-range axis count'
  cases=$((cases + 1))

  sed -e 's/^axes: icp-fit substitution ai-claim reachability$/axes: icp-fit substitution icp-fit reachability/' \
    "$r" >"$tmp/q1-axesdup.md"
  expect_red 'Q1 the same axis named twice' "$tmp/q1-axesdup.md" \
    'FAIL: Q1 header names the scoring axis "icp-fit" more than once'
  cases=$((cases + 1))

  sed -e 's/^scale: 1-5$/scale: 1 to 5/' "$r" >"$tmp/q1-scale.md"
  expect_red 'Q1 scale is not 1-5' "$tmp/q1-scale.md" \
    'FAIL: Q1 header declares scale: "1 to 5"'
  cases=$((cases + 1))

  sed -e 's/^pool: 14$/pool: fourteen/' "$r" >"$tmp/q1-poolword.md"
  expect_red 'Q1 pool is not an integer' "$tmp/q1-poolword.md" \
    'FAIL: Q1 header declares pool: "fourteen"'
  cases=$((cases + 1))

  sed -e 's/^pool: 14$/pool: -3/' "$r" >"$tmp/q1-poolneg.md"
  expect_red 'Q1 pool is negative' "$tmp/q1-poolneg.md" \
    'FAIL: Q1 header declares pool: "-3"'
  cases=$((cases + 1))

  sed -e 's/^pool: 14$/pool: 3/' "$r" >"$tmp/q1-poolsmall.md"
  expect_red 'Q1 pool smaller than scored' "$tmp/q1-poolsmall.md" \
    'FAIL: Q1 header declares pool: 3 and scored: 4'
  cases=$((cases + 1))

  sed -e 's/^scored: 4$/scored: 1/' "$r" >"$tmp/q1-scoredsmall.md"
  expect_red 'Q1 scored smaller than selected' "$tmp/q1-scoredsmall.md" \
    'FAIL: Q1 header declares scored: 1 and selected: 2'
  cases=$((cases + 1))

  sed -e 's/^selected: 2$/selected: 0/' "$r" >"$tmp/q1-selzero.md"
  expect_red 'Q1 selected is zero' "$tmp/q1-selzero.md" \
    'FAIL: Q1 header declares selected: 0'
  cases=$((cases + 1))

  # THE DATE SHAPE, red on a date a person reads fine and `run_cohort()` cannot: the key is present,
  # once, at column 0, and only its form is wrong.
  sed -e 's/^captured: 2026-09-02$/captured: 2 September 2026/' "$r" >"$tmp/q1-capshape.md"
  expect_red 'Q1 captured is not YYYY-MM-DD' "$tmp/q1-capshape.md" \
    'FAIL: Q1 header declares captured: "2 September 2026"'
  cases=$((cases + 1))

  # THE SEPARATOR, red both ways: gone, and doubled. Both fixtures leave every header key, every
  # count and every block untouched, so the separator rule is the only rule that can see either.
  sed -e '/^---$/d' "$r" >"$tmp/q1-nosep.md"
  expect_red 'Q1 no --- separator' "$tmp/q1-nosep.md" \
    'carries 0 "---" lines at column 0 before the first ### block'
  cases=$((cases + 1))

  awk '{ print } /^---$/ { print "---" }' "$r" >"$tmp/q1-twosep.md"
  expect_red 'Q1 two --- separators' "$tmp/q1-twosep.md" \
    'carries 2 "---" lines at column 0 before the first ### block'
  cases=$((cases + 1))

  # --- Q2 ----------------------------------------------------------------------------------------
  # One case per sub-rule, and the field-count cases are planted under BOREALIS -- the SECOND
  # candidate block -- so an implementation that always grades block 1 fails them.
  sed -e '/^axes: 4 4 4 3$/d' "$r" >"$tmp/q2-noaxes.md"
  expect_red 'Q2 no axes: line, second block' "$tmp/q2-noaxes.md" \
    'FAIL: Q2 candidate "Borealis" carries 0 axes: lines'
  cases=$((cases + 1))

  awk '{ print } /^axes: 4 4 4 3$/ { print "axes: 4 4 4 3" }' "$r" >"$tmp/q2-twoaxes.md"
  expect_red 'Q2 two axes: lines, second block' "$tmp/q2-twoaxes.md" \
    'FAIL: Q2 candidate "Borealis" carries 2 axes: lines'
  cases=$((cases + 1))

  sed -e '/^total: 15$/d' "$r" >"$tmp/q2-nototal.md"
  expect_red 'Q2 no total: line, second block' "$tmp/q2-nototal.md" \
    'FAIL: Q2 candidate "Borealis" carries 0 total: lines'
  cases=$((cases + 1))

  # THE COLUMN-0 FIELD RULE. `total: 15` is present, spelled right and inside the right block -- and
  # INDENTED BY TWO SPACES, which makes its key carry whitespace and makes the line prose. The format
  # is greppable only if a field starts at column 0, so an indented field is a missing field and is
  # reported as one, by the count rule that would otherwise have counted it.
  sed -e 's/^total: 15$/  total: 15/' "$r" >"$tmp/q2-indented.md"
  expect_red 'Q2 indented total: line' "$tmp/q2-indented.md" \
    'FAIL: Q2 candidate "Borealis" carries 0 total: lines'
  cases=$((cases + 1))

  awk '{ print } /^total: 15$/ { print "total: 15" }' "$r" >"$tmp/q2-twototal.md"
  expect_red 'Q2 two total: lines, second block' "$tmp/q2-twototal.md" \
    'FAIL: Q2 candidate "Borealis" carries 2 total: lines'
  cases=$((cases + 1))

  sed -e '/^outcome: selected. Ships the same/d' "$r" >"$tmp/q2-noout.md"
  expect_red 'Q2 no outcome: line, second block' "$tmp/q2-noout.md" \
    'FAIL: Q2 candidate "Borealis" carries 0 outcome: lines'
  cases=$((cases + 1))

  awk '{ print } /^outcome: selected. Ships the same/ { print "outcome: selected. And again." }' \
    "$r" >"$tmp/q2-twoout.md"
  expect_red 'Q2 two outcome: lines, second block' "$tmp/q2-twoout.md" \
    'FAIL: Q2 candidate "Borealis" carries 2 outcome: lines'
  cases=$((cases + 1))

  sed -e 's/^axes: 3 3 2 2$/axes: 3 3 2/' "$r" >"$tmp/q2-axes3.md"
  expect_red 'Q2 three axis scores, third block' "$tmp/q2-axes3.md" \
    'FAIL: Q2 candidate "Vantor" scores 3 axes'
  cases=$((cases + 1))

  sed -e 's/^axes: 3 3 2 2$/axes: 3 3 two 2/' "$r" >"$tmp/q2-axesword.md"
  expect_red 'Q2 axis score not an integer' "$tmp/q2-axesword.md" \
    'FAIL: Q2 candidate "Vantor" scores "two" on axis 3'
  cases=$((cases + 1))

  # OFF THE SCALE, both ends. Each also moves the block's sum, so Q3 reports the arithmetic too --
  # one defect, two findings, which is the honest report: a 7 on a 1-5 scale is both an illegal score
  # and a total that no longer adds up.
  sed -e 's/^axes: 3 3 2 2$/axes: 7 3 2 2/' "$r" >"$tmp/q2-axeshigh.md"
  expect_red 'Q2 axis score above the scale' "$tmp/q2-axeshigh.md" \
    'FAIL: Q2 candidate "Vantor" scores 7 on axis 1, which is off the 1-5 scale'
  cases=$((cases + 1))

  sed -e 's/^axes: 3 3 2 2$/axes: 3 3 2 0/' "$r" >"$tmp/q2-axeslow.md"
  expect_red 'Q2 axis score below the scale' "$tmp/q2-axeslow.md" \
    'FAIL: Q2 candidate "Vantor" scores 0 on axis 4, which is off the 1-5 scale'
  cases=$((cases + 1))

  sed -e 's/^total: 15$/total: fifteen/' "$r" >"$tmp/q2-totalword.md"
  expect_red 'Q2 total is not an integer' "$tmp/q2-totalword.md" \
    'FAIL: Q2 candidate "Borealis" carries total: "fifteen"'
  cases=$((cases + 1))

  sed -e 's/^total: 15$/total: 8 7/' "$r" >"$tmp/q2-totaltwo.md"
  expect_red 'Q2 total is two numbers' "$tmp/q2-totaltwo.md" \
    'FAIL: Q2 candidate "Borealis" carries total: "8 7"'
  cases=$((cases + 1))

  sed -e 's/^outcome: cut\. .*$/outcome: dropped. Sells to enterprise treasury teams./' "$r" \
    >"$tmp/q2-badtag.md"
  expect_red 'Q2 outcome tag outside the three' "$tmp/q2-badtag.md" \
    'FAIL: Q2 candidate "Vantor" opens its outcome "dropped. Sells to enter'
  cases=$((cases + 1))

  # THE WHOLE-TOKEN PREFIX TEST, half one: the tag word sits MID-SENTENCE, where it is a word and not
  # a classification. A run that narrates its way to a tag has recorded a sentence, not a decision.
  sed -e 's/^outcome: cut\. .*$/outcome: The pool was scored and this one was cut. Enterprise only./' \
    "$r" >"$tmp/q2-midsentence.md"
  expect_red 'Q2 outcome tag mid-sentence' "$tmp/q2-midsentence.md" \
    'FAIL: Q2 candidate "Vantor" opens its outcome "The pool was scored and this'
  cases=$((cases + 1))

  # Half two, and the one `tools/gap-test.sh` shipped without a fixture in any of its three copies of
  # `opens()`: the value OPENS with the tag's letters and carries on into a LONGER WORD, so a test
  # missing the ". " terminator accepts it. The mid-sentence case above cannot see that degradation,
  # because its value does not open with a tag at all.
  sed -e 's/^outcome: cut\. .*$/outcome: cutover to enterprise treasury teams, so out./' "$r" \
    >"$tmp/q2-longword.md"
  expect_red 'Q2 outcome tag inside a longer word' "$tmp/q2-longword.md" \
    'FAIL: Q2 candidate "Vantor" opens its outcome "cutover to enterprise treas'
  cases=$((cases + 1))

  sed -e 's/^outcome: cut\. .*$/outcome: cut./' "$r" >"$tmp/q2-nosentence.md"
  expect_red 'Q2 outcome tag with no sentence' "$tmp/q2-nosentence.md" \
    'FAIL: Q2 candidate "Vantor" carries outcome: cut with no sentence after it'
  cases=$((cases + 1))

  sed -e '/^### Shell hold$/d' "$r" >"$tmp/q2-noshell.md"
  expect_red 'Q2 no Shell hold block' "$tmp/q2-noshell.md" \
    'carries 0 "### Shell hold" blocks, want exactly 1'
  cases=$((cases + 1))

  awk '{ print } /^### Shell hold$/ { print ""; print "### Shell hold"; print ""; \
        print "hold: none. Nothing was held." }' "$r" >"$tmp/q2-twoshell.md"
  expect_red 'Q2 two Shell hold blocks' "$tmp/q2-twoshell.md" \
    'carries 2 "### Shell hold" blocks, want exactly 1'
  cases=$((cases + 1))

  sed -e '/^### Incumbent slot$/d' "$r" >"$tmp/q2-noinc.md"
  expect_red 'Q2 no Incumbent slot block' "$tmp/q2-noinc.md" \
    'carries 0 "### Incumbent slot" blocks, want exactly 1'
  cases=$((cases + 1))

  awk '{ print } /^### Incumbent slot$/ { print ""; print "### Incumbent slot"; print ""; \
        print "incumbent: filled. Hooli took the eighth slot." }' "$r" >"$tmp/q2-twoinc.md"
  expect_red 'Q2 two Incumbent slot blocks' "$tmp/q2-twoinc.md" \
    'carries 2 "### Incumbent slot" blocks, want exactly 1'
  cases=$((cases + 1))

  sed -e 's/^### Meridian$/### Vantor/' "$r" >"$tmp/q2-dupname.md"
  expect_red 'Q2 duplicate candidate name' "$tmp/q2-dupname.md" \
    'carries more than one candidate block named "Vantor"'
  cases=$((cases + 1))

  # NO CANDIDATE AT ALL, with both singleton blocks still present, so the record is not empty and the
  # fail-closed path does not fire: the two proof lines are not the scoring.
  write_lines "$tmp/q2-nocand.md" \
    'captured: 2026-09-02' \
    'pool: 14' \
    'scored: 0' \
    'selected: 1' \
    'axes: icp-fit substitution ai-claim reachability' \
    'scale: 1-5' \
    '' \
    '---' \
    '' \
    '### Shell hold' \
    '' \
    'hold: none. Nothing was held.' \
    '' \
    '### Incumbent slot' \
    '' \
    'incumbent: not-opened. The job description names no incumbent category at all.'
  expect_red 'Q2 no candidate block' "$tmp/q2-nocand.md" \
    'carries no candidate block at all'
  cases=$((cases + 1))

  # THE OUTCOME VOCABULARY, all three proved ACCEPTED from an independent literal, one fixture per
  # tag, with the reverse membership check. The tag is swapped on MERIDIAN, the last block, and the
  # header's `selected:` is moved with it, because the count rule is Q3's and this case is about the
  # vocabulary alone.
  rtags="selected cut held"
  ntag=0
  for tag in $rtags; do
    ntag=$((ntag + 1))
    want=2
    [ "$tag" = "selected" ] && want=3
    sed -e "s/^outcome: held\. .*/outcome: $tag. A fixture outcome sentence./" "$r" \
      | sed -e "s/^selected: 2$/selected: $want/" >"$tmp/q2-tag.md"
    check_file "$tmp/q2-tag.md"
    if [ -n "$FAILS" ]; then
      printf 'SELFTEST FAIL: outcome tag "%s" was not accepted; got: %s\n' "$tag" "$FAILS" >&2
      return 1
    fi
  done
  for tag in $S_OUTCOME_TAGS; do
    case " $rtags " in
      *" $tag "*) : ;;
      *) printf 'SELFTEST FAIL: S_OUTCOME_TAGS carries "%s", which no selftest case pins\n' \
           "$tag" >&2
         return 1 ;;
    esac
  done
  if [ "$ntag" -ne 3 ]; then
    printf 'SELFTEST FAIL: the pinned outcome vocabulary holds %s tags, want 3\n' "$ntag" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-34s -> all %s pinned outcome tags accepted\n' 'Q2 outcome vocabulary' \
    "$ntag"
  cases=$((cases + 1))

  # --- Q3 ----------------------------------------------------------------------------------------
  # The sum rule, planted under the THIRD block, and on a total that is still a legal integer on a
  # legal scale: only the arithmetic is wrong.
  sed -e 's/^total: 10$/total: 11/' "$r" >"$tmp/q3-sum.md"
  expect_red 'Q3 total does not match its axes' "$tmp/q3-sum.md" \
    'FAIL: Q3 candidate "Vantor" totals 11, but its axes sum to 10'
  cases=$((cases + 1))

  # THE CAP. A block whose axes and total agree with each other and both sit above what the scale
  # allows -- so the cap is the only rule that can see it. Q2 reds the off-scale axes as well, which
  # is the same one defect reported by the two rules it breaks.
  sed -e 's/^axes: 5 4 5 4$/axes: 9 9 9 9/' -e 's/^total: 18$/total: 36/' "$r" >"$tmp/q3-cap.md"
  expect_red 'Q3 total above the four-axis cap' "$tmp/q3-cap.md" \
    'FAIL: Q3 candidate "Acme" totals 36, above the 20 its 4 axes on the 1-5 scale allow'
  cases=$((cases + 1))

  sed -e 's/^scored: 4$/scored: 5/' "$r" >"$tmp/q3-scored.md"
  expect_red 'Q3 block count against scored:' "$tmp/q3-scored.md" \
    'carries 4 candidate blocks but its header says scored: 5'
  cases=$((cases + 1))

  sed -e 's/^selected: 2$/selected: 3/' "$r" >"$tmp/q3-selected.md"
  expect_red 'Q3 selected tags against selected:' "$tmp/q3-selected.md" \
    'carries 2 candidates whose outcome tag is selected, but its header says selected: 3'
  cases=$((cases + 1))

  # THE WHOLE-TOKEN PREFIX TEST INSIDE Q3, green. Q3 has its own copy of opens(), and it is the copy
  # that decides `nsel` -- so a copy degraded to a substring search reads Vantor's sentence, which
  # says the word `selected` mid-sentence about a candidate that was CUT, as a selected tag, counts
  # three against the header's two and reds a clean record. Every other fixture keeps the tag words
  # out of its sentences, so nothing else in this suite can see that. Reused by the bare-record child
  # case below, which is the same trap in the fourth copy.
  sed -e 's/^outcome: cut\. .*$/outcome: cut. Not selected for the final N, sells to treasury teams./' \
    "$r" >"$tmp/q3-selword.md"
  expect_green 'Q3 tag word inside a cut sentence' "$tmp/q3-selword.md"
  cases=$((cases + 1))

  # THE RANKING, and the defect is a MOVED BLOCK rather than an edited number: Meridian, which totals
  # 7, is lifted whole and re-inserted before Acme, which totals 18. Every field, every sum and every
  # count is untouched, so the order rule is the only rule that can see it -- and the pair it must
  # compare is the first and second blocks, which an implementation grading one block at a time
  # cannot reach.
  sed -n '/^### Meridian$/,/^### Shell hold$/p' "$r" | sed -e '$d' >"$tmp/q3-block.txt"
  sed -e '/^### Meridian$/,/^### Shell hold$/{ /^### Shell hold$/!d; }' "$r" >"$tmp/q3-cut.md"
  awk 'FNR == NR { m[++k] = $0; next } \
       /^### Acme$/ { for (i = 1; i <= k; i++) print m[i] } \
       { print }' "$tmp/q3-block.txt" "$tmp/q3-cut.md" >"$tmp/q3-order.md"
  expect_red 'Q3 candidates out of rank order' "$tmp/q3-order.md" \
    'FAIL: Q3 candidate "Acme" totals 18 and appears after "Meridian", which totals 7'
  cases=$((cases + 1))

  # --- THE AXIS COUNT IS THE RECORD'S -----------------------------------------------------------
  # Three cases on a THREE-AXIS record, which is the shape `references/stages/02-questions.md` lets a
  # run lock and the old fixed-4 rule rejected outright. Green first, because a rule that reds three
  # axes deadlocks the stage that has to fix its own exit code; then the two count-derived rules
  # proved to be reading the record's three and not this script's four.
  r3="$tmp/three-axis.md"
  write_three_axis_record "$r3"
  expect_green 'three-axis record, whole and legal' "$r3"
  cases=$((cases + 1))

  # Q2's ARITY, and the count it wants is the header's. Vantor alone scores a fourth axis; on the
  # clean four-axis record this same line is legal, so nothing but the declared count can red it.
  sed -e 's/^axes: 3 3 2$/axes: 3 3 2 2/' "$r3" >"$tmp/q3ax-arity.md"
  expect_red 'Q2 arity against a three-axis header' "$tmp/q3ax-arity.md" \
    'FAIL: Q2 candidate "Vantor" scores 4 axes, want the 3 integers the header'
  cases=$((cases + 1))

  # And the sum rule stays SILENT on that block: its four integers sum to 10 against a declared total
  # of 8, which would be a second finding for one defect and the wrong repair.
  check_file "$tmp/q3ax-arity.md"
  case "$FAILS" in
    *'axes sum to'*)
      printf 'SELFTEST FAIL: the sum rule graded a block whose arity Q2 had rejected; got: %s\n' \
        "$FAILS" >&2
      return 1 ;;
  esac
  printf 'SELFTEST green OK %-34s -> no sum finding on a rejected arity\n' 'Q3 sum on a wrong arity'
  cases=$((cases + 1))

  # Q3's CEILING, derived as 3 x 5 = 15. Acme totals 18, which is above what three axes on this
  # scale can reach and BELOW the literal 20 this rule used to carry -- so a cap that stayed at 20
  # passes this fixture and only a derived one reds it. Q2 reds the off-scale 6s as well: one defect,
  # two rules, the same honest double report the four-axis cap case makes.
  sed -e 's/^axes: 5 4 5$/axes: 6 6 6/' -e 's/^total: 14$/total: 18/' "$r3" >"$tmp/q3ax-cap.md"
  expect_red 'Q3 cap derived from three axes' "$tmp/q3ax-cap.md" \
    'FAIL: Q3 candidate "Acme" totals 18, above the 15 its 3 axes on the 1-5 scale allow'
  cases=$((cases + 1))

  # --- Q4 ----------------------------------------------------------------------------------------
  sed -e '/^hold: excluded\./d' "$r" >"$tmp/q4-nohold.md"
  expect_red 'Q4 no hold: proof line' "$tmp/q4-nohold.md" \
    'FAIL: Q4 block "Shell hold" carries 0 hold: lines'
  cases=$((cases + 1))

  awk '{ print } /^hold: excluded\./ { print "hold: unknown. The registry did not answer." }' "$r" \
    >"$tmp/q4-twohold.md"
  expect_red 'Q4 two hold: proof lines' "$tmp/q4-twohold.md" \
    'FAIL: Q4 block "Shell hold" carries 2 hold: lines'
  cases=$((cases + 1))

  sed -e 's/^hold: excluded\..*$/hold: dissolved. Companies House shows the entity dissolved./' "$r" \
    >"$tmp/q4-holdtag.md"
  expect_red 'Q4 hold tag outside the three' "$tmp/q4-holdtag.md" \
    'FAIL: Q4 hold opens "dissolved. Companies House'
  cases=$((cases + 1))

  sed -e 's/^hold: excluded\..*$/hold: The registry search returned none. Nothing was held./' "$r" \
    >"$tmp/q4-holdmid.md"
  expect_red 'Q4 hold tag mid-sentence' "$tmp/q4-holdmid.md" \
    'FAIL: Q4 hold opens "The registry search returned'
  cases=$((cases + 1))

  sed -e 's/^hold: excluded\..*$/hold: nonetheless the entity is dissolved at Companies House./' "$r" \
    >"$tmp/q4-holdlong.md"
  expect_red 'Q4 hold tag inside a longer word' "$tmp/q4-holdlong.md" \
    'FAIL: Q4 hold opens "nonetheless the entity is di'
  cases=$((cases + 1))

  sed -e 's/^hold: excluded\..*$/hold: excluded./' "$r" >"$tmp/q4-holdbare.md"
  expect_red 'Q4 hold tag with no sentence' "$tmp/q4-holdbare.md" \
    'FAIL: Q4 hold: excluded carries no sentence after its tag'
  cases=$((cases + 1))

  # THE CONSEQUENCE RULE on the hold line: a hold other than `none` was settled against a registry, so
  # the sentence names it. The replacement is a complete sentence in ordinary English with nothing
  # capitalised after its first word and no `registry` in it -- which is exactly the paperwork shape.
  sed -e 's/^hold: excluded\..*$/hold: excluded. It turned out to be a shell with no trading history./' \
    "$r" >"$tmp/q4-holdnoreg.md"
  expect_red 'Q4 hold names no registry' "$tmp/q4-holdnoreg.md" \
    'FAIL: Q4 hold: excluded does not name the registry consulted'
  cases=$((cases + 1))

  sed -e '/^incumbent: absent\./d' "$r" >"$tmp/q4-noinc.md"
  expect_red 'Q4 no incumbent: proof line' "$tmp/q4-noinc.md" \
    'FAIL: Q4 block "Incumbent slot" carries 0 incumbent: lines'
  cases=$((cases + 1))

  awk '{ print } /^incumbent: absent\./ { print "incumbent: filled. Hooli took the slot." }' "$r" \
    >"$tmp/q4-twoinc.md"
  expect_red 'Q4 two incumbent: proof lines' "$tmp/q4-twoinc.md" \
    'FAIL: Q4 block "Incumbent slot" carries 2 incumbent: lines'
  cases=$((cases + 1))

  sed -e 's/^incumbent: absent\..*$/incumbent: missing. The best score was 9 of 20./' "$r" \
    >"$tmp/q4-inctag.md"
  expect_red 'Q4 incumbent tag outside the five' "$tmp/q4-inctag.md" \
    'FAIL: Q4 incumbent opens "missing. The best score w'
  cases=$((cases + 1))

  sed -e 's/^incumbent: absent\..*$/incumbent: The slot is absent. Nobody reached the top 8./' "$r" \
    >"$tmp/q4-incmid.md"
  expect_red 'Q4 incumbent tag mid-sentence' "$tmp/q4-incmid.md" \
    'FAIL: Q4 incumbent opens "The slot is absent. Nobod'
  cases=$((cases + 1))

  sed -e 's/^incumbent: absent\..*$/incumbent: absentee firms scored 9 of 20 and lost the slot./' "$r" \
    >"$tmp/q4-inclong.md"
  expect_red 'Q4 incumbent tag inside a longer word' "$tmp/q4-inclong.md" \
    'FAIL: Q4 incumbent opens "absentee firms scored 9 o'
  cases=$((cases + 1))

  sed -e 's/^incumbent: absent\..*$/incumbent: absent./' "$r" >"$tmp/q4-incbare.md"
  expect_red 'Q4 incumbent tag with no sentence' "$tmp/q4-incbare.md" \
    'FAIL: Q4 incumbent: absent carries no sentence after its tag'
  cases=$((cases + 1))

  # THE THREE CONSEQUENCE RULES on the incumbent line, one case each. `absent` without the scores is
  # the exact sentence `docs/history/pipeline.md` Phase 1 forbids: "the slot is recorded absent with the
  # scores that decided it".
  sed -e 's/^incumbent: absent\..*$/incumbent: absent. No incumbent reached the final list this time./' \
    "$r" >"$tmp/q4-incnodigit.md"
  expect_red 'Q4 incumbent absent, no score' "$tmp/q4-incnodigit.md" \
    'FAIL: Q4 incumbent: absent carries no score in'
  cases=$((cases + 1))

  sed -e 's/^incumbent: absent\..*$/incumbent: blocked. The page would not open to either client./' \
    "$r" >"$tmp/q4-incblocked.md"
  expect_red 'Q4 incumbent blocked, no failure named' "$tmp/q4-incblocked.md" \
    'FAIL: Q4 incumbent: blocked does not name the fetch failure'
  cases=$((cases + 1))

  sed -e 's/^incumbent: absent\..*$/incumbent: not-opened. No trigger./' "$r" >"$tmp/q4-incshort.md"
  expect_red 'Q4 incumbent not-opened, no reason' "$tmp/q4-incshort.md" \
    'FAIL: Q4 incumbent: not-opened says why in 11 characters'
  cases=$((cases + 1))

  # THE HOLD VOCABULARY, all three accepted from an independent literal with the reverse membership
  # check. One sentence serves all three: it names a registry, which `none` does not need and the
  # other two do.
  rholds="none excluded unknown"
  nhold=0
  for st in $rholds; do
    nhold=$((nhold + 1))
    sed -e "s/^hold: excluded\..*$/hold: $st. Companies House was consulted on the entity./" "$r" \
      >"$tmp/q4-hold.md"
    check_file "$tmp/q4-hold.md"
    if [ -n "$FAILS" ]; then
      printf 'SELFTEST FAIL: hold state "%s" was not accepted; got: %s\n' "$st" "$FAILS" >&2
      return 1
    fi
  done
  for st in $S_HOLD_TAGS; do
    case " $rholds " in
      *" $st "*) : ;;
      *) printf 'SELFTEST FAIL: S_HOLD_TAGS carries "%s", which no selftest case pins\n' "$st" >&2
         return 1 ;;
    esac
  done
  if [ "$nhold" -ne 3 ]; then
    printf 'SELFTEST FAIL: the pinned hold vocabulary holds %s states, want 3\n' "$nhold" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-34s -> all %s pinned hold states accepted\n' 'Q4 hold vocabulary' \
    "$nhold"
  cases=$((cases + 1))

  # And the SAME RULE proved green on the other half of its disjunction: the word `registry` in an
  # otherwise all-lowercase sentence. Without this case the rule could be "a capitalised word" alone
  # and the suite would not notice.
  sed -e 's/^hold: excluded\..*$/hold: excluded. The company registry lists the entity as dissolved./' \
    "$r" >"$tmp/q4-holdword.md"
  expect_green 'Q4 hold names a lowercase registry' "$tmp/q4-holdword.md"
  cases=$((cases + 1))

  # THE INCUMBENT VOCABULARY, all five accepted. One sentence satisfies all four consequence rules at
  # once -- it carries digits, it names a fetch, it runs past 20 characters, and it says what was not
  # retained -- so this case tests membership and the rules above test the consequences.
  rincs="filled absent blocked not-opened unknown"
  ninc=0
  for it in $rincs; do
    ninc=$((ninc + 1))
    sed -e "s/^incumbent: absent\..*$/incumbent: $it. The fetch returned 403, no evidence of the trigger was retained, and the best score was 9 of 20./" \
      "$r" >"$tmp/q4-inc.md"
    check_file "$tmp/q4-inc.md"
    if [ -n "$FAILS" ]; then
      printf 'SELFTEST FAIL: incumbent state "%s" was not accepted; got: %s\n' "$it" "$FAILS" >&2
      return 1
    fi
  done
  for it in $S_INCUMBENT_TAGS; do
    case " $rincs " in
      *" $it "*) : ;;
      *) printf 'SELFTEST FAIL: S_INCUMBENT_TAGS carries "%s", which no selftest case pins\n' \
           "$it" >&2
         return 1 ;;
    esac
  done
  if [ "$ninc" -ne 5 ]; then
    printf 'SELFTEST FAIL: the pinned incumbent vocabulary holds %s states, want 5\n' "$ninc" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-34s -> all %s pinned incumbent states accepted\n' \
    'Q4 incumbent vocabulary' "$ninc"
  cases=$((cases + 1))

  # `blocked` green on the OTHER half of its disjunction, the word `fetch` with no digit in the
  # sentence, for the same reason the hold case above exists.
  sed -e 's/^incumbent: absent\..*$/incumbent: blocked. The diligence page refused every fetch./' \
    "$r" >"$tmp/q4-incfetch.md"
  expect_green 'Q4 incumbent blocked, fetch named' "$tmp/q4-incfetch.md"
  cases=$((cases + 1))

  # THE `unknown` CONSEQUENCE RULE, both ways. `unknown` is the slot nobody recorded either way, and
  # the one thing it can still be made to show is WHAT is missing -- so the sentence names the
  # evidence that was not retained. Green on the third word of the disjunction alone, with neither
  # `retain` nor `evidence` in it, so the rule cannot shrink to one word and stay green.
  sed -e 's/^incumbent: absent\..*$/incumbent: unknown. The job description text was never recorded, so the trigger cannot be read either way./' \
    "$r" >"$tmp/q4-incunknown.md"
  expect_green 'Q4 incumbent unknown, names what is missing' "$tmp/q4-incunknown.md"
  cases=$((cases + 1))

  # And red on the paperwork shape: a full sentence, well past 20 characters, that says the slot
  # could not be settled without ever saying what was not kept.
  sed -e 's/^incumbent: absent\..*$/incumbent: unknown. The slot could not be settled either way in this pass./' \
    "$r" >"$tmp/q4-incvague.md"
  expect_red 'Q4 incumbent unknown, nothing named' "$tmp/q4-incvague.md" \
    'FAIL: Q4 incumbent: unknown does not name what was not retained'
  cases=$((cases + 1))

  # --- fail closed -------------------------------------------------------------------------------
  # Four readings, each pinning its OWN message, `(missing)` and `(empty)` included: they are four
  # distinct defects and a run is sent to a different fix by each, so a shared prefix would let
  # "absent" and "empty" be rewritten into one message and still ship green.
  expect_red 'absent record' "$tmp/nope.md" "FAIL: no selection record to grade at $tmp/nope.md (missing)"
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty record' "$tmp/empty.md" "FAIL: no selection record to grade at $tmp/empty.md (empty)"
  cases=$((cases + 1))

  write_lines "$tmp/no-block.md" \
    'captured: 2026-09-02' \
    'pool: 14' \
    'scored: 4' \
    'selected: 2' \
    'axes: icp-fit substitution ai-claim reachability' \
    'scale: 1-5' \
    '' \
    '---'
  expect_red 'record with no ### block' "$tmp/no-block.md" 'FAIL: no ### block in'
  cases=$((cases + 1))

  write_lines "$tmp/no-header.md" \
    '# Candidate selection' \
    '' \
    '---' \
    '' \
    '### Acme' \
    '' \
    'axes: 5 4 5 4' \
    'total: 18' \
    'outcome: selected. Same buyer, and the nearest substitute in the pool.' \
    '' \
    '### Shell hold' \
    '' \
    'hold: none. Nothing was held.' \
    '' \
    '### Incumbent slot' \
    '' \
    'incumbent: filled. Hooli took the eighth slot on a score of 16 of 20.'
  expect_red 'record with no header key' "$tmp/no-header.md" 'FAIL: no rubric header key in'
  cases=$((cases + 1))

  # CHECKS_RUN DERIVED FROM EXECUTION rather than written down, proved on the one pair of runs where a
  # derived counter and a constant differ: the fail-closed path runs no check and must leave the
  # counter at 0, a full grade must leave it at 4, and both readings come from the same variable in
  # the same shell. A counter assigned once, or not reset between grades, fails one of the two.
  check_file "$tmp/nope.md"
  if [ "$CHECKS_RUN" -ne 0 ]; then
    printf 'SELFTEST FAIL: the fail-closed path ran %s checks, want 0\n' "$CHECKS_RUN" >&2
    return 1
  fi
  check_file "$r"
  if [ "$CHECKS_RUN" -ne 4 ]; then
    printf 'SELFTEST FAIL: a full grade ran %s checks, want 4\n' "$CHECKS_RUN" >&2
    return 1
  fi
  printf 'SELFTEST detail OK %-33s -> 0 on the fail-closed path, 4 on a full grade\n' \
    'CHECKS_RUN derived'
  cases=$((cases + 1))

  # --- child processes ---------------------------------------------------------------------------
  # P1: the whole script as a child, green, in --check mode with NO argument, so the documented
  # default record is the thing under test and is exercised by the run rather than by prose.
  proc="$tmp/proc-green"
  make_proc_root "$proc"
  cp "$r" "$proc/$DEFAULT_RECORD"
  expect_proc_green 'child, clean default record' "$proc" 'SCORE-CHECK-OK' '--check'
  cases=$((cases + 1))

  # The count in the OK line is asserted against `$CHECKS_RUN`, which the in-process `check_file "$r"`
  # immediately above this block left at the number of checks that ACTUALLY RAN on this same clean
  # record -- not against a literal 4. A printf that hard-coded 4 while two checks ran would pass a
  # literal assertion and fails this one.
  case "$PROC_OUT" in
    *"SCORE-CHECK-OK ($CHECKS_RUN checks, 0 findings in $DEFAULT_RECORD)"*) : ;;
    *) printf 'SELFTEST FAIL: OK line did not report %s checks on the record; got: %s\n' \
         "$CHECKS_RUN" "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-33s -> "%s"\n' 'OK line check count' "$PROC_OUT"
  cases=$((cases + 1))

  # P2: the same child on a RED default record. Exit non-zero, the finding on the stream, and an
  # explicit guard inside expect_proc_red that SCORE-CHECK-OK was NOT printed.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  cp "$tmp/q4-incnodigit.md" "$proc/$DEFAULT_RECORD"
  expect_proc_red 'child, red default record' "$proc" 'FAIL: Q4 incumbent: absent carries no score' \
    '--check'
  cases=$((cases + 1))

  # P3: the child with a path ARGUMENT naming a file that does not exist, which is both the argument
  # dispatch and the fail-closed path, proved in the process that actually exits.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child, absent record argument' "$proc" 'FAIL: no selection record to grade at' \
    '--check' 'output/review/nope.md'
  cases=$((cases + 1))

  # P4: BARE MODE as a child with no argument at all -- the default mode and the default record
  # together. The three counts in the header are asserted against numbers derived HERE, from the
  # fixture, by a different method than the script uses, so a header that printed a constant would
  # fail.
  proc="$tmp/proc-record"
  make_proc_root "$proc"
  cp "$r" "$proc/$DEFAULT_RECORD"
  es="$(awk -v s="### Shell hold" -v i="### Incumbent slot" \
    '/^### / { if ($0 != s && $0 != i) n++ } END { print n + 0 }' "$r")"
  esel="$(awk '/^outcome: selected\. / { n++ } END { print n + 0 }' "$r")"
  ecut="$(awk '/^outcome: cut\. / { n++ } END { print n + 0 }' "$r")"
  expect_proc_green 'child, bare record mode' "$proc" \
    "SCORE-CHECK ($DEFAULT_RECORD): $es scored, $esel selected, $ecut cut"
  cases=$((cases + 1))

  # The record must print the rubric, each candidate with its per-axis breakdown and total, and the
  # two proof lines -- which is what a reader opens it for.
  case "$PROC_OUT" in
    *'rubric: icp-fit substitution ai-claim reachability, scale 1-5'*) : ;;
    *) printf 'SELFTEST FAIL: the record did not print the rubric; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *'Vantor'*'3 3 2 2'*'total 10'*'[cut]'*) : ;;
    *) printf 'SELFTEST FAIL: the record did not print a per-axis breakdown; got: %s\n' \
         "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *'hold: excluded. Companies House'*'incumbent: absent. The best-scoring'*) : ;;
    *) printf 'SELFTEST FAIL: the record did not print both proof lines; got: %s\n' "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-33s -> rubric, breakdown, split and both proof lines printed\n' \
    'record shape'
  cases=$((cases + 1))

  # P5: BARE MODE AGAIN on a SECOND record whose three counts are all different numbers. P4's fixture
  # derives 4, 2 and 1, and a header printing those three constants passes it -- one fixture cannot
  # tell a derived count from a written one.
  proc="$tmp/proc-record2"
  make_proc_root "$proc"
  sed -e '/^### Meridian$/,/^outcome: held\./d' \
      -e 's/^outcome: selected\. Ships the same.*$/outcome: cut. Ships to the wrong buyer after all./' \
    "$r" >"$tmp/record2.md"
  cp "$tmp/record2.md" "$proc/$DEFAULT_RECORD"
  es="$(awk -v s="### Shell hold" -v i="### Incumbent slot" \
    '/^### / { if ($0 != s && $0 != i) n++ } END { print n + 0 }' "$tmp/record2.md")"
  esel="$(awk '/^outcome: selected\. / { n++ } END { print n + 0 }' "$tmp/record2.md")"
  ecut="$(awk '/^outcome: cut\. / { n++ } END { print n + 0 }' "$tmp/record2.md")"
  if [ "$es" = "4" ] || [ "$esel" = "2" ] || [ "$ecut" = "1" ]; then
    printf 'SELFTEST FAIL: the second record fixture derives %s scored, %s selected and %s cut, \
which does not differ from the first fixture in all three counts\n' "$es" "$esel" "$ecut" >&2
    return 1
  fi
  expect_proc_green 'child, second bare record' "$proc" \
    "SCORE-CHECK ($DEFAULT_RECORD): $es scored, $esel selected, $ecut cut"
  cases=$((cases + 1))

  # P6: BARE MODE on the Q3 fixture whose CUT candidate says the word `selected` mid-sentence. The
  # record has its own copy of opens(), it is the copy that decides which side of the split a
  # candidate lands on, and nothing else here reads it: degraded to a substring search it files
  # Vantor under selected:, prints [selected] in the breakdown and moves both counts in the header.
  proc="$tmp/proc-selword"
  make_proc_root "$proc"
  cp "$tmp/q3-selword.md" "$proc/$DEFAULT_RECORD"
  es="$(awk -v s="### Shell hold" -v i="### Incumbent slot" \
    '/^### / { if ($0 != s && $0 != i) n++ } END { print n + 0 }' "$tmp/q3-selword.md")"
  esel="$(awk '/^outcome: selected\. / { n++ } END { print n + 0 }' "$tmp/q3-selword.md")"
  ecut="$(awk '/^outcome: cut\. / { n++ } END { print n + 0 }' "$tmp/q3-selword.md")"
  expect_proc_green 'child, tag word in a cut sentence' "$proc" \
    "SCORE-CHECK ($DEFAULT_RECORD): $es scored, $esel selected, $ecut cut"
  cases=$((cases + 1))

  case "$PROC_OUT" in
    *'Vantor'*'3 3 2 2'*'total 10'*'[cut]'*) : ;;
    *) printf 'SELFTEST FAIL: the record did not read the cut sentence as cut; got: %s\n' \
         "$PROC_OUT" >&2
       return 1 ;;
  esac
  case "$PROC_OUT" in
    *'selected: Acme, Borealis'*'cut: Vantor'*) : ;;
    *) printf 'SELFTEST FAIL: the record filed Vantor on the wrong side of the split; got: %s\n' \
         "$PROC_OUT" >&2
       return 1 ;;
  esac
  printf 'SELFTEST detail OK %-33s -> [cut] in the breakdown and Vantor under cut:\n' \
    'record split on a tag word'
  cases=$((cases + 1))

  # P7 and P8: THE FAIL-CLOSED PATH OF BARE MODE, which is the DEFAULT invocation -- no `--check`, no
  # argument. `main_record()` carries its own two guards, reached by nothing above: the in-process
  # cases go through `check_file`, and the `--check` child cases go through `main_check`. Each pins
  # its own half, `(missing)` and `(empty)`, because they are two defects and a shared prefix would
  # let them be rewritten into one message and still ship green.
  proc="$tmp/proc-bare-missing"
  make_proc_root "$proc"
  expect_proc_red 'child, bare mode, no record' "$proc" \
    "FAIL: no selection record to grade at $DEFAULT_RECORD (missing)"
  cases=$((cases + 1))

  proc="$tmp/proc-bare-empty"
  make_proc_root "$proc"
  : >"$proc/$DEFAULT_RECORD"
  expect_proc_red 'child, bare mode, empty record' "$proc" \
    "FAIL: no selection record to grade at $DEFAULT_RECORD (empty)"
  cases=$((cases + 1))

  # THE COMMITTED ARTEFACTS, last, because a finding here is a report and not a repair. The run's
  # selection record must be green and the red fixture must red all four checks. Neither is stubbed:
  # grading this script against its own idea of a selection record would prove nothing about the file
  # a run actually writes. ABSENT, EACH IS A HARD FAILURE NAMED BY PATH, exactly as
  # `tools/gap-test.sh`, `tools/ai-smell.sh` and `tools/scan-layer.sh` treat their own committed
  # artefacts: a suite that skips the only two real files it reads and still prints OK is a green
  # this repository treats as a lie, and moving either file aside would otherwise exit 0.
  if [ ! -s "$ROOT/$DEFAULT_RECORD" ]; then
    printf 'SELFTEST FAIL: no committed selection record at %s\n' "$ROOT/$DEFAULT_RECORD" >&2
    return 1
  fi
  expect_green 'committed selection record' "$ROOT/$DEFAULT_RECORD"
  cases=$((cases + 1))

  fixture="$ROOT/tools/fixtures/unscored-selection.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no unscored-selection red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  check_file "$fixture"
  want=""
  for key in Q1 Q2 Q3 Q4; do
    case "$FAILS" in
      *"FAIL: $key "*) : ;;
      *) want="$want $key" ;;
    esac
  done
  if [ -n "$want" ]; then
    printf 'SELFTEST FAIL: tools/fixtures/unscored-selection.md did not go red on%s; got: %s\n' \
      "$want" "${FAILS:-<no findings>}" >&2
    return 1
  fi
  printf 'SELFTEST red OK   %-34s -> all four checks red\n' 'unscored-selection.md'
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  printf 'SELFTEST OK: %s cases, Q1 red on each of the %s pinned header keys missing, on a duplicated key, on a key that sits after the first ### block, on a key indented off column 0, on two and on six axis names -- the ends of the three-to-five range the run derives its own axis count inside, with the arity and ceiling rules proved OFF on both -- on the same axis named twice, on a scale that is not 1-5, on a count that is not an integer, on a negative count, on pool < scored, on scored < selected and on selected < 1, on a captured: value that is not YYYY-MM-DD in shape, and on a missing and on a doubled --- separator before the first block, Q2 red on each of its twenty-one sub-rules (no axes, two axes, no total, two total, no outcome, two outcome -- every one of them planted under the SECOND candidate block -- a total: line indented off column 0, three axis scores, a non-integer score, a score above and a score below the scale, a non-integer total, a two-number total, a tag outside the three, a tag word sitting mid-sentence, a tag opening the value inside a longer word, a tag with no sentence after it, a missing and a duplicated Shell hold block, a missing and a duplicated Incumbent slot block, a duplicate candidate name, and a record with no candidate block at all) and green on all %s pinned outcome tags read from an independent literal with a reverse membership check, Q3 red on a total that does not match its axes and on a rank order broken by MOVING a whole block, both under blocks that are not the first, on a total above the 20 a four-axis record allows, on a block count that disagrees with scored: and on a selected count that disagrees with selected:, green on a cut candidate whose sentence carries the word selected mid-sentence, a WHOLE THREE-AXIS record green end to end with Q2 red on a block scoring a fourth integer, the sum rule silent on that same block and the ceiling red at 15 on a total of 18, which the literal 20 this rule used to carry would have passed, Q4 red on a missing and a duplicated hold: line, on a hold tag outside the three, mid-sentence, inside a longer word and with no sentence, on a hold other than none naming no registry, on a missing and a duplicated incumbent: line, on an incumbent tag outside the five, mid-sentence, inside a longer word and with no sentence, on absent with no score, on blocked naming no fetch failure, on not-opened saying why in under 20 characters and on unknown naming nothing that was not retained, green on all %s pinned hold states and all %s pinned incumbent states, on both lowercase halves of the registry and fetch rules and on an unknown that names what was never recorded, four fail-closed readings each pinning its own message (record missing, record empty, no ### block, no header key), CHECKS_RUN derived from execution at 0 on the fail-closed path and 4 on a full grade, and 8 child-process cases (clean default record green with the token and a count asserted against the CHECKS_RUN the same record left in this shell, a red default record exiting 1 with the token absent, an absent record argument exiting 1, two bare record modes whose scored, selected and cut counts are derived from two fixtures holding different numbers, a third bare mode filing a cut candidate whose sentence carries the word selected under cut: and not selected:, and bare mode with no argument exiting 1 on a missing and on an empty default record, each pinning its own half of the message)\n' \
    "$cases" "$nkey" "$ntag" "$nhold" "$ninc"
}

# --- main -----------------------------------------------------------------------------------------
main_check() {
  local rec
  cd "$ROOT"
  rec="${1:-$DEFAULT_RECORD}"
  check_file "$rec"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  printf 'SCORE-CHECK-OK (%s checks, 0 findings in %s)\n' "$CHECKS_RUN" "$rec"
}

# main_record prints the scoring record and grades nothing. It still fails closed on a record it
# cannot read, so bare mode cannot report a record of nothing.
main_record() {
  local rec
  cd "$ROOT"
  rec="${1:-$DEFAULT_RECORD}"
  if [ ! -e "$rec" ]; then
    printf 'FAIL: no selection record to grade at %s (missing)\n' "$rec" >&2
    exit 1
  fi
  if [ ! -s "$rec" ]; then
    printf 'FAIL: no selection record to grade at %s (empty)\n' "$rec" >&2
    exit 1
  fi
  record_lines "$rec"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  elif [ "${1:-}" = "--check" ]; then
    shift
    main_check "${1:-}"
  else
    main_record "${1:-}"
  fi
fi
