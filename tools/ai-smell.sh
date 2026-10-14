#!/usr/bin/env bash
# V21. The machine-authorship lint. It greps one markdown draft for the tells of LLM voice, collects
# every finding, and fails closed.
#
# WHY IT EXISTS. BEFORE V21, `docs/history/pipeline.md:234-236` said of the WHOLE voice standard in
# `references/briefing-template.md` that it "is an authoring standard and not a lint: nothing
# downstream greps for it, so a draft that ignores it renders green and reads wrong." That gap was
# real, and this script closes the machine-authorship half of it, and that half only. The same V21
# diff corrected the paragraph to match, and it then said of the other half, the rules about
# judgement and what a sentence has to earn, that no gate greps for it. THAT SENTENCE IS GONE. On
# 2026-09-18 `tools/voice-lint.sh` landed and greps most of that other half from
# `quality-bar/04-banned-patterns.tsv`, and `references/briefing-template.md` was rewritten to say so
# and to name what is still ungraded. Quoting either retired sentence as current would misreport a
# file this script cites; read `## The register` there for what it says now.
# `docs/history/register-calibration.md:86-97` books eight voice rules as ungradeable for want of "an
# actual LLM-voiced draft as the red artefact"; `tools/fixtures/ai-voiced-draft.md` is that artefact
# and this script is what reads it, which is why the selftest below asserts all six rules red on it
# rather than trusting a hand-written fixture alone.
# That calibration lived in `references/briefing-template.md` until 2026-09-18 and moved to
# `docs/history/register-calibration.md` when `quality-bar/` landed; the citations here follow it.
#
# NOT an eighth `audit()` check. `docs/PLAN.md` section 7 excludes an eighth gate check by name and
# R18 fixes the count at seven, so this is a standalone script the pipeline invokes, exactly as
# `tools/thesis-check.sh` and the ICP floor are standalone build-blocking lints.
#
# It collects every finding and only then exits non-zero, the same discipline `audit()` uses:
# reading the printed output is not evidence, a zero exit is.
#
# `grep` is wrapped to `ugrep` on this machine, where a pattern starting with `--` parses as an
# option, so every pattern below is passed after `-e`.
#
# WHAT IT DELIBERATELY DOES NOT CHECK, and why each one is absent rather than forgotten:
#
#   - Tricolons. `docs/history/register-calibration.md:82-85` measured them RED on the exemplar
#     (`build/briefing.md:26`, "no AP module, no self-serve, and payroll is a file pass-through")
#     and green on the weak brief. That file owns the measurement; this one does not reinstate a
#     rule the exemplar already fails.
#   - A mechanical summary sentence at the end of every section. `references/briefing-template.md`
#     :199-214 refuses it outright: the per-section judgement sentence is mandatory here, so the
#     rulebook's tell and this repository's requirement are the same string.
#   - Em dashes. Already gate-enforced in `build/build.py`; a second copy is a second thing to
#     drift.
#   - Symmetrical constructions. No detection separates them from the parallel evidence rows this
#     brief is built out of.
#   - Rhetorical questions. The `?` detection cannot tell one from `## Open Questions`, a mandatory
#     section; measured 2026-09-07, one `?`-terminated line in each of the two real briefs
#     (`build/briefing.md` and `output/research/initech-run/artefacts/briefing-initech.md`) and both
#     legitimate.
#
# PRECONDITION: none beyond the target file existing. No network, no MKT1 call, no env var, no
# build artefact, no run directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_TARGET="build/briefing.md"

# Newline-delimited, not an array: /bin/bash on macOS is 3.2, where expanding an empty array under
# `set -u` is itself an error.
FAILS=""

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# --- the rule table -------------------------------------------------------------------------------
# One row per rule, `~`-delimited, so a rule added later is one row and never a seventh scattered
# branch. Fields: id ~ threshold ~ case-mode (i insensitive, s sensitive) ~ label ~ extended regex.
# `~` is the delimiter because no pattern contains one; every pattern does contain `|`, which rules
# out the obvious choice.
#
# The string is DOUBLE-quoted because five apostrophe positions carry a straight `'` (`let`, `it`
# twice, `isn`, `in today`). No pattern contains `$` or a backtick, and bash leaves `\b` and `\*`
# untouched inside double quotes, so the regexes reach grep exactly as written here.
#
# CURLY AND STRAIGHT ALIKE, widened 2026-09-07: every apostrophe position is `(’|')?`, so `it’s
# worth noting`, `it's worth noting` and `its worth noting` all red. The class was straight-only
# until here while both real briefs are typeset with U+2019, so a correctly-typeset draft walked
# past A1, A2 and A5 untouched. It is an ALTERNATION and not the shorter `['’]?`: U+2019 is three
# bytes, and a bracket class over it is a set of BYTES wherever the locale is byte-oriented.
# MEASURED with `env -u LANG /usr/bin/grep -noiE`, the bracket form loses the curly line and the
# alternation keeps it under both locales. The trailing `?` is unchanged, so the apostrophe-free
# spelling is still caught.
RULES="A1~1~i~over-signposting~in this (section|brief|report|analysis)|let(’|')?s (break|dive|unpack|take a look)|to summari[sz]e|the key takeaway|as (we|you) (can see|have seen)|we will (examine|explore|look at|discuss)|it(’|')?s worth noting|it is worth noting
A2~1~i~stock LLM vocabulary~\b(delve|tapestry|pivotal|multifaceted|robust|ever-evolving|cutting-edge|game-chang[a-z]*|seamless[a-z]*|holistic)\b|realm of|underscore[sd]?\b|navigate the|in today(’|')?s|landscape of
A3~1~s~sentence-opening adverb~(^|[.!?] )(Crucially|Notably|Importantly|Interestingly|Moreover|Furthermore|Additionally|Ultimately|Fundamentally),
A4~1~i~hedged superlative~one of the (most|largest|biggest|fastest|leading)|among the (most|largest|leading)|arguably the|is perhaps the
A5~2~i~antithesis~not just |not merely |not simply |isn(’|')?t about |it(’|')?s not about |not only .* but also
A6~1~i~bold run-in and colon~\*\*[^*]{1,80}\*\* *:"

# A3 is the one case-sensitive rule: the adverbs are only a tell at the head of a sentence, and
# lower-cased mid-sentence they are ordinary English ("the number moved, notably, in May").
#
# A5's threshold is 2 and that is the whole rule. `docs/history/review/09-earns-its-place.md:105-115`
# caps the "not X, but Y" antithesis at ONE per brief, counted in the author's voice only with
# quoted competitor copy excluded, so the finding is the SECOND author-voice occurrence, never the
# first and never a quotation. The quotation half is handled once, in preprocess() below.
#
# A6's tell is the COLON, not the bold. The house claim-header is a bold FULL SENTENCE with a
# terminal period and is mandatory here (`docs/DESIGN.md` Vocabulary, "Claim-header"). MEASURED
# 2026-09-07 across both real briefs, and EVERY COUNT BELOW STATES ITS BOUND, because the two bounds
# disagree and an unlabelled number here reads as a typo for the other one. Under this rule's own
# `{1,80}` span: 7 occurrences of `**Sentence.**` in `build/briefing.md` and 8 in
# `output/research/initech-run/artefacts/briefing-initech.md`. Unbounded (`[^*]+`): 9 in each. Against
# either of those, 0 occurrences of `**Phrase**:` in either brief under either bound. That
# separation is why this narrowed form can land while `### What did not land, and what dropped it`
# in `references/briefing-template.md` refuses the rulebook's unnarrowed "bolded phrase as
# pseudo-structure" version, which would red the exemplar's nine claim-headers -- the unbounded
# count -- on sight.
#
# THE `{1,80}` BOUND IS ITSELF A BLIND SPOT and is named here rather than fixed: a bold run-in
# longer than 80 characters followed by a colon is invisible to A6. The exemplar's own two longest
# claim-headers, at 87 and 88 characters, are exactly the gap between the bounded 7 and the
# unbounded 9, so the shape demonstrably occurs in real prose. It is the sibling of grep's
# line-at-a-time reading, which hides a bold run-in wrapped across two source lines the same way.

rule_count() {
  # Counted from the table rather than hardcoded, so the success line cannot claim six rules while
  # five run.
  printf '%s\n' "$RULES" | grep -c -e '^A[0-9]' || true
}

# --- preprocessing --------------------------------------------------------------------------------
# THE SINGLE PLACE THE EXCLUSIONS LIVE. Every rule reads the preprocessed copy, so no rule carries
# its own quotation or URL escape hatch and none can be forgotten in a later row.
#
# Two strips, in this order:
#
#   1. URLs (`https?://` up to whitespace). A slug is not prose; `landscape-of-spend` inside a link
#      is not an author writing "landscape of".
#   2. Every span between MATCHED double quotes, curly `“ ”` and straight `" "` alike. This lint
#      grades the AUTHOR'S VOICE and never a quotation. It is V20's exclusion at
#      `docs/history/review/09-earns-its-place.md:105-115` generalised from A5 to every rule.
#      MEASURED: `build/briefing.md:62` carries Payhawk's own marketing line “Intelligence that
#      acts, not just reports.” in the What Each Company Says Its AI Does table. That is the
#      exemplar's ONLY raw A5 hit. Under the one-per-brief cap it is the first occurrence, so
#      without this strip the exemplar spends its single allowance on a competitor's advertising
#      copy and any one antithesis the author later writes reds a correctly-quoted brief.
#
# perl, not sed: the curly pair is multi-byte, and a negated character class over UTF-8 bytes in BSD
# sed is not the same thing as one over characters. `-CSD` decodes stdin and encodes stdout as
# UTF-8, so `[^\x{201D}]` means one character. `-p` is per-line, which also bounds a run-away
# unmatched quote to its own line.
#
# Matched text is BLANKED IN PLACE and lines are never deleted, so `grep -n` on the copy reports the
# real line number in the source file.
preprocess() {
  local src="$1" dst="$2"
  perl -CSD -pe 's{https?://\S+}{}g; s{\x{201C}[^\x{201D}]*\x{201D}}{}g; s{"[^"]*"}{}g' \
    "$src" >"$dst"
}

# --- the check ------------------------------------------------------------------------------------
# check_file populates FAILS for one target path and ALWAYS returns 0; the caller decides. Same
# contract as `check_file` in `tools/thesis-check.sh`, and it is what lets the selftest run every
# case in this shell without `set -e` ending the run at the first red.
check_file() {
  local f="$1" pp id thr cs label pat flags hits n reported oldifs h ln text

  FAILS=""

  # `test -s` first, and every rule skipped when it fires. An absent or empty draft is a FAILURE and
  # never a vacuous pass: `grep` over nothing matches nothing, and six rules reporting no findings on
  # a file that does not exist is precisely the shape of green that this repository treats as a lie.
  if [ ! -s "$f" ]; then
    add_fail "FAIL: no draft to grade at $f (missing or empty)"
    return 0
  fi

  pp="$(mktemp "${TMPDIR:-/tmp}/ai-smell-pp.XXXXXX")"
  preprocess "$f" "$pp"

  # `IFS='~' read` over the table. The loop body must run IN THIS SHELL or every add_fail is
  # discarded in a subshell, so the table is fed by a here-string redirection and never by a pipe.
  while IFS='~' read -r id thr cs label pat; do
    [ -n "$id" ] || continue

    # -o so the finding can quote the matched text, -n for the source line number. -i for every
    # rule but A3, whose tell is the capital.
    if [ "$cs" = "i" ]; then
      flags="-noiE"
    else
      flags="-noE"
    fi

    hits="$(grep $flags -e "$pat" "$pp" || true)"
    [ -n "$hits" ] || continue

    n="$(printf '%s\n' "$hits" | wc -l | tr -d ' ')"
    # Under threshold is not a finding. For A5 that is the cap doing its job: one antithesis in the
    # author's voice is allowed, so the first occurrence is passed over in silence.
    [ "$n" -ge "$thr" ] || continue

    # Report from the threshold'th occurrence onward, which for every rule but A5 is all of them and
    # for A5 is the second and any after it.
    reported="$(printf '%s\n' "$hits" | tail -n +"$thr")"

    # Split on newlines only, with globbing OFF: A6's matched text contains `**`, and an unguarded
    # word split would let the shell expand it against the working directory.
    oldifs="$IFS"
    set -f
    IFS=$'\n'
    for h in $reported; do
      ln="${h%%:*}"
      text="${h#*:}"
      add_fail "FAIL: $id $label at $f:$ln: $text"
    done
    IFS="$oldifs"
    set +f
  done <<<"$RULES"

  rm -f "$pp"
  return 0
}

# --- selftest -------------------------------------------------------------------------------------
# Proves each of the six rules goes red on its own minimal fixture, proves A5's cap in both
# directions, proves the two preprocessing exclusions by removing the exclusion and watching the same
# text go red, and leaves no residue. A check that has never gone red is an untested assertion.

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
    *"$want"*) printf 'SELFTEST red OK   %-26s -> %s' "$label" "$FAILS" ;;
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
  printf 'SELFTEST green OK %-26s -> no findings\n' "$label"
}

# --- process mode ---------------------------------------------------------------------------------
# Every case above calls check_file IN THIS SHELL, so `main()`, its `cd "$ROOT"`, the default target,
# the argument dispatch, the AI-SMELL-OK line and the non-zero exit are exercised by nothing. That
# gap is load-bearing and not hypothetical: inside `OUT="$( (f) 2>&1 )"` bash suspends `set -e`, so
# an in-process case cannot see an abort at all, and it was `main()` on the real corpus that killed
# `tools/known-traps.sh` while its twelve in-process cases stayed green. The cases below copy this
# script into a fixture root and run it as a CHILD with its own fully armed `set -euo pipefail`,
# which is the invocation a run actually makes. The idiom is `tools/thesis-check.sh:186-197`.
PROC_RC=0
PROC_OUT=""

# make_proc_root builds a fixture that looks like a checkout from this script's point of view: the
# script at tools/, and the build/ directory main() reads relatively after its cd.
make_proc_root() {
  local root="$1"
  mkdir -p "$root/tools" "$root/build"
  cp "${BASH_SOURCE[0]}" "$root/tools/ai-smell.sh"
}

run_proc() {
  local root="$1"
  shift
  PROC_RC=0
  PROC_OUT="$( bash "$root/tools/ai-smell.sh" "$@" 2>&1 )" || PROC_RC=$?
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
    *"$want"*) printf 'SELFTEST proc OK  %-26s -> exit 0, %s\n' "$label" "$PROC_OUT" ;;
    *) printf 'SELFTEST FAIL: %s was green but did not print %s; got: %s\n' \
         "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# expect_proc_red asserts the exit code AND the message AND, at every call site below, the absence of
# the success token. A script that printed AI-SMELL-OK and then exited 1 anyway is the exact defect a
# sibling gate shipped with.
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
    *AI-SMELL-OK*) printf 'SELFTEST FAIL: a red child run printed AI-SMELL-OK: %s\n' "$PROC_OUT" >&2
                   return 1 ;;
  esac
  printf 'SELFTEST proc red %-26s -> exit %s, %s\n' "$label" "$PROC_RC" "$want"
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp fixture cases=0

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/ai-smell-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # A clean draft first. Every red fixture below is this draft plus one tell, so a red case proves
  # the tell and not the scaffolding.
  write_lines "$tmp/clean.md" \
    '# Competitor Intel Brief' \
    '' \
    'The vendor ships payroll to 40 customers in Iberia.' \
    '' \
    '**The seat count moved in May.** Two banks went live.'
  expect_green 'clean draft' "$tmp/clean.md"
  cases=$((cases + 1))

  # R1..R6: each rule red on its own minimal fixture. One tell per file, so a fixture that reds two
  # rules would be a fixture bug and not a pass.
  write_lines "$tmp/a1.md" 'The vendor ships payroll.' "It's worth noting the seat count moved."
  expect_red 'A1 over-signposting' "$tmp/a1.md" 'FAIL: A1 over-signposting'
  cases=$((cases + 1))

  # The apostrophe widening, proved in both directions on the same phrase. The curly U+2019 is the
  # spelling both real briefs are typeset with and the one the straight-only class used to miss; the
  # straight case immediately above is what proves the widening did not trade one spelling for the
  # other, so the pair fails if either half stops matching.
  write_lines "$tmp/a1-curly.md" 'The vendor ships payroll.' 'It’s worth noting the seat count moved.'
  expect_red 'A1 curly apostrophe' "$tmp/a1-curly.md" 'FAIL: A1 over-signposting'
  cases=$((cases + 1))

  write_lines "$tmp/a2.md" 'The realm of spend management rewards a robust ledger.'
  expect_red 'A2 stock vocabulary' "$tmp/a2.md" 'FAIL: A2 stock LLM vocabulary'
  cases=$((cases + 1))

  write_lines "$tmp/a3.md" 'Crucially, the vendor ships payroll.'
  expect_red 'A3 opening adverb' "$tmp/a3.md" 'FAIL: A3 sentence-opening adverb'
  cases=$((cases + 1))

  # The same adverb lower-cased mid-sentence must stay green, or A3 is a word ban and not a
  # sentence-shape rule.
  write_lines "$tmp/a3-lower.md" 'The seat count moved, notably, in May.'
  expect_green 'A3 mid-sentence lowercase' "$tmp/a3-lower.md"
  cases=$((cases + 1))

  write_lines "$tmp/a4.md" 'It is one of the largest vendors in Iberia.'
  expect_red 'A4 hedged superlative' "$tmp/a4.md" 'FAIL: A4 hedged superlative'
  cases=$((cases + 1))

  write_lines "$tmp/a6.md" '**Key point**: the vendor ships payroll.'
  expect_red 'A6 bold run-in colon' "$tmp/a6.md" 'FAIL: A6 bold run-in and colon'
  cases=$((cases + 1))

  # The house claim-header, a bold full sentence with a terminal period, must stay green: it is
  # mandatory, and A6 flagging it would make the lint unusable on either real brief.
  write_lines "$tmp/a6-header.md" '**The seat count moved in May.** Two banks went live.'
  expect_green 'A6 claim-header allowed' "$tmp/a6-header.md"
  cases=$((cases + 1))

  # A5 in both directions, because the cap is the rule. One occurrence is the allowance and must be
  # green; two spend it and must be red on the SECOND, which is what the reported line number proves.
  write_lines "$tmp/a5-one.md" 'The tool is not just a ledger.'
  expect_green 'A5 one occurrence' "$tmp/a5-one.md"
  cases=$((cases + 1))

  write_lines "$tmp/a5-two.md" \
    'The tool is not just a ledger.' \
    '' \
    'The buyer is not merely a controller.'
  expect_red 'A5 two occurrences' "$tmp/a5-two.md" "FAIL: A5 antithesis at $tmp/a5-two.md:3"
  cases=$((cases + 1))

  # A5 on the curly apostrophe. The allowance is spent on line 1 by an apostrophe-free tell, so the
  # REPORTED occurrence is line 2 and the assertion on that line number is what proves `isn’t about`
  # matched rather than the cap merely counting to two.
  write_lines "$tmp/a5-curly.md" \
    'The tool is not just a ledger.' \
    'The buyer isn’t about to reconcile by hand.'
  expect_red 'A5 curly apostrophe' "$tmp/a5-curly.md" "FAIL: A5 antithesis at $tmp/a5-curly.md:2"
  cases=$((cases + 1))

  # The quote strip, proved by removing the quotes and nothing else. Both fixtures carry TWO
  # antitheses, so the green one is green because of the strip and not because of the cap.
  write_lines "$tmp/a5-quoted.md" \
    'Payhawk says “Intelligence that acts, not just reports.” on its homepage.' \
    'Embat says “Treasury that is not merely a ledger.” in the same table.'
  expect_green 'A5 inside curly quotes' "$tmp/a5-quoted.md"
  cases=$((cases + 1))

  write_lines "$tmp/a5-unquoted.md" \
    'Payhawk says Intelligence that acts, not just reports. on its homepage.' \
    'Embat says Treasury that is not merely a ledger. in the same table.'
  expect_red 'A5 same text unquoted' "$tmp/a5-unquoted.md" 'FAIL: A5 antithesis'
  cases=$((cases + 1))

  # The STRAIGHT-quote half of the same strip, which is a second substitution in preprocess() and
  # needs its own case: with only the curly case above, `s{"[^"]*"}{}g` could be deleted outright and
  # this suite would stay green. Same two antitheses, same words, straight `"` instead of `“ ”`, and
  # `$tmp/a5-unquoted.md` immediately above is the red half of the pair.
  write_lines "$tmp/a5-straight.md" \
    'Payhawk says "Intelligence that acts, not just reports." on its homepage.' \
    'Embat says "Treasury that is not merely a ledger." in the same table.'
  expect_green 'A5 inside straight quotes' "$tmp/a5-straight.md"
  cases=$((cases + 1))

  # The URL strip, proved the same way: identical words, once inside a link and once as prose.
  #
  # The tell here is `\brobust\b` and not A2's `landscape of`, and that is forced by the grammar of
  # the strip rather than chosen: `https?://\S+` stops at whitespace, so NO single URL token can
  # ever contain a space-bearing pattern and a `landscape of` pair would be green with the strip and
  # green without it -- a case that proves nothing. MEASURED 2026-09-07 by deleting the URL
  # substitution from a scratch copy: the `landscape of` version of this pair stayed green, this
  # `robust` version goes red. A space-free alternative in a slug is the only shape that can
  # discriminate, and `\b` matches at both `/` and `-`.
  write_lines "$tmp/url-green.md" 'See https://example.com/blog/robust-spend-controls for pricing.'
  expect_green 'A2 inside a URL' "$tmp/url-green.md"
  cases=$((cases + 1))

  write_lines "$tmp/url-red.md" 'See the robust spend controls for pricing.'
  expect_red 'A2 same text as prose' "$tmp/url-red.md" 'FAIL: A2 stock LLM vocabulary'
  cases=$((cases + 1))

  # A missing and an empty target are FAILURES. Without these two cases the whole script could be
  # pointed at nothing and report six clean rules.
  expect_red 'absent file' "$tmp/absent.md" 'no draft to grade'
  cases=$((cases + 1))

  : >"$tmp/empty.md"
  expect_red 'empty file' "$tmp/empty.md" 'no draft to grade'
  cases=$((cases + 1))

  # The red artefact `docs/history/register-calibration.md:86-97` asks for. It must red ALL SIX rules,
  # because a fixture that only reds four leaves two patterns proved by this file's own minimal
  # strings alone. It is authored elsewhere: if it is absent, say so by path and fail, rather than
  # stubbing it here and grading this script against its own idea of LLM voice.
  fixture="$ROOT/tools/fixtures/ai-voiced-draft.md"
  if [ ! -s "$fixture" ]; then
    printf 'SELFTEST FAIL: no LLM-voiced red artefact at %s\n' "$fixture" >&2
    return 1
  fi
  check_file "$fixture"
  local id missing=""
  for id in A1 A2 A3 A4 A5 A6; do
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
  printf 'SELFTEST red OK   %-26s -> all six rules red\n' 'ai-voiced-draft.md'
  cases=$((cases + 1))

  # THE EXEMPLAR ASSERTION, and the one that must never be weakened to reach green. If
  # `build/briefing.md` goes red here, the finding is the answer: report it and stop. Editing a
  # pattern until the accepted brief passes is how `docs/history/register-calibration.md:82-85` ended up
  # with a rule that runs backwards against the artefact it produced.
  expect_green 'exemplar build/briefing.md' "$ROOT/$DEFAULT_TARGET"
  cases=$((cases + 1))

  # P1: the whole script as a child, green, with NO argument, so the default target is the thing
  # under test and the documented default is exercised by the run rather than by prose.
  local proc="$tmp/proc-green"
  make_proc_root "$proc"
  write_lines "$proc/$DEFAULT_TARGET" \
    '# Competitor Intel Brief' \
    'The vendor ships payroll to 40 customers in Iberia.'
  expect_proc_green 'child, clean default target' "$proc" 'AI-SMELL-OK'
  cases=$((cases + 1))

  # P2: the same child on a draft with two antitheses. Exit non-zero, the finding on the stream, and
  # an explicit guard inside expect_proc_red that AI-SMELL-OK was NOT printed.
  proc="$tmp/proc-red"
  make_proc_root "$proc"
  write_lines "$proc/$DEFAULT_TARGET" \
    '# Competitor Intel Brief' \
    'The tool is not just a ledger.' \
    'The buyer is not merely a controller.'
  expect_proc_red 'child, LLM-voiced default' "$proc" 'FAIL: A5 antithesis'
  cases=$((cases + 1))

  # P3: the child with a path ARGUMENT naming a file that does not exist, which is both the argument
  # dispatch and the missing-file failure, proved in the process that actually exits.
  proc="$tmp/proc-absent"
  make_proc_root "$proc"
  expect_proc_red 'child, absent path argument' "$proc" 'no draft to grade' 'build/nope.md'
  cases=$((cases + 1))

  rm -rf "$tmp"
  trap - EXIT
  if [ -e "$tmp" ]; then
    printf 'SELFTEST FAIL: residue left at %s\n' "$tmp" >&2
    return 1
  fi
  printf 'SELFTEST OK: %s cases, 6 rules proved red individually, A1 and A5 red on the curly U+2019 apostrophe as well as the straight one, A5 green at one and red at two, the curly quote strip, the straight quote strip and the URL strip each proved by removing them, absent and empty red, %s red on all six, exemplar green, 3 child-process cases (clean default green with the token, LLM-voiced default red with no token, absent argument red), no residue at %s\n' \
    "$cases" "tools/fixtures/ai-voiced-draft.md" "$tmp"
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
  printf 'AI-SMELL-OK (%s rules, 0 findings in %s)\n' "$(rule_count)" "$target"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
