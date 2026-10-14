#!/usr/bin/env bash
# The quality-bar lint. It grades one markdown brief against `quality-bar/04-banned-patterns.tsv`,
# adds the two checks a regex cannot express, collects every finding, and fails closed.
#
# WHY IT EXISTS. `tools/ai-smell.sh` closed the machine-authorship half of the voice standard: six
# rules for the tells of LLM prose. It never touched the other half, the one the Northwind run failed on
# -- prose whose subject is the run rather than the market. `21-voice-audit.md` counted six such
# sentences on the delivered page against the exemplar's zero, and four of the six had been READ by
# the register pass, which cleared two and downgraded one. A pass that reads a draft after the words
# exist cannot stop a run writing them, and a judgement that can be overruled by a second judgement
# is not a gate. These rules are.
#
# THREE KINDS OF FINDING, and the exit code is only one of them.
#
#   FAIL   a blocking rule. Non-zero exit. Every `route=block` row in the TSV, plus the two code
#          checks below.
#   ROUTE  a `route=truth` row. The sentence is not wrong, it needs a ledger row behind it, so the
#          finding goes to the truth critic and the exit code is UNCHANGED. A quantifier is not a
#          defect; an unsourced quantifier is, and only the ledger knows which one this is.
#   SIGNAL the rhythm signals, ADVISORY by construction. `21-quality-bar-system.md` §6 is explicit:
#          a rhythm quota pushes the author to bolt short sentences onto paragraphs, which is
#          itself the tic being hunted (H8). The voice critic reads these and decides, quoting the
#          sentence. They never move the exit code.
#
# MEASURED ON THE EXEMPLAR, and the number is not the one the design predicted. `21-quality-bar-
# system.md` §6 says the four rhythm signals are "calibrated on the exemplar (0 violations)".
# Measured 2026-09-18 by this script: R1, "each prose paragraph has at least one sentence of six
# words or fewer", fires 5 times on `build/briefing.md`, on paragraphs whose shortest sentences run
# 9, 9, 9, 8 and 12 words, and R2 once. `21-voice-audit.md` §1 measured the same five by hand and
# called them the exemplar's practice. The design's claim is wrong, the signal is kept
# anyway, and the reason it can be kept is exactly that it is advisory: it is a profile the critic
# compares two briefs on, not a threshold either brief passes. `quality-bar/decisions.md` D-003
# books the correction. A BLOCKING rule measured red on the exemplar would have been dropped
# instead, which is what happened to three of the design's own rows -- see D-001 and D-002.
#
# WHAT IT DELIBERATELY DOES NOT CHECK.
#
#   - Em dashes, straight quotes and the ellipsis. `21-quality-bar-system.md` §6 lists all three as
#     rows. They are already GATE 1 in `build/build.py`, and `tools/ai-smell.sh` refuses a second
#     copy by name: "a second copy is a second thing to drift". The straight-quote row also cannot
#     be run here at all, because grading the AUTHOR'S voice means blanking every quoted span out
#     of the copy the rules read, and that strip destroys the evidence the row needs. D-002.
#   - The six `tools/ai-smell.sh` rules. A1 to A6 already run on every build and are wired into
#     `tools/ci-gates.sh`. The TSV carries `signpost`, `llm_vocab`, `adverb_opener`, `hedged_super`,
#     `bold_colon` and `not_x_but_y` because the quality-bar folder is the single source the AUTHOR
#     writes from and a rule the author cannot see in the card is a rule the author cannot follow.
#     The two scripts overlapping on six patterns is deliberate duplication of a CHECK, not of a
#     MEANING: ai-smell grades a draft, this grades the same draft against the reader's bar.
#   - Anything needing the claims ledger. `tools/claims-check.py` owns every number.
#
# THE BLIND SPOT, named rather than fixed: `grep` reads a line at a time, so a pattern that spans a
# markdown line wrap is invisible to every row. The paragraph and sentence work below joins wrapped
# lines first and does not share it.
#
# `grep` is wrapped to `ugrep` on this machine, where a pattern starting with `--` parses as an
# option, so every pattern is passed after `-e`. The rule table is a FILE and not a string in this
# script: `quality-bar/` is the single source the author, the critics and this lint all read, and a
# second copy of the patterns here would be a second thing to drift.
#
# PRECONDITION: the target file, `quality-bar/04-banned-patterns.tsv`, perl and python3. No network,
# no MKT1 call, no env var, no build artefact, no run directory.
#
# PAGE MODE, `voice-lint.sh --page FILE` (W2-rulings.md G27). A web page's text
# (`build/web.py --text`, with or without `--authored`) has no `##` sections, and a run stopped
# writing `headings.json` when the page replaced the PDF. So page mode skips the slot resolver and
# its three sections: the corpus denylist and R4 measure nothing. Every TSV row and code check stays
# live. The page's headings are `brief.json` fields that `tools/brief-check.py` grades. Page mode
# names its FILE explicitly and never falls back to the exemplar, whose `build/headings.json` is a
# PDF record.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# THE THREE SECTIONS R4 AND THE CORPUS KNOW ABOUT, resolved from the run own allocation record by
# the one resolver, never named here. See the block comment at PYCHECKS for what the literal cost:
# a rename took R4 silent rather than red. A record that cannot be read, or that carries no such
# slot, is a fail-closed exit and never a grade.
PAGE_MODE=0
if [ "${BASH_SOURCE[0]}" = "${0}" ] && [ "${1:-}" = "--page" ]; then
  PAGE_MODE=1
fi
if [ "$PAGE_MODE" -eq 0 ]; then
  if [ ! -f "$ROOT/tools/slot-heading.sh" ]; then
    printf 'FAIL: no slot resolver at %s/tools/slot-heading.sh\n' "$ROOT" >&2
    exit 2
  fi
  # shellcheck source=tools/slot-heading.sh
  . "$ROOT/tools/slot-heading.sh"
fi

resolve_section() {
  local slot="$1" out rc=0
  out="$(slot_heading "$slot")" || rc=$?
  if [ "$rc" -eq 1 ]; then
    printf 'FAIL: the allocation record at %s carries no %s slot\n' "$(slot_heading_record)" "$slot" >&2
    exit 2
  fi
  if [ "$rc" -ne 0 ]; then
    printf 'FAIL: no readable allocation record at %s; this lint cannot know which sections to grade\n' \
      "$(slot_heading_record)" >&2
    exit 2
  fi
  printf '%s\n' "$out"
}
BUDGET_SECTION=""
GRADED_SECTION=""
SOURCES_SECTION=""
if [ "$PAGE_MODE" -eq 0 ]; then
  BUDGET_SECTION="$(resolve_section quick-take)"
  GRADED_SECTION="$(resolve_section coverage-notes)"
  SOURCES_SECTION="$(resolve_section sources)"
fi
DEFAULT_TARGET="build/briefing.md"
RULES_TSV="quality-bar/04-banned-patterns.tsv"

# Newline-delimited strings, not arrays: /bin/bash on macOS is 3.2, where expanding an empty array
# under `set -u` is itself an error.
FAILS=""
ROUTES=""
SIGNALS=""
NRULES=0

add_fail()   { FAILS="${FAILS}$1"$'\n'; }
add_route()  { ROUTES="${ROUTES}$1"$'\n'; }
add_signal() { SIGNALS="${SIGNALS}$1"$'\n'; }

# --- preprocessing --------------------------------------------------------------------------------
# THE SINGLE PLACE THE SCOPE EXCLUSIONS LIVE. `21-quality-bar-system.md` §6 scopes every rule to
# prose plus table cells, excluding headings, link text and quoted third-party copy. That is six
# strips, in this order, and no rule below carries its own escape hatch:
#
#   1. A heading line is blanked whole. A heading is graded by the LABELS critic and by
#      `tools/scan-layer.sh`, on whether it covers its rows; it is not prose.
#   2. HTML tags. This is also what makes a straight quote inside `class="rec"` invisible, which is
#      why the design's `(outside HTML attributes)` parenthesis needs no rule-level handling.
#   3. Markdown links, label and target together. Link text is out of scope by §6, and a slug is
#      not prose: `landscape-of-spend` inside a link is not an author writing "landscape of".
#   4. Bare URLs, for the same reason.
#   5. Curly-quoted spans, then 6. straight-quoted spans. This lint grades the AUTHOR'S voice and
#      never a quotation, the same exclusion `tools/ai-smell.sh` generalises from A5 to every rule.
#      MEASURED on the exemplar: `build/briefing.md:14` carries Round's own copy, "Round only moves
#      money based on thresholds you define. Nothing happens without your rules. Ever." Without the
#      strip a competitor's marketing sentence is graded as the author's.
#
# Matched text is BLANKED IN PLACE and no line is ever deleted, so `grep -n` on the copy reports the
# real line number in the source file.
#
# perl and not sed: the curly pair is multi-byte, and a negated character class over UTF-8 bytes in
# BSD sed is not the same thing as one over characters. `-CSD` decodes stdin and encodes stdout as
# UTF-8, so `[^\x{201D}]` means one character. `-p` is per-line, which also bounds a runaway
# unmatched quote to its own line.
preprocess() {
  local src="$1" dst="$2"
  perl -CSD -pe '
    if (m{^\s{0,3}\#{1,6}\s}) { $_ = "\n"; }
    else {
      s{<[^>]*>}{}g;
      s{\[[^\]]*\]\([^)]*\)}{}g;
      s{https?://\S+}{}g;
      s{\x{201C}[^\x{201D}]*\x{201D}}{}g;
      s{"[^"]*"}{}g;
    }
  ' "$src" >"$dst"
}

# prose_only blanks every table row out of an already-preprocessed copy, keeping line numbers. It is
# what `scope=prose` reads. One rule uses it today, `semicolon`: `20-voice-standard.md` counts
# semicolons IN PROSE, exemplar 0 against Initech 16, and the exemplar's two semicolons both sit in
# table cells. Grading cells on that rule would red the exemplar, so it does not.
prose_only() {
  perl -pe 's{^\s*\|.*$}{}' "$1" >"$2"
}

# --- the code checks ------------------------------------------------------------------------------
# Two things no regex in the TSV can say, so they are written as code, which is
# `21-quality-bar-system.md` §11's "code over words" applied to the rule table itself.
#
#   dup_row_date  BLOCKING. One date printed twice inside one table row. `21-voice-audit.md` M7:
#                 "the only row in either brief that does this. The exemplar never repeats a date
#                 across the columns of a row." Measured 2026-09-18: 0 such rows in
#                 build/briefing.md, 1 in the fixture.
#   R1..R4        ADVISORY rhythm signals, §6.
#
# The program is read into a variable and passed with `-c`, and NOT written as
# `OUT="$( python3 - <<'PY' )"`: the closing `)` would end the command substitution on that line and
# the heredoc body would never reach python. That failure is booked in `tools/exemplar-cohort.sh`,
# whose idiom this copies. `read -d ''` stops at a NUL that never comes and returns 1 at EOF, hence
# the `|| true`.
PYCHECKS=""
read -r -d '' PYCHECKS <<'PY' || true
import os, re, sys

# THE THREE SECTIONS THIS BLOCK KNOWS ABOUT ARRIVE FROM THE ENVIRONMENT, resolved by
# `tools/slot-heading.sh` from the run own allocation record. D3 made a section a slot id plus the
# heading a run writes over it, so a literal here grades a section that may not be on the page:
# `S5T-verify-2.md` measured R4 going SILENT under a legitimate rename -- the ratio simply stopped
# being measured, with no finding and exit 0, which is worse than a red. The shell resolves and
# fails closed; this block trusts what it is handed.
SECTION_BUDGET = os.environ["VOICE_BUDGET_SECTION"]
SECTION_GRADED = os.environ["VOICE_GRADED_SECTION"]
# Page mode hands all three over empty: no section is denied, and R4 is not measured.
NOT_PROSE_SECTIONS = tuple(s.lower() for s in (os.environ["VOICE_SOURCES_SECTION"],) if s)

path = sys.argv[1]
src = open(path, encoding="utf-8").read().split("\n")

# --- dup_row_date ---------------------------------------------------------------------------------
# Read from the RAW line, not the preprocessed copy: a date inside a quoted span is still a date
# printed twice in one row, and the row is the unit the reader sees.
DATE = re.compile(
    r"\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{2,4}\b"
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r" \d{1,2}, \d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)
for n, line in enumerate(src, 1):
    if not line.lstrip().startswith("|"):
        continue
    found = DATE.findall(line) if False else [m.group(0) for m in DATE.finditer(line)]
    seen, dup = set(), []
    for d in found:
        if d in seen and d not in dup:
            dup.append(d)
        seen.add(d)
    for d in dup:
        print("FAIL\tdup_row_date\tone date printed twice in one row\t%d\t%s" % (n, d))

# --- the prose corpus -----------------------------------------------------------------------------
# A prose paragraph is a run of consecutive lines that are not a heading, not a table row, not a
# list item and not blank. Wrapped lines are joined first, which is what keeps this half free of the
# line-at-a-time blind spot the regex rows carry. Markup is stripped but QUOTATIONS ARE KEPT: the
# exemplar's shortest sentence is `Ever.”`, the tail of Round's own copy, and a corpus that drops it
# reports a rhythm the page does not have.
#
# ONE BLOCK IS OUTSIDE THE CORPUS, and it is measured rather than assumed. The `sources` slot is a
# `<br>`-joined list of link labels: graded as prose it reported two paragraphs whose shortest
# sentence ran 21 and 33 words, which are not sentences at all, they are `roundtreasury.com AI
# Treasury Manager FSCS coverage funding announcement …` read as one. `21-voice-audit.md` §1 defines
# the corpus as an ALLOWLIST of five blocks; this is the same corpus written as a denylist, so a
# menu section added later is graded by default rather than silently ungraded. The masthead is in
# the corpus and measured green: its three lines are 3, 3 and a 3-plus-6 pair.
SKIP = (
    re.compile(r"^\s{0,3}#{1,6}\s"),
    re.compile(r"^\s*\|"),
    re.compile(r"^\s*(?:\d+\.|[-*+])\s"),
)
def strip_markup(t):
    t = re.sub(r"<[^>]*>", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.replace("**", "").replace("*", "")
    t = re.sub(r"→\s*Next step:\s*", "", t)
    return t.strip()

paras, cur, start = [], [], 0
in_corpus = True
for n, line in enumerate(src, 1):
    if re.match(r"^\s{0,3}##\s", line):
        head = line.strip().lstrip("# ").strip().lower()
        in_corpus = head not in NOT_PROSE_SECTIONS
    if not in_corpus or any(p.match(line) for p in SKIP) or not line.strip():
        if cur:
            paras.append((start, " ".join(cur)))
            cur = []
        continue
    t = strip_markup(line)
    if not cur:
        start = n
    cur.append(t)
if cur:
    paras.append((start, " ".join(cur)))
paras = [(n, p) for n, p in paras if p.strip()]

def sentences(p):
    out = []
    for s in re.split(r"(?<=[.!?”])\s+", p):
        w = [t for t in re.split(r"\s+", s) if re.search(r"[A-Za-z0-9]", t)]
        if w:
            out.append((len(w), s.strip()))
    return out

allsent = []
for n, p in paras:
    ss = sentences(p)
    allsent += ss
    if not ss:
        continue
    shortest = min(x[0] for x in ss)
    # R1. The floor `21-quality-bar-system.md` §6 sets. Advisory; see the header for the exemplar
    # baseline, which is 7 of 16 paragraphs over this line.
    if shortest > 6:
        print("SIGNAL\tR1\tno sentence of 6 words or fewer (shortest %d)\t%d\t%s"
              % (shortest, n, p[:60]))
    # R2. Three consecutive sentences within a 3-word spread: the flat run that reads as machine
    # cadence. `21-voice-audit.md` M3 measures the Northwind draft at twelve straight sentences none
    # shorter than eleven words.
    lens = [x[0] for x in ss]
    for j in range(len(lens) - 2):
        w = lens[j:j + 3]
        if max(w) - min(w) <= 3:
            print("SIGNAL\tR2\tthree consecutive sentences within 3 words (%s)\t%d\t%s"
                  % (",".join(str(x) for x in w), n, p[:60]))
            break

# R3. At least one prose sentence in five runs to 10 words or fewer.
if allsent:
    short = sum(1 for n, _ in allsent if n <= 10)
    if short * 5 < len(allsent):
        print("SIGNAL\tR3\tonly %d of %d prose sentences are 10 words or fewer\t0\t"
              % (short, len(allsent)))

# R4. The graded section prose against the budget section prose. The exemplar runs 56%; the Northwind draft ran 75%,
# which is the reallocation `21-voice-audit.md` §1 names: the brief did not get longer, it moved
# words from what the reader came for to what the run wanted to explain.
def section_words(name):
    total, inside = 0, False
    for line in src:
        if re.match(r"^\s{0,3}##\s", line):
            inside = line.strip().lower().lstrip("# ").startswith(name.lower())
            continue
        if not inside or any(p.match(line) for p in SKIP[1:]) or not line.strip():
            continue
        total += len([t for t in re.split(r"\s+", strip_markup(line)) if re.search(r"[A-Za-z0-9]", t)])
    return total

qt, cn = (section_words(SECTION_BUDGET), section_words(SECTION_GRADED)) if SECTION_BUDGET and SECTION_GRADED else (0, 0)
if qt and cn and cn * 100 > qt * 60:
    print("SIGNAL\tR4\t%s prose is %d%% of %s (exemplar 56%%)\t0\t"
          % (SECTION_GRADED, round(cn * 100.0 / qt), SECTION_BUDGET))
PY

# --- the check ------------------------------------------------------------------------------------
# check_file populates FAILS, ROUTES and SIGNALS for one target and ALWAYS returns 0; the caller
# decides. Same contract as `check_file` in `tools/ai-smell.sh`, and it is what lets the selftest run
# every case in this shell without `set -e` ending the run at the first red.
check_file() {
  local f="$1" tsv pp ppp id pat scope cs thr route rest flags src hits n reported oldifs h ln text
  local line kind rid label lno detail

  FAILS=""; ROUTES=""; SIGNALS=""; NRULES=0
  tsv="$ROOT/$RULES_TSV"

  # The rule table missing is a FAILURE, never a vacuous pass. Zero rules reporting zero findings is
  # precisely the shape of green this repository treats as a lie.
  if [ ! -s "$tsv" ]; then
    add_fail "FAIL: no rule table at $RULES_TSV (missing or empty)"
    return 0
  fi
  if [ ! -s "$f" ]; then
    add_fail "FAIL: no brief to grade at $f (missing or empty)"
    return 0
  fi

  pp="$(mktemp "${TMPDIR:-/tmp}/voice-lint-pp.XXXXXX")"
  ppp="$(mktemp "${TMPDIR:-/tmp}/voice-lint-pr.XXXXXX")"
  preprocess "$f" "$pp"
  prose_only "$pp" "$ppp"

  # `IFS=<tab> read` over the table, fed by a here-string: the loop body must run IN THIS SHELL or
  # every add_fail is discarded in a subshell. `rest` swallows why/source/hits/last_hit, so a row
  # that ends early -- no `last_hit` yet -- still parses, and adding a column to the TSV does not
  # touch this loop.
  # `IFS=$'\037'` over a tab-to-US translation, and NOT `IFS=$'\t'`. TAB IS IFS WHITESPACE, so a
  # run of tabs collapses into one delimiter and a row with an EMPTY field silently shifts every
  # column after it left -- a `hits` column not yet filled would arrive as the pattern's `route`.
  # The unit separator is not IFS whitespace, so empty fields survive.
  while IFS=$'\037' read -r id pat scope cs thr route rest; do
    case "$id" in ''|'#'*) continue ;; id) continue ;; esac
    [ -n "$pat" ] || { add_fail "FAIL: rule $id in $RULES_TSV has no pattern"; continue; }
    NRULES=$((NRULES + 1))

    if [ "$scope" = "prose" ]; then src="$ppp"; else src="$pp"; fi
    if [ "$cs" = "s" ]; then flags="-noE"; else flags="-noiE"; fi

    hits="$(grep $flags -e "$pat" "$src" || true)"

    # `conditional` alone carries a second condition the TSV cannot hold: a comparative is only a
    # finding when no number stands behind it. grep reads a line at a time, so the design's "no
    # digit within 12 tokens" window is APPROXIMATED BY THE LINE, and the approximation is stated
    # rather than hidden. It routes to truth, so the approximation costs a critic one read and never
    # an exit code.
    if [ "$id" = "conditional" ] && [ -n "$hits" ]; then
      local kept="" hh lnum
      oldifs="$IFS"; set -f; IFS=$'\n'
      for hh in $hits; do
        lnum="${hh%%:*}"
        if ! sed -n "${lnum}p" "$src" | grep -q -e '[0-9]'; then kept="${kept}${hh}"$'\n'; fi
      done
      IFS="$oldifs"; set +f
      hits="$(printf '%s' "$kept")"
    fi

    [ -n "$hits" ] || continue
    n="$(printf '%s\n' "$hits" | grep -c -e ':' || true)"
    # Under threshold is not a finding. For `not_x_but_y` and `semicolon` that is the cap doing its
    # job: the first occurrence is the allowance and is passed over in silence.
    [ "$n" -ge "$thr" ] || continue
    reported="$(printf '%s\n' "$hits" | tail -n +"$thr")"

    # Split on newlines only, with globbing OFF: `bold_colon` matches text containing `**`, and an
    # unguarded word split would let the shell expand it against the working directory.
    oldifs="$IFS"; set -f; IFS=$'\n'
    for h in $reported; do
      # ONE strip, not two. `grep -no` prints `LINE:MATCH`, so a second `${text#*:}` is silent on a
      # match with no colon in it and eats the whole finding on one that has: `bold_colon` matches
      # `**Key point**:` and reported an empty quote, which is a finding a critic cannot cite.
      ln="${h%%:*}"; text="${h#*:}"
      if [ "$route" = "truth" ]; then
        add_route "ROUTE: $id needs a ledger row at $f:$ln: $text"
      else
        add_fail "FAIL: $id at $f:$ln: $text"
      fi
    done
    IFS="$oldifs"; set +f
  done <<<"$(tr '\t' '\037' < "$tsv")"

  # The two code checks. Output is `kind<TAB>id<TAB>detail<TAB>line<TAB>text`, parsed here so the
  # python block owns the measurement and this shell owns the reporting format.
  oldifs="$IFS"; set -f; IFS=$'\n'
  for line in $(VOICE_BUDGET_SECTION="$BUDGET_SECTION" VOICE_GRADED_SECTION="$GRADED_SECTION" \
                VOICE_SOURCES_SECTION="$SOURCES_SECTION" python3 -c "$PYCHECKS" "$f"); do
    kind="${line%%$'\t'*}"; rest="${line#*$'\t'}"
    rid="${rest%%$'\t'*}"; rest="${rest#*$'\t'}"
    detail="${rest%%$'\t'*}"; rest="${rest#*$'\t'}"
    lno="${rest%%$'\t'*}"; text="${rest#*$'\t'}"
    if [ "$kind" = "FAIL" ]; then
      add_fail "FAIL: $rid $detail at $f:$lno: $text"
      NRULES=$((NRULES + 1))
    else
      if [ "$lno" = "0" ]; then
        add_signal "SIGNAL: $rid $detail in $f"
      else
        add_signal "SIGNAL: $rid $detail at $f:$lno: $text"
      fi
    fi
  done
  IFS="$oldifs"; set +f

  rm -f "$pp" "$ppp"
  return 0
}

# --- selftest -------------------------------------------------------------------------------------
# Proves every TSV row goes red on its own minimal fixture, proves both capped rows in both
# directions, proves each preprocessing strip by removing the quotes or the link and watching the
# same text go red, proves the two code checks in both directions, proves the eight finding IDs the
# S2 Done list names on `quality-bar/fixtures/northwind-v1.md`, and proves the exemplar green. A check
# that has never gone red is an untested assertion.

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
    *"$want"*) printf 'SELFTEST red OK   %-30s -> %s' "$label" "$FAILS" ;;
    *) printf 'SELFTEST FAIL: %s did not go red; got: %s\n' "$label" "${FAILS:-<no findings>}" >&2
       return 1 ;;
  esac
}

expect_route() {
  local label="$1" f="$2" want="$3"
  check_file "$f"
  if [ -n "$FAILS" ]; then
    printf 'SELFTEST FAIL: %s produced a BLOCKING finding, want a route; got: %s\n' \
      "$label" "$FAILS" >&2
    return 1
  fi
  case "$ROUTES" in
    *"$want"*) printf 'SELFTEST route OK %-30s -> %s' "$label" "$ROUTES" ;;
    *) printf 'SELFTEST FAIL: %s did not route; got: %s\n' "$label" "${ROUTES:-<none>}" >&2
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
  printf 'SELFTEST green OK %-30s -> no blocking findings\n' "$label"
}

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main()`, its `cd "$ROOT"`, the default
# target, the argument dispatch, the VOICE-LINT-OK line and the non-zero exit are exercised by
# nothing. That gap is load-bearing and not hypothetical: inside `OUT="$( (f) 2>&1 )"` bash suspends
# `set -e`, so an in-process case cannot see an abort at all. The cases below copy this script and
# the rule table into a fixture root and run it as a CHILD with its own fully armed
# `set -euo pipefail`, which is the invocation a run actually makes. The idiom is
# `tools/ai-smell.sh:249-262`.
PROC_RC=0
PROC_OUT=""

make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/build" "$root/quality-bar"
  cp "${BASH_SOURCE[0]}" "$root/tools/voice-lint.sh"
  cp "$ROOT/$RULES_TSV" "$root/$RULES_TSV"
  # The resolver and an allocation record travel with the script: without them a child exits 2
  # before it grades anything, which is the fail-closed direction and is asserted below.
  cp "$ROOT/tools/slot-heading.sh" "$root/tools/slot-heading.sh"
  write_lines "$root/build/headings.json" \
    "{ \"sections\": [ { \"slot\": \"quick-take\", \"heading\": \"$BUDGET_SECTION\" },"  \
    "                  { \"slot\": \"coverage-notes\", \"heading\": \"$GRADED_SECTION\" }," \
    "                  { \"slot\": \"sources\", \"heading\": \"$SOURCES_SECTION\" } ] }"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/voice-lint.sh" "$@" 2>&1 )" || PROC_RC=$?
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
    *"$want"*) printf 'SELFTEST proc OK  %-30s -> exit 0\n' "$label" ;;
    *) printf 'SELFTEST FAIL: %s was green but did not print %s; got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# expect_proc_red asserts the exit code AND the message AND the absence of the success token. A
# script that printed VOICE-LINT-OK and then exited 1 anyway is the exact defect a sibling gate
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
    *VOICE-LINT-OK*) printf 'SELFTEST FAIL: a red child run printed VOICE-LINT-OK: %s\n' \
                       "$PROC_OUT" >&2
                     return 1 ;;
  esac
  printf 'SELFTEST proc red %-30s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

# expect_signal grades the ADVISORY stream, and asserts the exit-code contract at the same time: a
# rhythm signal that moved FAILS would make the design's "advisory" word a lie.
expect_signal() {
  local label="$1" f="$2" want="$3"
  check_file "$f"
  case "$SIGNALS" in
    *"$want"*) printf 'SELFTEST signal   %-30s -> %s' "$label" "$SIGNALS" ;;
    *) printf 'SELFTEST FAIL: %s produced no such signal; got: %s\n' \
         "$label" "${SIGNALS:-<none>}" >&2
       return 1 ;;
  esac
}

selftest() {
  local tmp fixture cases=0 want id missing

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/voice-lint-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # A clean draft first. Every red fixture below is this draft plus one tell, so a red case proves
  # the tell and not the scaffolding.
  write_lines "$tmp/clean.md" \
    '# Competitor Intel Brief' \
    '' \
    'The vendor ships payroll to 40 customers in Iberia. Two banks went live.' \
    '' \
    '**The seat count moved in May.** It moved again in June. Nobody said why.'
  expect_green 'clean draft' "$tmp/clean.md"
  cases=$((cases + 1))

  # --- one minimal fixture per blocking row -------------------------------------------------------
  write_lines "$tmp/r-process.md" 'No heat pump on its integrations page or on 22 pages fetched.'
  expect_red 'process_subject' "$tmp/r-process.md" 'FAIL: process_subject'
  cases=$((cases + 1))

  # The bound is legal and the verb is not, which is the whole of S1: the register pass cleared the
  # sentence because it read the two as one thing. The rewrite keeps 22 and must be green.
  write_lines "$tmp/r-process-ok.md" \
    'No heat pump on its integrations page, or on 22 other pages of ev.energy.'
  expect_green 'process_subject, bound kept' "$tmp/r-process-ok.md"
  cases=$((cases + 1))

  write_lines "$tmp/r-count.md" \
    'The site is thin. Sixteen pages and twenty-eight posts on northwind.example never say so.'
  expect_red 'count_subject' "$tmp/r-count.md" 'FAIL: count_subject'
  cases=$((cases + 1))

  # The exemplar's legal move: the same count in a prepositional phrase under a sentence about the
  # client. A rule that cannot tell these two apart is a rule that reds the exemplar.
  write_lines "$tmp/r-count-ok.md" \
    'Round states a threshold rule once, on 1 of 13 pages on roundtreasury.com.'
  expect_green 'count_subject, prepositional' "$tmp/r-count-ok.md"
  cases=$((cases + 1))

  write_lines "$tmp/r-passive.md" \
    'Revenue estimates conflict by a factor of two, so no revenue figure is given for it.'
  expect_red 'doc_passive' "$tmp/r-passive.md" 'FAIL: doc_passive'
  cases=$((cases + 1))

  write_lines "$tmp/r-passive-ok.md" \
    'Revenue estimates conflict by a factor of two, so it carries no revenue figure.'
  expect_green 'doc_passive, rewritten' "$tmp/r-passive-ok.md"
  cases=$((cases + 1))

  write_lines "$tmp/r-tool.md" 'Every URL in this table appears in a retained snapshot.'
  expect_red 'tool_name' "$tmp/r-tool.md" 'FAIL: tool_name'
  cases=$((cases + 1))

  write_lines "$tmp/r-tag.md" 'The figure is 300k assets [COMPANY CLAIM] and undated.'
  expect_red 'verif_tag' "$tmp/r-tag.md" 'FAIL: verif_tag'
  cases=$((cases + 1))

  write_lines "$tmp/r-reldate.md" 'The relaunch landed eleven days ago in the same market.'
  expect_red 'relative_date' "$tmp/r-reldate.md" 'FAIL: relative_date'
  cases=$((cases + 1))

  write_lines "$tmp/r-signpost.md" 'It is worth noting that the seat count moved in May.'
  expect_red 'signpost' "$tmp/r-signpost.md" 'FAIL: signpost'
  cases=$((cases + 1))

  write_lines "$tmp/r-llm.md" 'The vendor ships a robust platform for the realm of spend.'
  expect_red 'llm_vocab' "$tmp/r-llm.md" 'FAIL: llm_vocab'
  cases=$((cases + 1))

  write_lines "$tmp/r-adverb.md" 'Crucially, the vendor ships payroll.'
  expect_red 'adverb_opener' "$tmp/r-adverb.md" 'FAIL: adverb_opener'
  cases=$((cases + 1))

  # The same adverb lower-cased mid-sentence stays green under adverb_opener, but `notably` is a
  # `signpost` word at any case, so the case that proves the SHAPE rule must use an adverb signpost
  # does not carry.
  write_lines "$tmp/r-adverb-lower.md" 'The seat count moved, ultimately, in May.'
  expect_green 'adverb_opener, mid-sentence' "$tmp/r-adverb-lower.md"
  cases=$((cases + 1))

  write_lines "$tmp/r-super.md" 'It is one of the largest vendors in Iberia.'
  expect_red 'hedged_super' "$tmp/r-super.md" 'FAIL: hedged_super'
  cases=$((cases + 1))

  write_lines "$tmp/r-boldcolon.md" '**Key point**: the vendor ships payroll.'
  expect_red 'bold_colon' "$tmp/r-boldcolon.md" 'FAIL: bold_colon'
  cases=$((cases + 1))

  # The house claim-header, a bold full sentence with a terminal period, is mandatory here and must
  # stay green, or the lint is unusable on the exemplar.
  write_lines "$tmp/r-header-ok.md" '**The seat count moved in May.** Two banks went live.'
  expect_green 'bold claim-header allowed' "$tmp/r-header-ok.md"
  cases=$((cases + 1))

  # not_x_but_y in both directions, because the cap is the rule. One is the allowance.
  write_lines "$tmp/r-antithesis-one.md" 'It is not a rail but a road.'
  expect_green 'not_x_but_y, one occurrence' "$tmp/r-antithesis-one.md"
  cases=$((cases + 1))

  write_lines "$tmp/r-antithesis-two.md" \
    'It is not a rail but a road.' \
    'The buyer is not a controller but a treasurer.'
  expect_red 'not_x_but_y, two occurrences' "$tmp/r-antithesis-two.md" 'FAIL: not_x_but_y'
  cases=$((cases + 1))

  # semicolon in both directions, and only in prose. A table row carrying one is the exemplar's own
  # practice, twice.
  write_lines "$tmp/r-semi-one.md" 'The vendor ships payroll; the buyer signs for it.'
  expect_green 'semicolon, one in prose' "$tmp/r-semi-one.md"
  cases=$((cases + 1))

  write_lines "$tmp/r-semi-two.md" \
    'The vendor ships payroll; the buyer signs for it.' \
    'The rail is owned; the float is rented.'
  expect_red 'semicolon, two in prose' "$tmp/r-semi-two.md" 'FAIL: semicolon'
  cases=$((cases + 1))

  write_lines "$tmp/r-semi-cell.md" \
    '| Company | Note |' \
    '|---|---|' \
    '| Nilus | No direct bank execution; payments export as a file |' \
    '| Atlar | Stated no; its own post logs nightly sweeps |'
  expect_green 'semicolon, both in cells' "$tmp/r-semi-cell.md"
  cases=$((cases + 1))

  # --- the two truth-routed rows ------------------------------------------------------------------
  # They must NOT move the exit code. expect_route asserts FAILS is empty as well as ROUTES full,
  # so a row promoted to blocking by a careless TSV edit is caught here and not in a run.
  write_lines "$tmp/r-exclusive.md" 'Round runs the only self-serve motion in a sales-led category.'
  expect_route 'exclusive routes to truth' "$tmp/r-exclusive.md" 'ROUTE: exclusive'
  cases=$((cases + 1))

  write_lines "$tmp/r-conditional.md" 'Kraken is the largest company here by revenue.'
  expect_route 'conditional routes to truth' "$tmp/r-conditional.md" 'ROUTE: conditional'
  cases=$((cases + 1))

  # The same comparative with a number standing behind it is not a finding. This is the half of
  # `conditional` the TSV cannot express, so it is the half most worth a case.
  write_lines "$tmp/r-conditional-ok.md" 'Kraken is the largest here, at 4,781 employees.'
  check_file "$tmp/r-conditional-ok.md"
  case "$ROUTES" in
    *conditional*) printf 'SELFTEST FAIL: conditional fired with a digit on the line; got: %s\n' \
                     "$ROUTES" >&2
                   return 1 ;;
    *) printf 'SELFTEST green OK %-30s -> not routed\n' 'conditional with a number' ;;
  esac
  cases=$((cases + 1))

  # --- the preprocessing strips, each proved by removing it ---------------------------------------
  write_lines "$tmp/pp-quoted.md" \
    'Payhawk says “Our robust platform is one of the largest.” on its homepage.'
  expect_green 'strip: inside curly quotes' "$tmp/pp-quoted.md"
  cases=$((cases + 1))

  write_lines "$tmp/pp-straight.md" \
    'Payhawk says "Our robust platform is one of the largest." on its homepage.'
  expect_green 'strip: inside straight quotes' "$tmp/pp-straight.md"
  cases=$((cases + 1))

  write_lines "$tmp/pp-unquoted.md" \
    'Payhawk says our robust platform is one of the largest on its homepage.'
  expect_red 'strip: same text unquoted' "$tmp/pp-unquoted.md" 'FAIL: llm_vocab'
  cases=$((cases + 1))

  write_lines "$tmp/pp-link.md" 'See [the robust index](https://example.com/robust) for pricing.'
  expect_green 'strip: link label and target' "$tmp/pp-link.md"
  cases=$((cases + 1))

  write_lines "$tmp/pp-heading.md" '## The robust index' '' 'The vendor ships payroll.'
  expect_green 'strip: heading line' "$tmp/pp-heading.md"
  cases=$((cases + 1))

  # --- dup_row_date, both directions --------------------------------------------------------------
  write_lines "$tmp/dup-red.md" \
    '| Company | Change | What it means |' \
    '|---|---|---|' \
    '| Kaluza | Flex for OEMs launched 2 Apr 2026. | Same argument on 2 Apr 2026. |'
  expect_red 'dup_row_date' "$tmp/dup-red.md" 'FAIL: dup_row_date'
  cases=$((cases + 1))

  # Two DIFFERENT dates in one row is the normal shape, and the row below is the exemplar's own.
  write_lines "$tmp/dup-green.md" \
    '| Company | Change | What it means |' \
    '|---|---|---|' \
    '| Atlar | Post dated 11 Aug 2026. | Contradicts the rule stated 10 April 2026. |'
  expect_green 'dup_row_date, two dates differ' "$tmp/dup-green.md"
  cases=$((cases + 1))

  # --- the rhythm signals are advisory ------------------------------------------------------------
  # A paragraph of flat long sentences must SIGNAL and must not FAIL. Both halves matter: without
  # the second, "advisory" is a word in a comment with nothing behind it.
  write_lines "$tmp/rhythm.md" \
    'The vendor ships payroll to forty customers across Iberia and France. The buyer signs a contract every quarter in the same market. The rail is owned outright by the vendor and not rented.'
  expect_signal 'R1 signals a long-only paragraph' "$tmp/rhythm.md" 'SIGNAL: R1'
  cases=$((cases + 1))
  if [ -n "$FAILS" ]; then
    printf 'SELFTEST FAIL: a rhythm signal produced a blocking finding: %s\n' "$FAILS" >&2
    return 1
  fi
  printf 'SELFTEST green OK %-30s -> exit unaffected\n' 'R1 is advisory'
  cases=$((cases + 1))

  # --- the rule table itself ----------------------------------------------------------------------
  # An absent table is a FAILURE, never zero rules reporting zero findings.
  write_lines "$tmp/tsv-probe.md" 'The vendor ships payroll.'
  local saved="$RULES_TSV"
  RULES_TSV="quality-bar/does-not-exist.tsv"
  expect_red 'absent rule table' "$tmp/tsv-probe.md" 'no rule table at'
  RULES_TSV="$saved"
  cases=$((cases + 1))

  expect_red 'absent brief' "$tmp/absent.md" 'no brief to grade'
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty brief' "$tmp/empty.md" 'no brief to grade'
  cases=$((cases + 1))

  # --- the red artefact ---------------------------------------------------------------------------
  # `46-spec.md` S2 Done: voice-lint flags S1-S6, M3 and M7 on the fixture. Each ID is asserted on
  # the TEXT the audit quoted, not merely on the rule id, so a fixture edit that drops a sentence
  # cannot leave this case green on a different sentence. It is authored elsewhere: if it is absent,
  # say so by path and fail, rather than stubbing it here and grading this script against its own
  # idea of the defect.
  fixture="$ROOT/quality-bar/fixtures/northwind-v1.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  check_file "$fixture"
  missing=""
  for want in \
    'S1|FAIL: process_subject|pages fetched' \
    'S2|FAIL: process_subject|before this brief' \
    'S3a|FAIL: process_subject|the thesis' \
    'S3b|FAIL: process_subject|crawling' \
    'S4|FAIL: process_subject|pages that answered' \
    'S5|FAIL: doc_passive|is given for' \
    'S6|FAIL: count_subject|Sixteen pages' \
    'M7|FAIL: dup_row_date|2 Apr 2026'; do
    id="${want%%|*}"; local rest2="${want#*|}"
    local rule="${rest2%%|*}" quote="${rest2#*|}"
    case "$FAILS" in
      *"$rule"*) : ;;
      *) missing="$missing $id(rule)"; continue ;;
    esac
    case "$FAILS" in
      *"$quote"*) : ;;
      *) missing="$missing $id(quote)" ;;
    esac
  done
  case "$SIGNALS" in
    *'SIGNAL: R1'*) : ;;
    *) missing="$missing M3(signal)" ;;
  esac
  case "$SIGNALS" in
    *'Two of the five buyers'*) : ;;
    *) missing="$missing M3(paragraph)" ;;
  esac
  if [ -n "$missing" ]; then
    printf 'SELFTEST FAIL: %s did not flag%s;\nFAILS: %s\nSIGNALS: %s\n' \
      "$fixture" "$missing" "${FAILS:-<none>}" "${SIGNALS:-<none>}" >&2
    return 1
  fi
  printf 'SELFTEST red OK   %-30s -> S1-S6, M3 and M7 all flagged\n' 'northwind-v1.md'
  cases=$((cases + 1))

  # THE EXEMPLAR ASSERTION, and the one that must never be weakened to reach green. If
  # `build/briefing.md` goes red here, the finding is the answer: report it and stop. Editing a
  # pattern until the accepted brief passes is how the rulebook ended up with a tricolon rule that
  # runs backwards against the artefact it produced.
  expect_green 'exemplar build/briefing.md' "$ROOT/$DEFAULT_TARGET"
  cases=$((cases + 1))

  # --- child-process cases ------------------------------------------------------------------------
  local proc="$tmp/proc-green"
  make_proc_root "$proc"
  write_lines "$proc/$DEFAULT_TARGET" \
    '# Competitor Intel Brief' \
    'The vendor ships payroll to 40 customers in Iberia. Two banks went live.'
  expect_proc_green 'child, clean default target' "$proc" 'VOICE-LINT-OK'
  cases=$((cases + 1))

  proc="$tmp/proc-red"
  make_proc_root "$proc"
  write_lines "$proc/$DEFAULT_TARGET" \
    '# Competitor Intel Brief' \
    'No heat pump on its integrations page or on 22 pages fetched.'
  expect_proc_red 'child, process-narrating default' "$proc" 'FAIL: process_subject'
  cases=$((cases + 1))

  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child, absent path argument' "$proc" 'no brief to grade' 'build/nope.md'
  cases=$((cases + 1))

  # G27, page mode: a run root with no headings.json, BRIEF_ROOT exported at it, and no resolver
  # beside the script. Default mode fails closed there; page mode grades, every rule live.
  proc="$tmp/proc-page"
  make_proc_root "$proc"
  rm "$proc/tools/slot-heading.sh" "$proc/build/headings.json"
  mkdir -p "$proc/run"
  write_lines "$proc/run/page.md" 'Competitor intel' '' 'The vendor ships payroll to 40 customers in Iberia. Two banks went live.'
  write_lines "$proc/run/page-red.md" 'Competitor intel' '' 'No heat pump on its integrations page or on 22 pages fetched.'
  PROC_RC=0
  PROC_OUT="$( BRIEF_ROOT="$proc/run" bash "$proc/tools/voice-lint.sh" --page "$proc/run/page.md" 2>&1 )" || PROC_RC=$?
  case "$PROC_RC:$PROC_OUT" in
    0:*VOICE-LINT-OK*) printf 'SELFTEST proc OK  %-30s -> exit 0\n' 'page mode, no headings record' ;;
    *) printf 'SELFTEST FAIL: page mode with no headings record exited %s: %s\n' "$PROC_RC" "$PROC_OUT" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))
  PROC_RC=0
  PROC_OUT="$( BRIEF_ROOT="$proc/run" bash "$proc/tools/voice-lint.sh" --page "$proc/run/page-red.md" 2>&1 )" || PROC_RC=$?
  case "$PROC_RC:$PROC_OUT" in
    1:*'FAIL: process_subject'*) printf 'SELFTEST proc red %-30s -> exit 1, rules live\n' 'page mode, process-narrating' ;;
    *) printf 'SELFTEST FAIL: page mode did not red a process sentence: exit %s: %s\n' "$PROC_RC" "$PROC_OUT" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))
  PROC_RC=0
  PROC_OUT="$( BRIEF_ROOT="$proc/run" bash "$proc/tools/voice-lint.sh" --page 2>&1 )" || PROC_RC=$?
  case "$PROC_RC:$PROC_OUT" in
    2:*'page mode grades one named file'*) printf 'SELFTEST proc red %-30s -> exit 2\n' 'page mode, no file named' ;;
    *) printf 'SELFTEST FAIL: page mode with no file fell back: exit %s: %s\n' "$PROC_RC" "$PROC_OUT" >&2
       return 1 ;;
  esac
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  if [ -e "$tmp" ]; then
    printf 'SELFTEST FAIL: residue left at %s\n' "$tmp" >&2
    return 1
  fi
  printf 'SELFTEST OK: %s cases, every rule in %s proved red on its own fixture, both capped rows proved at one and at two, the semicolon rule proved prose-only, both truth rows proved non-blocking, the quote, link and heading strips each proved by removing them, dup_row_date proved in both directions, R1 proved advisory, an absent rule table and an absent brief both red, %s flagged on S1-S6 M3 and M7, exemplar green, 6 child-process cases (3 in page mode), no residue at %s\n' \
    "$cases" "$RULES_TSV" "quality-bar/fixtures/northwind-v1.md" "$tmp"
}

main() {
  local target
  cd "$ROOT"
  if [ "$PAGE_MODE" -eq 1 ]; then
    if [ "$#" -ne 2 ]; then
      printf 'FAIL: page mode grades one named file: voice-lint.sh --page FILE\n' >&2
      exit 2
    fi
    shift
  fi
  target="${1:-$DEFAULT_TARGET}"
  check_file "$target"
  # ROUTES and SIGNALS print on stdout whatever the verdict: they are the truth critic's and the
  # voice critic's worklist, and a run that only sees them when the build is already red gets them
  # too late to use.
  [ -n "$ROUTES" ] && printf '%s' "$ROUTES"
  [ -n "$SIGNALS" ] && printf '%s' "$SIGNALS"
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  printf 'VOICE-LINT-OK (%s rules, 0 blocking findings in %s; %s routed to truth, %s rhythm signals)\n' \
    "$NRULES" "$target" \
    "$(printf '%s' "$ROUTES" | grep -c -e '^ROUTE' || true)" \
    "$(printf '%s' "$SIGNALS" | grep -c -e '^SIGNAL' || true)"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
