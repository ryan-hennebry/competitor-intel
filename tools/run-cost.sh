#!/usr/bin/env bash
# V43. The run-cost meter. It reads one or more Claude Code session transcripts already on disk and
# prints what the run cost in tokens: parent turns, parent and nested dispatch counts, subagent
# transcript count, cache-read, cache-creation, output, and the one derived number that decides the
# bill -- parent resident tokens per turn. Two or more transcripts on one command line also print a
# side-by-side comparison table, which is what `docs/PLAN.md` V43's *the operator opens* clause asks for.
# `--caps <parent.jsonl>` prints the turn-cap tripwire instead, one line per subagent; see `caps`.
# `--by-model --caps`, in either order, prints the parent's block and by-model lines, then the caps
# lines (selftest case 17). Tokens only: `43-rulings.md` F1 dropped the cost mode.
#
# PRECONDITION: `jq` on PATH. Nothing else. No network, no MKT1 call, no run directory, no build
# artefact and no browser: every input is a `.jsonl` file already on disk, and `--selftest` reads
# only the fixture at `tools/fixtures/run-cost-sample.jsonl`, its `subagents/` directory and the
# flat-layout sidecars at `tools/fixtures/run-cost-flat/`.
#
# WHY IT EXISTS. `docs/PLAN.md` V43 books that nothing in this repository measures what a run costs
# -- section 8 already carried "no timing figure and no token estimate exists anywhere in the
# repository" -- and that every cheapening proposed before it rested on an estimate at four
# characters per token. Two real transcripts were measured on 2026-09-10 and their figures are
# carried in `baselines()` below as DATA, so V43's "reproduces both recorded runs' measured figures"
# is a check that goes RED when it stops holding rather than a sentence in a plan. Hand a recorded
# transcript to this script and every figure is compared against its baseline; hand it any other
# transcript and it simply prints the block.
#
# MEASURED, re-measured 2026-09-24 with one record per `message.id`, asserted by `baselines()`:
#   run 1, 2026-09-06, 05f278d4-fe6b-41b9-afb6-27f986ccea92: 251 parent turns, 35 parent and 16
#     nested dispatches, 51 subagent transcripts, cache-read 121,198,700, cache-creation 4,495,067,
#     output 900,248.
#   run 2, 2026-09-08 to 09, 0f0fc1fe-0aa3-4b09-b2b0-539f834dcc7b: 154 parent turns, 22 parent and 9
#     nested dispatches, 31 subagent transcripts, cache-read 72,939,546, cache-creation 3,566,492,
#     output 749,757.
# The 2026-09-10 figures (501 and 270 parent turns) summed every content-block record and roughly
# doubled each call; `dedupe` below is the fix. A turn here is one API call.
#
# THREE TRAPS, each measured and each load-bearing:
#   - `.message.usage.iterations[]` RESTATES the same usage numbers once per API iteration, so
#     summing it double-counts. Only the top-level `usage` keys are read. The fixture carries an
#     `iterations` array in the parent and in a subagent precisely so the selftest's green case is
#     green ONLY if both are ignored.
#   - A multi-megabyte transcript is never read whole. `docs/DESIGN.md:244-246` bans reading one
#     with the concatenate command; the aggregation is one `jq -n 'reduce (inputs | ...)'` streaming
#     record-by-record across every path passed as an argument, in bounded memory, and it never
#     slurps the subagent fan-in into one array. Selftest case 8 asserts BOTH halves against this
#     file's own source -- the banned concatenate command, and any slurping invocation of the
#     parser -- so the rule is code and not a comment.
#   - The parent/subagent split is BY FILE. `isSidechain` is false throughout the parent transcript
#     and true throughout every subagent transcript, so no record-level filter is needed and none is
#     applied; a filter would silently drop everything if the field were ever renamed.
#
# WHAT IT DELIBERATELY DOES NOT CHECK, absent rather than forgotten:
#   - Per-phase attribution. `docs/PLAN.md` V43 refuses it in writing: `message.usage` reports the
#     CUMULATIVE resident context per turn, so summing by phase double-counts, and parent against
#     subagent is the finest honest cut.
#   - Wall-clock time and MKT1 call counts. V43 records both as prose figures (5h16m, 12 and 15
#     calls); neither is derived here, so neither is asserted here.
#   - The `subagents/*.meta.json` sidecars as a COUNT. They only pick a flat-layout parent's
#     transcripts (`subagent_files`). Dispatch counts come from launch records (`toolUseResult.agentId`) in
#     the `.jsonl` files alone; the count of transcripts found is the CROSS-CHECK, never the source, and
#     a disagreement between them is printed as a finding with both numbers rather than resolved
#     silently in favour of either.
#   - Dollars. No price table lives here: a price is not a property of a transcript, and a stale
#     rate card would make every figure above look wrong for a reason that is not the run's.
#   - The full parent tool histogram. V43 records `Bash` 175, `Write` 16, `Read` 8, `Edit` 4 for run
#     1; only `Agent` is read here, because only dispatches are part of the bill's shape.
#
# It collects every finding and only then exits non-zero, the discipline `audit()` uses: reading the
# printed output is not evidence, a zero exit is.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FIXTURE="tools/fixtures/run-cost-sample.jsonl"

FAILS=""

add_fail() {
  FAILS="${FAILS}$1"$'\n'
}

# baselines carries the two runs, re-measured deduped on 2026-09-24, one per line, keyed by session UUID, which
# is the transcript's basename without `.jsonl`. Fields, in order:
#   uuid | parent turns | parent dispatches | nested dispatches | subagent files | subagent turns |
#   parent cache-read | subagent cache-read | parent cache-creation | subagent cache-creation |
#   parent output | subagent output
baselines() {
  printf '%s\n' \
    "05f278d4-fe6b-41b9-afb6-27f986ccea92|251|35|16|51|628|89602407|31596293|1281040|3214027|316895|583353" \
    "0f0fc1fe-0aa3-4b09-b2b0-539f834dcc7b|154|22|9|31|568|38250627|34688919|855687|2710805|179736|570021"
}

# require_jq asserts the script's one precondition once, at the boundary, so no downstream arm has
# to guess. Without it a missing parser exits 127 inside `aggregate`, which is indistinguishable
# from a parse error, and the script accuses a committed valid fixture of being malformed --
# measured. `.github/workflows/ci.yml` installs nothing and works only because the runner image
# happens to ship the parser, so the day that changes this message is what a reader gets.
require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    printf 'run-cost: PRECONDITION FAILED: jq is not on PATH, and every figure here is computed by it; install jq and re-run\n' >&2
    exit 1
  fi
}

# commify groups thousands with a portable sed loop. `printf "%'d"` is NOT used: it depends on the
# locale being set, and under the `LC_ALL=C` a CI runner may impose it prints the bare integer, so
# the alignment would differ between this machine and the runner for no visible reason.
commify() {
  printf '%s' "$1" | sed -e :a -e 's/\(.*[0-9]\)\([0-9]\{3\}\)/\1,\2/;ta'
}

row() {
  printf '  %-31s %13s%s\n' "$1" "$(commify "$2")" "${3:-}"
}

# DEDUPE_JQ defines `dedupe`, shared by `aggregate` and `aggregate_by_model` so the two cannot
# disagree on what a turn is. Claude Code writes one assistant record per content block and repeats
# the API call's usage on each (`docs/retro/2026-09-18-northwind/05-token-ledger.md:3`), so summing
# records counted run 1's parent as 501 turns and 183.8M cache-read against 251 calls and 89.6M.
# One entry per `message.id` is kept, the LAST copy, because `output_tokens` grows across the
# copies while the streamed call runs. `<synthetic>` records are client-side stand-ins with zero
# usage, not API calls, and are dropped. A record with no id keeps its own entry, never merged.
# Dispatches are counted from launch records, `toolUseResult.agentId` on a user record (the
# selector `kids_of` uses), never from `Agent` tool_use blocks: a refused dispatch ("Agent type ...
# not found") writes a tool_use and no transcript, so counting blocks reported one dispatch more
# than the files on disk (b2-code-measurements.md section 6). `recs` is every record for that
# reason; only assistant records become calls.
DEDUPE_JQ='def dedupe(recs): reduce recs as $r ({m:{}, n:0, a:0};
      .n += 1
    | .a += (if (($r.toolUseResult? | type) == "object") and ($r.toolUseResult.agentId? != null)
             then 1 else 0 end)
    | if ($r.type? != "assistant") or (($r.message.model? // "") == "<synthetic>") then .
      else .m[(($r.message.id? // "no-id-\(.n)") | tostring)] =
             {model: ($r.message.model? // "unknown"), u: ($r.message.usage? // {})}
      end);'

# aggregate streams every path in "$@" through ONE jq invocation and prints five integers:
# API calls (deduped turns), cache-read, cache-creation, output, launch records. `jq -n`
# with `inputs` inside a `reduce` reads record by record across all files, holding one small entry
# per call, which is why a 7.6 MB transcript costs nothing to measure and why nothing here
# concatenates a file first. `// 0` throughout, because a call without usage is a call, not a crash.
aggregate() {
  jq -n -r "$DEDUPE_JQ"' dedupe(inputs)
    | reduce .m[] as $c ({t:0, cr:0, cc:0, o:0, a:.a};
        .t  += 1
      | .cr += ($c.u.cache_read_input_tokens // 0)
      | .cc += ($c.u.cache_creation_input_tokens // 0)
      | .o  += ($c.u.output_tokens // 0))
    | "\(.t) \(.cr) \(.cc) \(.o) \(.a)"' "$@"
}

# aggregate_by_model prints one line per `message.model` over the same deduped calls: model, calls,
# input, output, cache-read, cache-write at the 5-minute TTL, cache-write at the 1-hour TTL. Token
# classes and never dollars (`68-review.md` Rec 9): the 1h write bills at a different rate, so it is
# split out rather than folded into one cache-creation figure. A record without the nested
# `usage.cache_creation` object reports its writes only in `cache_creation_input_tokens`, so the
# last column, write-untyped, carries whatever the two TTL columns miss (P1-verify Rec 2). The three
# write columns always sum to the block's cache-creation.
aggregate_by_model() {
  jq -n -r "$DEDUPE_JQ"' dedupe(inputs)
    | reduce .m[] as $c ({};
        .[$c.model] |= ((. // {c:0, i:0, o:0, cr:0, w5:0, w1:0, wu:0})
          | .c  += 1
          | .i  += ($c.u.input_tokens // 0)
          | .o  += ($c.u.output_tokens // 0)
          | .cr += ($c.u.cache_read_input_tokens // 0)
          | .w5 += ($c.u.cache_creation.ephemeral_5m_input_tokens? // 0)
          | .w1 += ($c.u.cache_creation.ephemeral_1h_input_tokens? // 0)
          | .wu += (($c.u.cache_creation_input_tokens // 0)
                    - ($c.u.cache_creation.ephemeral_5m_input_tokens? // 0)
                    - ($c.u.cache_creation.ephemeral_1h_input_tokens? // 0))))
    | to_entries | sort_by(.key)[]
    | "\(.key) \(.value.c) \(.value.i) \(.value.o) \(.value.cr) \(.value.w5) \(.value.w1) \(.value.wu)"' "$@"
}

# subagent_files prints, sorted and one per line, the transcripts of every agent $1 dispatched,
# nested ones included. Claude Code writes two layouts. A session's own transcript keeps its agents
# in a directory named after it, `<uuid>/subagents/`. A transcript that is itself an agent has no
# directory of its own: its descendants sit flat beside it in the session's `subagents/`, among the
# session's other agents, and only each `agent-<id>.meta.json`'s `parentAgentId` says whose they
# are. The flat arm walks that link from $1's id until no agent joins, so a stage agent's nested
# agents come too (P20-verify-2 Recommended 5, `73-web-plan.md` W10). It prints and registers
# nothing, so a caller runs it inside `$( )` and turns its non-zero exit into its own finding.
# A flat sidecar whose `.jsonl` is missing is dropped, because `probe` cross-checks the count
# against the dispatch records and reds the gap. Pass `keep` as $2 and it is printed anyway:
# `caps` has no such cross-check, so it takes the path and refuses on it (G78 (i),
# `W10-verify-2.md` Rec 2).
subagent_files() {
  local f="$1" keep="${2:-}" dir id pairs
  dir="${f%.jsonl}/subagents"
  if [ -d "$dir" ]; then
    find "$dir" -maxdepth 1 -type f -name 'agent-*.jsonl' | sort
    return 0
  fi
  case "$( basename "$f" )" in
    agent-*.jsonl) : ;;
    *) return 0 ;;
  esac
  dir="$( dirname "$f" )"
  id="$( basename "$f" .jsonl )"; id="${id#agent-}"
  set -- "$dir"/agent-*.meta.json
  [ -e "$1" ] || return 0
  pairs="$( jq -r '"\(.parentAgentId? // "-")\t\(input_filename)"' "$@" )" || return 1
  printf '%s\n' "$pairs" | awk -F '\t' -v root="$id" -v dir="$dir" '
    { n = split($2, p, "/"); c = p[n]; sub(/^agent-/, "", c); sub(/[.]meta[.]json$/, "", c)
      kid[NR] = c; par[NR] = $1 }
    END { have[root] = 1
      do { more = 0
        for (i = 1; i <= NR; i++)
          if (!(kid[i] in have) && (par[i] in have)) { have[kid[i]] = 1; more = 1 } } while (more)
      for (k in have) if (k != root) print dir "/agent-" k ".jsonl" }' \
    | while IFS= read -r sf; do
        if [ -f "$sf" ] || [ -n "$keep" ]; then printf '%s\n' "$sf"; fi
      done | sort
}

# probe measures one transcript into globals and registers findings in THIS shell. It is never
# called inside `$( )`: a helper that registers a finding from a subshell loses the registration,
# and the script would print a clean block and exit 0 on a broken transcript.
P_TURNS=0; P_CR=0; P_CC=0; P_OUT=0; P_AG=0
S_TURNS=0; S_CR=0; S_CC=0; S_OUT=0; S_AG=0
N_SUB=0
SUBS=""
PROBE_OK=0
BASELINE_ID=""
N_CMP=0
BY_MODEL=0

probe() {
  local f="$1" subs agg oldifs
  P_TURNS=0; P_CR=0; P_CC=0; P_OUT=0; P_AG=0
  S_TURNS=0; S_CR=0; S_CC=0; S_OUT=0; S_AG=0
  N_SUB=0
  SUBS=""
  PROBE_OK=0
  BASELINE_ID=""
  N_CMP=0

  if [ ! -f "$f" ]; then
    add_fail "run-cost: transcript not found: $f"
    return 0
  fi

  agg="$( aggregate "$f" 2>/dev/null )" || {
    add_fail "run-cost: unreadable or malformed JSON in the parent transcript: $f"
    return 0
  }
  read -r P_TURNS P_CR P_CC P_OUT P_AG <<<"$agg"

  # The subagent transcripts: either layout, see `subagent_files`.
  subs="$( subagent_files "$f" 2>/dev/null )" || {
    add_fail "run-cost: unreadable or malformed JSON among the agent-*.meta.json sidecars beside $f"
    return 0
  }
  SUBS="$subs"
  if [ -n "$subs" ]; then
    N_SUB="$( printf '%s\n' "$subs" | wc -l | tr -d ' ' )"
    oldifs="$IFS"
    IFS=$'\n'
    # shellcheck disable=SC2086
    set -- $subs
    IFS="$oldifs"
    agg="$( aggregate "$@" 2>/dev/null )" || {
      add_fail "run-cost: unreadable or malformed JSON among the subagent transcripts of $f"
      return 0
    }
    read -r S_TURNS S_CR S_CC S_OUT S_AG <<<"$agg"
  fi

  # A run that measures as costing nothing is a measurement failure, not a free run.
  if [ "$P_TURNS" -eq 0 ]; then
    add_fail "run-cost: 0 assistant turns in $f -- a run that measures as costing nothing is a measurement failure, not a free run"
    return 0
  fi

  # Dispatches counted from the records must equal the transcripts actually on disk. Neither number
  # is trusted over the other: the finding prints both.
  if [ "$(( P_AG + S_AG ))" -ne "$N_SUB" ]; then
    add_fail "$(printf 'run-cost: dispatch count disagrees with subagent transcripts in %s: %s parent + %s nested = %s, but %s subagents/agent-*.jsonl files on disk' \
      "$f" "$P_AG" "$S_AG" "$(( P_AG + S_AG ))" "$N_SUB")"
  fi

  PROBE_OK=1
  check_baseline "$f"
}

# cmp_field counts every comparison it makes, matching or not, and print_block prints that count.
# The count is what stops a comparison from being quietly deleted: drop one `cmp_field` call below
# and the printed coverage falls to 10, which the selftest asserts.
cmp_field() {
  local tag="$1" name="$2" want="$3" got="$4"
  N_CMP=$(( N_CMP + 1 ))
  if [ "$want" != "$got" ]; then
    add_fail "$(printf 'run-cost: %s baseline mismatch: %s expected %s, got %s' \
      "$tag" "$name" "$(commify "$want")" "$(commify "$got")")"
  fi
}

# check_baseline is what makes V43's claim falsifiable. The `< <(baselines)` redirection, and not a
# pipe, is deliberate: a pipe would run the loop in a subshell and every mismatch it found would be
# discarded with that subshell.
check_baseline() {
  local f="$1" uuid
  uuid="$( basename "$f" .jsonl )"
  while IFS='|' read -r b_uuid b_pt b_pd b_nd b_nf b_st b_pcr b_scr b_pcc b_scc b_po b_so; do
    if [ "$b_uuid" = "$uuid" ]; then
      BASELINE_ID="$( printf '%s' "$uuid" | cut -c1-8 )"
      cmp_field "$uuid" "parent turns" "$b_pt" "$P_TURNS"
      cmp_field "$uuid" "parent dispatches" "$b_pd" "$P_AG"
      cmp_field "$uuid" "nested dispatches" "$b_nd" "$S_AG"
      cmp_field "$uuid" "subagent transcripts" "$b_nf" "$N_SUB"
      cmp_field "$uuid" "subagent turns" "$b_st" "$S_TURNS"
      cmp_field "$uuid" "parent cache-read" "$b_pcr" "$P_CR"
      cmp_field "$uuid" "subagent cache-read" "$b_scr" "$S_CR"
      cmp_field "$uuid" "parent cache-creation" "$b_pcc" "$P_CC"
      cmp_field "$uuid" "subagent cache-creation" "$b_scc" "$S_CC"
      cmp_field "$uuid" "parent output" "$b_po" "$P_OUT"
      cmp_field "$uuid" "subagent output" "$b_so" "$S_OUT"
    fi
  done < <(baselines)
}

print_block() {
  local f="$1"
  printf 'run-cost: %s\n' "$f"
  row "parent turns" "$P_TURNS"
  row "subagent turns" "$S_TURNS"
  row "parent dispatches" "$P_AG"
  row "nested dispatches" "$S_AG"
  row "subagent transcripts" "$N_SUB" "$(printf '   (%s + %s)' "$P_AG" "$S_AG")"
  row "cache-read" "$(( P_CR + S_CR ))" \
    "$(printf '   (parent %s + subagent %s)' "$(commify "$P_CR")" "$(commify "$S_CR")")"
  row "cache-creation" "$(( P_CC + S_CC ))" \
    "$(printf '   (parent %s + subagent %s)' "$(commify "$P_CC")" "$(commify "$S_CC")")"
  row "output" "$(( P_OUT + S_OUT ))" \
    "$(printf '   (parent %s + subagent %s)' "$(commify "$P_OUT")" "$(commify "$S_OUT")")"
  # The number V43 says decides the bill: the bill is parent turn count multiplied by resident
  # context size, so resident size is printed rather than left to be divided by hand.
  row "parent resident tokens per turn" "$(( P_CR / P_TURNS ))"
  # Baseline coverage, printed rather than assumed. A recorded transcript that has been renamed or
  # copied still measures fine and prints a perfectly plausible block, and the only visible symptom
  # is that its eleven comparisons quietly stopped happening. This line is that symptom.
  if [ -n "$BASELINE_ID" ]; then
    printf '  (baseline %s: %s figures compared)\n' "$BASELINE_ID" "$N_CMP"
  else
    printf '  (no baseline)\n'
  fi
}

# print_by_model is `--by-model`: the parent and its subagent transcripts together, one line per
# model. It runs in THIS shell and registers its own finding, never from inside `$( )`.
print_by_model() {
  local f="$1" out oldifs m c i o cr w5 w1 wu
  oldifs="$IFS"
  IFS=$'\n'
  # shellcheck disable=SC2086
  set -- "$f" $SUBS
  IFS="$oldifs"
  out="$( aggregate_by_model "$@" 2>/dev/null )" || {
    add_fail "run-cost: --by-model could not read the transcripts of $f"
    return 0
  }
  printf '  by model: %-21s %7s %11s %11s %13s %13s %13s %13s\n' \
    "model" "calls" "input" "output" "cache-read" "write-5m" "write-1h" "write-untyped"
  while read -r m c i o cr w5 w1 wu; do
    [ -n "$m" ] || continue
    printf '  by model: %-21s %7s %11s %11s %13s %13s %13s %13s\n' "$m" "$(commify "$c")" \
      "$(commify "$i")" "$(commify "$o")" "$(commify "$cr")" "$(commify "$w5")" "$(commify "$w1")" \
      "$(commify "$wu")"
  done <<<"$out"
}

# --caps is the turn-cap tripwire (70-plan P7). A subagent's stage is the first
# `references/stages/NN-*.md` path in its first user record, and its cap is that template's
# `max_turns:`. An agent dispatched by one that names a stage is that stage's nested agent and takes
# `nested_max_turns:`, WHATEVER its own prompt names: `dispatch-contract.md:11` has every subagent
# carry a stage pointer, so the dispatcher link is resolved first (P7-verify R1). A dispatcher's
# links come from two places. A launch record carries `toolUseResult.agentId` and a timestamp; only
# a session root writes one, so a real agent transcript has none. Each sidecar names its
# `parentAgentId` (`sidecar_kids_of`), in either layout. A root naming a stage is linked by its
# sidecars only. Two dispatchers of one agent resolve to the EARLIEST launch, the one that created
# it, never to filename order (P7-verify Rec 3). Calls are deduped by
# `aggregate`, so a turn here is the meter's turn. Caps are tripwires, never kills: a breach prints
# OVER and the exit is 0. A missing stages directory exits 1; a missing template prints notemplate,
# a template without the key nocap.
# RUN_COST_STAGES points the selftest at fixture templates.
STAGES_DIR="${RUN_COST_STAGES:-$ROOT/references/stages}"

stage_of() {
  jq -n -r 'first(inputs | select(.type? == "user")) | .message.content?
    | if type == "string" then . else ([.[]? | select(.type? == "text") | .text] | join(" ")) end
    | [match("references/stages/([0-9][0-9]-[A-Za-z0-9_-]+)[.]md").captures[0].string]
    | first // empty' "$1"
}

kids_of() {
  jq -r 'select(.type? == "user") | select((.toolUseResult? | type) == "object")
    | select(.toolUseResult.agentId? != null)
    | "agent-\(.toolUseResult.agentId)@\(.timestamp? // "~")"' "$1"
}

# sidecar_kids_of prints `agent-<id>@~` for each flat sidecar beside $1 naming $1's id as its
# `parentAgentId`. A sidecar carries no launch time, so `~` sorts after every timestamp and a
# launch record, where one exists, stays the earliest dispatcher.
sidecar_kids_of() {
  local dir id
  dir="$( dirname "$1" )"
  id="$( basename "$1" .jsonl )"; id="${id#agent-}"
  set -- "$dir"/agent-*.meta.json
  [ -e "$1" ] || return 0
  jq -r --arg id "$id" 'select(.parentAgentId? == $id) | input_filename
    | sub("^.*/"; "") | sub("[.]meta[.]json$"; "") | "\(.)@~"' "$@"
}

# cap_of prints the integer value of key $2 in stage $1's frontmatter, or nothing.
cap_of() {
  local t="$STAGES_DIR/$1.md"
  [ -f "$t" ] || return 0
  awk -v k="$2:" 'NR == 1 { if ($0 != "---") exit; next } $0 == "---" { exit }
    $1 == k && $2 ~ /^[0-9]+$/ { print $2; exit }' "$t"
}

caps() {
  local f="$1" list sf a stage calls kids recs="" n=0 over=0 label key cap pa ps pc pk ts best
  if [ ! -f "$f" ]; then
    printf 'run-cost: transcript not found: %s\n' "$f" >&2
    exit 1
  fi
  if [ ! -d "$STAGES_DIR" ]; then
    printf 'run-cost: --caps: stages directory not found: %s\n' "$STAGES_DIR" >&2
    exit 1
  fi
  list="$( subagent_files "$f" keep 2>/dev/null )" || {
    printf 'run-cost: --caps: unreadable or malformed JSON among the agent-*.meta.json sidecars beside %s\n' "$f" >&2
    exit 1
  }
  if [ -n "$list" ]; then
    while IFS= read -r sf; do
      [ -n "$sf" ] || continue
      if [ ! -f "$sf" ]; then
        printf 'run-cost: --caps: a sidecar names an agent with no transcript on disk: %s\n' "$sf" >&2
        exit 1
      fi
      a="$( basename "$sf" .jsonl )"
      { stage="$( stage_of "$sf" 2>/dev/null )" \
          && calls="$( aggregate "$sf" 2>/dev/null )" \
          && kids="$( { kids_of "$sf" && sidecar_kids_of "$sf"; } 2>/dev/null | tr '\n' ' ' )"; } || {
        printf 'run-cost: --caps: unreadable or malformed JSON in %s\n' "$sf" >&2
        exit 1
      }
      recs="${recs}${a}|${stage}|${calls%% *}| ${kids}"$'\n'
      n=$(( n + 1 ))
    done <<<"$list"
  fi
  # A root that names a stage is that stage's lead (G78 (ii)). It joins `recs` link-only, calls
  # `-`: its kids resolve to its stage's `nested_max_turns`, and it is never counted or graded. Its
  # kids come from the flat sidecars beside it: an agent's own transcript records its Agent results
  # without `toolUseResult` (W18 stage 6, `agent-a84f2f41d9c05ee92`), so `kids_of` finds none
  # there. A session root has no sidecars beside it, so naming a stage links it to nothing.
  { stage="$( stage_of "$f" 2>/dev/null )" \
      && kids="$( sidecar_kids_of "$f" 2>/dev/null | tr '\n' ' ' )"; } || {
    printf 'run-cost: --caps: unreadable or malformed JSON in %s\n' "$f" >&2
    exit 1
  }
  [ -z "$stage" ] || recs="${recs}$( basename "$f" .jsonl )|${stage}|-| ${kids}"$'\n'
  while IFS='|' read -r a stage calls kids; do
    [ -n "$a" ] || continue
    [ "$calls" != "-" ] || continue
    label="$stage"; key="max_turns"; best=""
    while IFS='|' read -r pa ps pc pk; do
      [ -n "$ps" ] || continue
      case "$pk" in
        *" $a@"*)
          ts="${pk#* $a@}"; ts="${ts%% *}"
          if [ -z "$best" ] || [[ "$ts" < "$best" ]]; then
            best="$ts"; stage="$ps"; label="$ps/nested"; key="nested_max_turns"
          fi ;;
      esac
    done <<<"$recs"
    if [ -z "$stage" ]; then
      printf 'unmapped %s\n' "$a"
      continue
    fi
    if [ ! -f "$STAGES_DIR/$stage.md" ]; then
      printf 'notemplate %s %s %s\n' "$label" "$a" "$calls"
      continue
    fi
    cap="$( cap_of "$stage" "$key" )"
    if [ -z "$cap" ]; then
      printf 'nocap %s %s %s\n' "$label" "$a" "$calls"
    elif [ "$calls" -gt "$cap" ]; then
      printf 'OVER %s %s %s/%s\n' "$label" "$a" "$calls" "$cap"
      over=$(( over + 1 ))
    else
      printf 'within %s %s %s/%s\n' "$label" "$a" "$calls" "$cap"
    fi
  done <<<"$recs"
  printf 'RUN-COST-OK (--caps: %s subagent transcript(s), %s OVER)\n' "$n" "$over"
}

# ROWS holds one `|`-delimited record per successfully probed transcript, newline-delimited, because
# bash 3.2 has no associative arrays. Field 1 is the column header; every field after it is a
# `label=value` PAIR, and that is the point: the label travels WITH its value, so the table cannot
# be driven by a positional index held anywhere else. There is no index-to-label map to fall out of
# step, and reordering the pairs below reorders the printed rows correctly instead of transposing
# two values under each other's names -- which is what the earlier index map did silently.
ROWS=""

row_record() {
  printf '%s' "$( basename "$1" .jsonl | cut -c1-8 )"
  printf '|%s' \
    "parent turns=$P_TURNS" \
    "parent dispatches=$P_AG" \
    "nested dispatches=$S_AG" \
    "subagent transcripts=$N_SUB" \
    "cache-read=$(( P_CR + S_CR ))" \
    "cache-creation=$(( P_CC + S_CC ))" \
    "output=$(( P_OUT + S_OUT ))" \
    "parent resident tokens per turn=$(( P_CR / P_TURNS ))"
}

print_comparison() {
  local npairs i pair label line
  printf '\nrun-cost comparison\n'
  printf '  %-31s' 'metric'
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    printf ' %13s' "$( printf '%s' "$line" | cut -d'|' -f1 )"
  done < <(printf '%s' "$ROWS")
  printf '\n'
  # Row count and row labels both come from the pairs themselves, never from a second list.
  line="$( printf '%s' "$ROWS" | sed -n '1p' )"
  npairs="$( printf '%s' "$line" | tr '|' '\n' | sed -n '2,$p' | grep -c . || true )"
  i=1
  while [ "$i" -le "$npairs" ]; do
    label="$( printf '%s' "$line" | cut -d'|' -f"$(( i + 1 ))" )"
    label="${label%%=*}"
    printf '  %-31s' "$label"
    while IFS= read -r pair; do
      [ -n "$pair" ] || continue
      pair="$( printf '%s' "$pair" | cut -d'|' -f"$(( i + 1 ))" )"
      printf ' %13s' "$( commify "${pair#*=}" )"
    done < <(printf '%s' "$ROWS")
    printf '\n'
    i=$(( i + 1 ))
  done
}

count_rows() {
  if [ -z "$ROWS" ]; then
    printf '0'
    return 0
  fi
  printf '%s' "$ROWS" | grep -c . || true
}

main() {
  local f
  require_jq
  local want_caps=0
  ROWS=""
  BY_MODEL=0
  # The two flags in either order. Together they are one parent: its block and by-model lines,
  # then the caps lines.
  while [ "${1:-}" = "--caps" ] || [ "${1:-}" = "--by-model" ]; do
    if [ "$1" = "--caps" ]; then want_caps=1; else BY_MODEL=1; fi
    shift
  done
  if [ "$want_caps" -eq 1 ]; then
    if [ "$#" -ne 1 ]; then
      printf 'run-cost: usage: bash tools/run-cost.sh [--by-model] --caps <parent.jsonl>\n' >&2
      exit 1
    fi
    if [ "$BY_MODEL" -eq 1 ]; then
      probe "$1"
      if [ -n "$FAILS" ]; then
        printf '%s' "$FAILS" >&2
        exit 1
      fi
      print_block "$1"
      print_by_model "$1"
    fi
    caps "$1"
    return 0
  fi
  if [ "$#" -lt 1 ]; then
    printf 'run-cost: usage: bash tools/run-cost.sh [--by-model] <transcript.jsonl> [<transcript.jsonl> ...]\n' >&2
    exit 1
  fi
  for f in "$@"; do
    probe "$f"
    if [ "$PROBE_OK" -eq 1 ]; then
      print_block "$f"
      if [ "$BY_MODEL" -eq 1 ]; then
        print_by_model "$f"
      fi
      ROWS="${ROWS}$( row_record "$f" )"$'\n'
    fi
  done
  if [ "$( count_rows )" -ge 2 ]; then
    print_comparison
  fi
  if [ -n "$FAILS" ]; then
    printf '%s' "$FAILS" >&2
    exit 1
  fi
  printf 'RUN-COST-OK (%s transcript(s))\n' "$#"
}

# --- selftest -------------------------------------------------------------------------------------
# Ten cases over the committed fixture and mutated copies of it in a temp directory. No network,
# no real transcript, no run directory. The fixture's figures are hand-computed and written here, so
# a change to the fixture that changes a total shows up as a red case rather than as a new "correct"
# answer:
#
#   parent   3 API calls from 5 assistant records: `msg_fixture_dup` is written twice, as Claude
#            Code writes one record per content block, and only its LAST copy (output 200, not
#            12) counts. Its `Agent` block sits in the FIRST copy and its text in the last, as in
#            real transcripts, so counting `Agent` only on the kept copy reads 0 parent dispatches
#            (P1-verify Rec 1). The `<synthetic>` record is not a call. Summing records would print 5
#            parent turns, which is the red a dropped dedupe hits. The three `user` records and the
#            `system` record are not turns either;
#            cache-read 5,000 + 7,000 + 9,000 = 21,000; cache-creation 1,000 + 500 + 0 = 1,500;
#            output 100 + 200 + 50 = 350; 1 launch record (`toolUseResult.agentId`).
#   subagent 3 assistant turns across 2 files; cache-read 2,000 + 3,000 + 4,000 = 9,000;
#            cache-creation 100 + 50 + 25 = 175; output 30 + 20 + 10 = 60; 1 launch record.
#   totals   cache-read 30,000; cache-creation 1,675; output 410; 1 + 1 = 2 dispatches against 2
#            files on disk; parent resident tokens per turn 21,000 / 3 = 7,000.
#
# The iterations trap is exercised, not merely described. The parent's second assistant record
# carries `usage.iterations` restating 3,000 and 7,000 cache-read and 120 and 200 output, and a
# subagent record restates 4,000 and 10. Summing `iterations` instead of the top-level keys would
# print 31,000 parent cache-read and 13,000 subagent cache-read, so case 1 is green ONLY because
# they are ignored.

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

# Every case runs the script as a CHILD process with its own fully armed `set -euo pipefail`. That
# is not decoration: inside `OUT="$( f )"` bash suspends `set -e`, so an in-process case cannot see
# an abort at all, and it is `main()` -- its argument dispatch, its success token and its non-zero
# exit -- that a caller actually invokes. The idiom is `tools/ai-smell.sh:246-310`.
PROC_RC=0
PROC_OUT=""

# PROC_PATH, when set, replaces the child's PATH. Case 9 uses it to run the child with the parser
# genuinely absent, which no in-process case can simulate. The interpreter is named absolutely
# because `env` would otherwise resolve `bash` through the very PATH being emptied.
PROC_PATH=""

run_proc() {
  PROC_RC=0
  if [ -n "$PROC_PATH" ]; then
    PROC_OUT="$( env PATH="$PROC_PATH" "${BASH:-/bin/bash}" "${BASH_SOURCE[0]}" "$@" 2>&1 )" \
      || PROC_RC=$?
  else
    PROC_OUT="$( bash "${BASH_SOURCE[0]}" "$@" 2>&1 )" || PROC_RC=$?
  fi
  return 0
}

expect_proc_green() {
  local label="$1"
  shift
  run_proc "$@"
  if [ "$PROC_RC" -ne 0 ]; then
    printf 'SELFTEST FAIL: %s exited %s, want 0; got: %s\n' "$label" "$PROC_RC" "$PROC_OUT" >&2
    return 1
  fi
  case "$PROC_OUT" in
    *RUN-COST-OK*) printf 'SELFTEST proc OK   %-28s -> exit 0\n' "$label" ;;
    *) printf 'SELFTEST FAIL: %s was green but printed no success token; got: %s\n' \
         "$label" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# expect_proc_red asserts the exit code AND the message AND the absence of the success token. A
# script that printed RUN-COST-OK and then exited 1 anyway is the exact defect a sibling gate
# shipped with.
expect_proc_red() {
  local label="$1" want="$2"
  shift 2
  run_proc "$@"
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
    *RUN-COST-OK*) printf 'SELFTEST FAIL: a red child run printed RUN-COST-OK: %s\n' "$PROC_OUT" >&2
                   return 1 ;;
  esac
  printf 'SELFTEST proc red  %-28s -> exit %s\n' "$label" "$PROC_RC"
}

expect_line() {
  local label="$1" want="$2"
  case "$PROC_OUT" in
    *"$want"*) : ;;
    *) printf 'SELFTEST FAIL: %s missing line [%s]; got: %s\n' "$label" "$want" "$PROC_OUT" >&2
       return 1 ;;
  esac
}

# SELFTEST_TMP is a global. The EXIT trap runs after selftest()'s frame is gone, so a `local` named
# in the trap is unset under `set -u` and the trap dies with `tmp: unbound variable` on the failure
# path -- the one path where the reader needs the diagnosis and not a second error on top of it.
SELFTEST_TMP=""

selftest() {
  local tmp cases=0 uuid="05f278d4-fe6b-41b9-afb6-27f986ccea92" ncat nslurp t src

  require_jq
  cd "$ROOT"
  SELFTEST_TMP="$( mktemp -d "${TMPDIR:-/tmp}/run-cost-selftest.XXXXXX" )"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT
  tmp="$SELFTEST_TMP"

  # Case 1. GREEN on the committed fixture, every printed line asserted against the hand-computed
  # figures above, including the two totals that only come out right if `iterations` is ignored.
  expect_proc_green "fixture green" "$FIXTURE"
  expect_line "fixture green" "run-cost: $FIXTURE"
  expect_line "fixture green" "  parent turns                                3"
  expect_line "fixture green" "  subagent turns                              3"
  expect_line "fixture green" "  parent dispatches                           1"
  expect_line "fixture green" "  nested dispatches                           1"
  expect_line "fixture green" "  subagent transcripts                        2   (1 + 1)"
  expect_line "fixture green" "  cache-read                             30,000   (parent 21,000 + subagent 9,000)"
  expect_line "fixture green" "  cache-creation                          1,675   (parent 1,500 + subagent 175)"
  expect_line "fixture green" "  output                                    410   (parent 350 + subagent 60)"
  expect_line "fixture green" "  parent resident tokens per turn         7,000"
  # The fixture wears no recorded UUID, so it must SAY so rather than be silently uncompared.
  expect_line "fixture green" "  (no baseline)"
  expect_line "fixture green" "RUN-COST-OK (1 transcript(s))"
  cases=$(( cases + 1 ))

  # Case 2. RED when the transcript does not exist. A missing input is a finding, never a zero.
  expect_proc_red "missing transcript" "transcript not found" "$tmp/nope.jsonl"
  cases=$(( cases + 1 ))

  # Case 3. RED when parent plus nested dispatches disagrees with the `subagents/*.jsonl` files on
  # disk. A third subagent file is added to a copy, so 1 + 1 = 2 meets 3 files.
  mkdir -p "$tmp/mismatch/subagents"
  cp "$FIXTURE" "$tmp/mismatch.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/mismatch/subagents/"
  cp "$tmp/mismatch/subagents/agent-2222.jsonl" "$tmp/mismatch/subagents/agent-3333.jsonl"
  expect_proc_red "dispatch/file mismatch" "1 parent + 1 nested = 2, but 3 subagents/agent-*.jsonl files on disk" \
    "$tmp/mismatch.jsonl"
  cases=$(( cases + 1 ))

  # Case 3b. GREEN with a refused dispatch: an `Agent` tool_use with no launch record wrote no
  # transcript, so it is not a dispatch. Counting tool_use blocks reads 2 parent + 1 nested = 3
  # against 2 files and reds here (b2-code-measurements.md section 6).
  mkdir -p "$tmp/refused/subagents"
  cp "$FIXTURE" "$tmp/refused.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/refused/subagents/"
  printf '%s\n' '{"type":"assistant","isSidechain":false,"message":{"id":"msg_refused","model":"claude-opus-5","role":"assistant","content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"opus-high"}}],"usage":{"input_tokens":1,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":1}}}' \
    >>"$tmp/refused.jsonl"
  expect_proc_green "refused dispatch not counted" "$tmp/refused.jsonl"
  cases=$(( cases + 1 ))

  # Case 4. RED on zero assistant turns. No subagents directory, so the dispatch cross-check is
  # satisfied at 0 = 0 and this case proves the zero-turn guard alone.
  write_lines "$tmp/empty.jsonl" \
    '{"type":"user","message":{"role":"user","content":"hello"}}' \
    '{"type":"system","subtype":"summary","content":"nothing happened"}'
  expect_proc_red "zero assistant turns" "0 assistant turns" "$tmp/empty.jsonl"
  cases=$(( cases + 1 ))

  # Case 5. RED on a malformed JSON line in the parent transcript. A parser that swallowed it would
  # under-report the bill by however many records followed it.
  cp "$FIXTURE" "$tmp/broken.jsonl"
  printf '%s\n' '{"type":"assistant", this is not json' >>"$tmp/broken.jsonl"
  expect_proc_red "malformed JSON line" "malformed JSON in the parent transcript" "$tmp/broken.jsonl"
  cases=$(( cases + 1 ))

  # Case 6. RED when a transcript named with a recorded baseline UUID does not reproduce that
  # baseline. This is the case that makes V43's "reproduces both recorded runs' measured figures"
  # falsifiable: the fixture's 3 turns wear run 1's name and every figure is named in the finding.
  # ALL ELEVEN comparisons are asserted, not a sample of them. MEASURED before this was written:
  # with only six asserted, deleting the `subagent turns`, `parent output` or `subagent
  # cache-creation` comparison each left the selftest GREEN, so five of the eleven figures V43
  # claims to reproduce were being checked by nothing. The printed coverage line is asserted here
  # too, so deleting a comparison now fails twice over: the missing finding, and the count at 10.
  mkdir -p "$tmp/$uuid/subagents"
  cp "$FIXTURE" "$tmp/$uuid.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/$uuid/subagents/"
  expect_proc_red "baseline mismatch" "baseline mismatch: parent turns expected 251, got 3" "$tmp/$uuid.jsonl"
  expect_line "baseline mismatch" "baseline mismatch: parent dispatches expected 35, got 1"
  expect_line "baseline mismatch" "baseline mismatch: nested dispatches expected 16, got 1"
  expect_line "baseline mismatch" "baseline mismatch: subagent transcripts expected 51, got 2"
  expect_line "baseline mismatch" "baseline mismatch: subagent turns expected 628, got 3"
  expect_line "baseline mismatch" "baseline mismatch: parent cache-read expected 89,602,407, got 21,000"
  expect_line "baseline mismatch" "baseline mismatch: subagent cache-read expected 31,596,293, got 9,000"
  expect_line "baseline mismatch" "baseline mismatch: parent cache-creation expected 1,281,040, got 1,500"
  expect_line "baseline mismatch" "baseline mismatch: subagent cache-creation expected 3,214,027, got 175"
  expect_line "baseline mismatch" "baseline mismatch: parent output expected 316,895, got 350"
  expect_line "baseline mismatch" "baseline mismatch: subagent output expected 583,353, got 60"
  expect_line "baseline mismatch" "  (baseline 05f278d4: 11 figures compared)"
  cases=$(( cases + 1 ))

  # Case 7. GREEN on two transcripts at once, and the comparison table is what the second one buys.
  mkdir -p "$tmp/zeta-two/subagents"
  cp "$FIXTURE" "$tmp/zeta-two.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/zeta-two/subagents/"
  expect_proc_green "two transcripts" "$FIXTURE" "$tmp/zeta-two.jsonl"
  expect_line "two transcripts" "run-cost comparison"
  # EVERY row of the table is asserted, label and both values together, not a sample of two.
  # MEASURED before this was written: with only two rows asserted, swapping the `cache-creation` and
  # `output` entries transposed the two values under each other's labels and the selftest still
  # exited 0 -- the printed artefact V43's *the operator opens* clause names, mislabelling itself in
  # silence. The table is now built from `label=value` pairs so that transposition is structurally
  # impossible, and these assertions are the belt to that braces.
  expect_line "two transcripts" "  metric                               run-cost      zeta-two"
  expect_line "two transcripts" "  parent turns                                3             3"
  expect_line "two transcripts" "  parent dispatches                           1             1"
  expect_line "two transcripts" "  nested dispatches                           1             1"
  expect_line "two transcripts" "  subagent transcripts                        2             2"
  expect_line "two transcripts" "  cache-read                             30,000        30,000"
  expect_line "two transcripts" "  cache-creation                          1,675         1,675"
  expect_line "two transcripts" "  output                                    410           410"
  expect_line "two transcripts" "  parent resident tokens per turn         7,000         7,000"
  expect_line "two transcripts" "RUN-COST-OK (2 transcript(s))"
  cases=$(( cases + 1 ))

  # Case 8. The bounded-read rule of `docs/DESIGN.md:244-246` asserted against this file's own
  # source, so it is code rather than a comment. BOTH halves, because only the second one protects
  # bounded memory: no concatenate command, and no slurping invocation of the parser -- a `-s` or
  # `--slurp` reads all 51 subagent transcripts into one array in memory, which is the same defect
  # the concatenate ban exists to prevent and passes a grep that looks only for the word.
  # Both patterns are written with a bracketed letter, so neither command line below matches its own
  # regex; spelling either plainly would make the assertion count itself and fail forever.
  ncat="$( grep -cE -e '(^|[;|&( ])ca[t][[:space:]]' "${BASH_SOURCE[0]}" || true )"
  if [ "$ncat" -ne 0 ]; then
    printf 'SELFTEST FAIL: the script reads a transcript through the banned concatenate command on %s line(s)\n' \
      "$ncat" >&2
    return 1
  fi
  nslurp="$( grep -cE -e 'jq[^|;]*(-[s]([[:space:]]|$)|[-]-slurp)' "${BASH_SOURCE[0]}" || true )"
  if [ "$nslurp" -ne 0 ]; then
    printf 'SELFTEST FAIL: the script slurps the fan-in instead of streaming it, on %s line(s)\n' \
      "$nslurp" >&2
    return 1
  fi
  printf 'SELFTEST src OK    %-28s -> 0 banned reads, 0 slurps\n' "bounded-read rule"
  cases=$(( cases + 1 ))

  # Case 9. RED with the RIGHT diagnosis when the one declared precondition is absent. The child
  # runs with a PATH holding every tool this script uses EXCEPT the parser. MEASURED before the
  # guard existed: exit 127 inside `aggregate` landed in the malformed-JSON arm and the script
  # accused its own committed, valid fixture of being corrupt, so this case asserts the absence of
  # that accusation as well as the presence of the precondition message.
  mkdir -p "$tmp/nojq-bin"
  for t in dirname basename sed grep find sort wc tr cut mktemp rm mkdir cp env; do
    src="$( command -v "$t" || true )"
    if [ -n "$src" ]; then
      ln -s "$src" "$tmp/nojq-bin/$t"
    fi
  done
  PROC_PATH="$tmp/nojq-bin"
  expect_proc_red "jq precondition absent" "PRECONDITION FAILED: jq is not on PATH" "$FIXTURE"
  case "$PROC_OUT" in
    *"malformed JSON"*)
      printf 'SELFTEST FAIL: a missing parser was diagnosed as a corrupt transcript: %s\n' \
        "$PROC_OUT" >&2
      PROC_PATH=""
      return 1 ;;
  esac
  PROC_PATH=""
  cases=$(( cases + 1 ))

  # Case 10. `--by-model` on the fixture: the deduped `msg_fixture_dup` call is claude-opus-5's
  # only call, its LAST copy's 200 output and its 1h write of 500; the five id-less calls group as
  # unknown; `<synthetic>` gets no line. The ordinary block still prints above it. The id-less
  # records carry no `usage.cache_creation` object, so their 1,000 + 100 + 50 + 25 = 1,175 writes land
  # in write-untyped, and 500 + 1,175 = 1,675 is the block's cache-creation. Without that column the
  # writes summed to 500 and nothing said so (P1-verify Rec 2).
  expect_proc_green "by model" --by-model "$FIXTURE"
  expect_line "by model" "  parent turns                                3"
  expect_line "by model" "  by model: claude-opus-5               1           5         200         7,000             0           500             0"
  expect_line "by model" "  by model: unknown                     5          20         210        23,000             0             0         1,175"
  case "$PROC_OUT" in
    *"<synthetic>"*) printf 'SELFTEST FAIL: by model printed a <synthetic> line: %s\n' "$PROC_OUT" >&2
                     return 1 ;;
  esac
  cases=$(( cases + 1 ))

  # Case 11. `--caps` against the fixture templates. agent-1111 names 04-research and makes 2
  # deduped calls against `max_turns: 1`. agent-2222 names 04-research too, as the dispatch contract
  # has it, but agent-1111's launch record carries its agentId, so it is nested and takes
  # `nested_max_turns: 2`; checking its own path first prints `within 04-research agent-2222 1/1`
  # (P7-verify R1). A comparison that never fires reds on the missing OVER line.
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  expect_proc_green "caps over" --caps "$FIXTURE"
  expect_line "caps over" "OVER 04-research agent-1111 2/1"
  expect_line "caps over" "within 04-research/nested agent-2222 1/2"
  expect_line "caps over" "RUN-COST-OK (--caps: 2 subagent transcript(s), 1 OVER)"
  cases=$(( cases + 1 ))

  # Case 12. A template without `max_turns:` prints nocap, never a silent pass.
  mkdir -p "$tmp/nocap-stages"
  grep -v 'max_turns:' "$RUN_COST_STAGES/04-research.md" >"$tmp/nocap-stages/04-research.md"
  export RUN_COST_STAGES="$tmp/nocap-stages"
  expect_proc_green "caps nocap" --caps "$FIXTURE"
  expect_line "caps nocap" "nocap 04-research agent-1111 2"
  expect_line "caps nocap" "nocap 04-research/nested agent-2222 1"
  cases=$(( cases + 1 ))

  # Case 13. With the stage path gone from agent-1111's first user record, agent-1111 is unmapped
  # and agent-2222 is no longer nested: a dispatcher counts only when it names a stage itself, so
  # agent-2222 falls back to its own path and the lead cap.
  mkdir -p "$tmp/unmapped/subagents"
  cp "$FIXTURE" "$tmp/unmapped.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/unmapped/subagents/"
  sed 's#references/stages/04-research[.]md#nothing#' "${FIXTURE%.jsonl}/subagents/agent-1111.jsonl" \
    >"$tmp/unmapped/subagents/agent-1111.jsonl"
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  expect_proc_green "caps unmapped" --caps "$tmp/unmapped.jsonl"
  expect_line "caps unmapped" "unmapped agent-1111"
  expect_line "caps unmapped" "within 04-research agent-2222 1/1"
  cases=$(( cases + 1 ))

  # Case 14. The boundary and the FIRST path (P7-verify Rec 1). Caps of 2 and 1 equal the calls,
  # so `-ge` would print OVER; agent-1111's first message names 04 before 05, and 05 has no
  # template, so taking the last path prints notemplate.
  mkdir -p "$tmp/edge-stages" "$tmp/edge/subagents"
  printf '%s\n' '---' 'max_turns: 2' 'nested_max_turns: 1' '---' >"$tmp/edge-stages/04-research.md"
  cp "$FIXTURE" "$tmp/edge.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/edge/subagents/"
  sed 's#research this, per references/stages/04-research[.]md#per references/stages/04-research.md then references/stages/05-thesis-lock.md#' \
    "${FIXTURE%.jsonl}/subagents/agent-1111.jsonl" >"$tmp/edge/subagents/agent-1111.jsonl"
  export RUN_COST_STAGES="$tmp/edge-stages"
  expect_proc_green "caps edge" --caps "$tmp/edge.jsonl"
  expect_line "caps edge" "within 04-research agent-1111 2/2"
  expect_line "caps edge" "within 04-research/nested agent-2222 1/1"
  cases=$(( cases + 1 ))

  # Case 15. The faults nocap used to cover (P7-verify Rec 2): a missing template prints
  # notemplate, and a missing stages directory exits 1 rather than passing every agent.
  mkdir -p "$tmp/empty-stages"
  export RUN_COST_STAGES="$tmp/empty-stages"
  expect_proc_green "caps notemplate" --caps "$FIXTURE"
  expect_line "caps notemplate" "notemplate 04-research agent-1111 2"
  export RUN_COST_STAGES="$tmp/no-such-dir"
  expect_proc_red "caps no stages dir" "stages directory not found" --caps "$FIXTURE"
  cases=$(( cases + 1 ))

  # Case 16. Two dispatchers of one agent (P7-verify Rec 3). agent-3333, a 03-selection lead that
  # sorts AFTER agent-1111, re-launches agent-2222 an hour after agent-1111 created it. The earliest
  # launch wins, so agent-2222 stays 04-research/nested; filename order would make it 03's.
  mkdir -p "$tmp/two-stages" "$tmp/two/subagents"
  cp "$ROOT/tools/fixtures/run-cost-sample/stages/04-research.md" "$tmp/two-stages/"
  printf '%s\n' '---' 'max_turns: 5' 'nested_max_turns: 5' '---' >"$tmp/two-stages/03-selection.md"
  cp "$FIXTURE" "$tmp/two.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/two/subagents/"
  write_lines "$tmp/two/subagents/agent-3333.jsonl" \
    '{"type":"user","message":{"role":"user","content":"select, per references/stages/03-selection.md"}}' \
    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"usage":{"output_tokens":1}}}' \
    '{"type":"user","timestamp":"2026-09-24T09:00:00.000Z","message":{"role":"user","content":"launched"},"toolUseResult":{"agentId":"2222"}}'
  export RUN_COST_STAGES="$tmp/two-stages"
  expect_proc_green "caps two dispatchers" --caps "$tmp/two.jsonl"
  expect_line "caps two dispatchers" "within 04-research/nested agent-2222 1/2"
  expect_line "caps two dispatchers" "within 03-selection agent-3333 1/5"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  # Case 17. `--by-model` and `--caps` together, in both orders: the block, the by-model lines of
  # case 10 and the caps lines of case 11 from one call, with no dollar figure anywhere (F1). Two
  # transcripts with `--caps` stay a usage error.
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  for t in "--by-model --caps" "--caps --by-model"; do
    # shellcheck disable=SC2086
    expect_proc_green "combined $t" $t "$FIXTURE"
    expect_line "combined $t" "  parent turns                                3"
    expect_line "combined $t" "  by model: claude-opus-5               1           5         200         7,000             0           500             0"
    expect_line "combined $t" "OVER 04-research agent-1111 2/1"
    expect_line "combined $t" "RUN-COST-OK (--caps: 2 subagent transcript(s), 1 OVER)"
    case "$PROC_OUT" in
      *'$'*) printf 'SELFTEST FAIL: combined %s printed a dollar figure: %s\n' "$t" "$PROC_OUT" >&2
             return 1 ;;
    esac
  done
  expect_proc_red "caps with two transcripts" "usage: bash tools/run-cost.sh [--by-model] --caps" \
    --caps --by-model "$FIXTURE" "$FIXTURE"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  # Case 18. The flat layout (W10): the parent is itself an agent, so its descendants sit beside it
  # in one `subagents/` directory and only `tools/fixtures/run-cost-flat/`'s sidecars link them.
  # agent-d000 is the parent fixture; agent-9111 (the sample's agent-1111) names it as parent and
  # agent-2222 names 9111. 2222 sorts BEFORE its parent, so a walk that stops after one pass over
  # the sidecars misses it: only the fixpoint loop finds it (W10-verify Rec 1). agent-3333 is a
  # sibling the driver never dispatched. Measured flat, the transcript and cache-read lines must equal
  # case 1's and the caps lines case 11's; a lookup that took every sibling counts 3333 or the driver
  # itself, and one without the flat arm finds 0 files. `--caps` runs alone too, because it has no
  # dispatch cross-check to catch a dropped agent.
  mkdir -p "$tmp/flat/subagents"
  cp "$FIXTURE" "$tmp/flat/subagents/agent-d000.jsonl"
  cp "${FIXTURE%.jsonl}/subagents/agent-1111.jsonl" "$tmp/flat/subagents/agent-9111.jsonl"
  cp "${FIXTURE%.jsonl}/subagents/agent-2222.jsonl" "$tmp/flat/subagents/agent-2222.jsonl"
  cp "${FIXTURE%.jsonl}/subagents/agent-2222.jsonl" "$tmp/flat/subagents/agent-3333.jsonl"
  cp "$ROOT"/tools/fixtures/run-cost-flat/agent-*.meta.json "$tmp/flat/subagents/"
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  expect_proc_green "flat caps alone" --caps "$tmp/flat/subagents/agent-d000.jsonl"
  expect_line "flat caps alone" "within 04-research/nested agent-2222 1/2"
  expect_line "flat caps alone" "RUN-COST-OK (--caps: 2 subagent transcript(s), 1 OVER)"
  expect_proc_green "flat layout" --by-model --caps "$tmp/flat/subagents/agent-d000.jsonl"
  expect_line "flat layout" "  subagent transcripts                        2   (1 + 1)"
  expect_line "flat layout" "  cache-read                             30,000   (parent 21,000 + subagent 9,000)"
  expect_line "flat layout" "OVER 04-research agent-9111 2/1"
  expect_line "flat layout" "within 04-research/nested agent-2222 1/2"
  expect_line "flat layout" "RUN-COST-OK (--caps: 2 subagent transcript(s), 1 OVER)"
  case "$PROC_OUT" in
    *agent-3333*|*" agent-d000 "*)
      printf 'SELFTEST FAIL: flat layout counted an agent the driver never dispatched: %s\n' "$PROC_OUT" >&2
      return 1 ;;
  esac
  # A malformed sidecar is a finding in both modes, never a driver with no agents.
  printf '%s\n' '{"parentAgentId": not json' >"$tmp/flat/subagents/agent-4444.meta.json"
  expect_proc_red "flat bad sidecar" "malformed JSON among the agent-*.meta.json sidecars" \
    "$tmp/flat/subagents/agent-d000.jsonl"
  expect_proc_red "flat bad sidecar caps" "malformed JSON among the agent-*.meta.json sidecars" \
    --caps "$tmp/flat/subagents/agent-d000.jsonl"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  # Case 19 (G78 (i)). Case 18's flat layout with agent-2222.jsonl gone and its sidecar kept.
  # `--caps` alone has no dispatch cross-check, so it refuses on the missing transcript, where it
  # once printed RUN-COST-OK at 1 transcript (`W10-verify-2.md` Rec 2). The plain block still drops
  # the path and reds on the count, so the kept path reaches `caps` only.
  mkdir -p "$tmp/gone/subagents"
  cp "$tmp/flat/subagents"/agent-d000.jsonl "$tmp/flat/subagents"/agent-9111.jsonl "$tmp/gone/subagents/"
  cp "$ROOT"/tools/fixtures/run-cost-flat/agent-*.meta.json "$tmp/gone/subagents/"
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  expect_proc_red "flat caps missing transcript" "a sidecar names an agent with no transcript on disk" \
    --caps "$tmp/gone/subagents/agent-d000.jsonl"
  expect_line "flat caps missing transcript" "agent-2222.jsonl"
  expect_proc_red "flat block missing transcript" "1 parent + 1 nested = 2, but 1 subagents" \
    "$tmp/gone/subagents/agent-d000.jsonl"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  # Case 20 (G78 (ii)). The root is the stage lead: agent-9111 names 04-research and agent-2222's
  # sidecar names 9111 as its parent, so 2222 takes `nested_max_turns: 2`, as in case 18. The root
  # is a link only: no line, and not counted. A root that is graded prints agent-9111; one left out
  # of the links grades 2222 at 1/1. 9111's launch record loses its `toolUseResult`, as a real
  # agent transcript has it, so the link is the sidecar's. A root whose JSON breaks is refused,
  # never read as naming no stage. Known limit: a session root naming a stage has no sidecars
  # beside it, so its agent keeps its own path's cap. No session root in this project names one.
  mkdir -p "$tmp/root/subagents"
  cp "$tmp/flat/subagents"/agent-[d23]*.jsonl "$ROOT"/tools/fixtures/run-cost-flat/agent-*.meta.json \
    "$tmp/root/subagents/"
  sed 's#"toolUseResult":{[^}]*},##' "$tmp/flat/subagents/agent-9111.jsonl" \
    >"$tmp/root/subagents/agent-9111.jsonl"
  if grep -q toolUseResult "$tmp/root/subagents/agent-9111.jsonl"; then
    printf 'SELFTEST FAIL: flat caps lead root kept a toolUseResult in agent-9111\n' >&2
    return 1
  fi
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  expect_proc_green "flat caps lead root" --caps "$tmp/root/subagents/agent-9111.jsonl"
  expect_line "flat caps lead root" "within 04-research/nested agent-2222 1/2"
  expect_line "flat caps lead root" "RUN-COST-OK (--caps: 1 subagent transcript(s), 0 OVER)"
  case "$PROC_OUT" in
    *agent-9111*) printf 'SELFTEST FAIL: flat caps lead root graded the root: %s\n' "$PROC_OUT" >&2
                  return 1 ;;
  esac
  mkdir -p "$tmp/lead/subagents"
  cp "${FIXTURE%.jsonl}/subagents/agent-1111.jsonl" "$tmp/lead.jsonl"
  cp "${FIXTURE%.jsonl}/subagents/agent-2222.jsonl" "$tmp/lead/subagents/"
  expect_proc_green "session root names a stage" --caps "$tmp/lead.jsonl"
  expect_line "session root names a stage" "within 04-research agent-2222 1/1"
  printf '%s\n' '{"type":"user", not json' >"$tmp/root/subagents/agent-9111.jsonl"
  expect_proc_red "flat caps lead root malformed" "malformed JSON in $tmp/root/subagents/agent-9111.jsonl" \
    --caps "$tmp/root/subagents/agent-9111.jsonl"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  # Case 21 (W18-fix7-verify.md Rec 1). A session root's agents, linked as real ones are: no agent
  # writes a `toolUseResult`, so each dispatcher among them is linked by the sidecars beside it.
  # agent-1111 (04-research, launch record stripped) is 2222's parent. agent-5555, a copy of 2222,
  # names a parent outside this session, so nobody here links it and it keeps the lead cap. Without
  # the sidecar link 2222 prints 1/1; a link from any sidecar parent prints 5555 nested.
  mkdir -p "$tmp/sess/subagents"
  cp "$FIXTURE" "$tmp/sess.jsonl"
  sed 's#"toolUseResult":{[^}]*},##' "${FIXTURE%.jsonl}/subagents/agent-1111.jsonl" \
    >"$tmp/sess/subagents/agent-1111.jsonl"
  cp "${FIXTURE%.jsonl}/subagents/agent-2222.jsonl" "$tmp/sess/subagents/agent-2222.jsonl"
  cp "${FIXTURE%.jsonl}/subagents/agent-2222.jsonl" "$tmp/sess/subagents/agent-5555.jsonl"
  printf '%s\n' '{"agentType":"general-purpose","spawnDepth":1}' >"$tmp/sess/subagents/agent-1111.meta.json"
  printf '%s\n' '{"parentAgentId":"1111","spawnDepth":2}' >"$tmp/sess/subagents/agent-2222.meta.json"
  printf '%s\n' '{"parentAgentId":"6666","spawnDepth":2}' >"$tmp/sess/subagents/agent-5555.meta.json"
  if grep -q toolUseResult "$tmp/sess/subagents/agent-1111.jsonl"; then
    printf 'SELFTEST FAIL: session sidecar links kept a toolUseResult in agent-1111\n' >&2
    return 1
  fi
  export RUN_COST_STAGES="$ROOT/tools/fixtures/run-cost-sample/stages"
  expect_proc_green "session sidecar links" --caps "$tmp/sess.jsonl"
  expect_line "session sidecar links" "OVER 04-research agent-1111 2/1"
  expect_line "session sidecar links" "within 04-research/nested agent-2222 1/2"
  expect_line "session sidecar links" "within 04-research agent-5555 1/1"
  expect_line "session sidecar links" "RUN-COST-OK (--caps: 3 subagent transcript(s), 1 OVER)"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  # Case 22. A launch record outranks a sidecar link. agent-1111 launched agent-2222 at its
  # record's timestamp; 2222's sidecar names agent-3333, a 03-selection lead. A sidecar link's time
  # is `~`, after every timestamp, so 2222 stays 04-research/nested. A sidecar time that sorts
  # first makes it 03-selection/nested at 1/5.
  mkdir -p "$tmp/prec/subagents"
  cp "$FIXTURE" "$tmp/prec.jsonl"
  cp "${FIXTURE%.jsonl}"/subagents/agent-*.jsonl "$tmp/prec/subagents/"
  write_lines "$tmp/prec/subagents/agent-3333.jsonl" \
    '{"type":"user","message":{"role":"user","content":"select, per references/stages/03-selection.md"}}' \
    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"usage":{"output_tokens":1}}}'
  printf '%s\n' '{"parentAgentId":"3333","spawnDepth":2}' >"$tmp/prec/subagents/agent-2222.meta.json"
  export RUN_COST_STAGES="$tmp/two-stages"
  expect_proc_green "launch outranks sidecar" --caps "$tmp/prec.jsonl"
  expect_line "launch outranks sidecar" "within 04-research/nested agent-2222 1/2"
  expect_line "launch outranks sidecar" "within 03-selection agent-3333 1/5"
  unset RUN_COST_STAGES
  cases=$(( cases + 1 ))

  rm -rf "$tmp"
  trap - EXIT
  if [ -e "$tmp" ]; then
    printf 'SELFTEST FAIL: residue left at %s\n' "$tmp" >&2
    return 1
  fi
  printf 'SELFTEST OK: %s cases, fixture %s green on the hand-computed 3 parent turns / 21,000 parent cache-read / 30,000 total cache-read with usage.iterations ignored, one duplicated message.id and one <synthetic> record not counted, --by-model lines asserted with write-untyped, --caps OVER/within/nocap/notemplate/unmapped lines asserted with dispatcher-before-own-path, the cap boundary, the first path and the earliest dispatcher, the flat layout walked to a fixpoint past a sibling with a malformed sidecar red in both modes, --caps refusing a sidecar with no transcript, a stage-lead root linking its agents as nested and never graded and refused on bad JSON, agents of a session root linked by their sidecars, a launch record outranking a sidecar, 5 red arms proved as child processes (missing transcript, dispatch/file mismatch, zero assistant turns, malformed JSON, jq precondition absent), all 11 comparisons of the recorded run-1 baseline proved red on a transcript that does not reproduce it plus the printed coverage count, every row of the two-transcript comparison table asserted label and both values, both halves of the bounded-read rule asserted against this source, no residue at %s\n' \
    "$cases" "$FIXTURE" "$tmp"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
