---
# design.md § 3, S13: a FAIL gets up to `rounds` arbiter repairs on the spans still failing (the
# repair group, skipped from the first round with none failing); a FAIL after the last round stops
# the run at verdict-final, which names the spans.
node: span-verify
role: span-verify
model: opus
effort: high
max_turns: 15
timeout_min: 4
inputs: [span-verify-in.md]
inline: [span-verify-in.md]
outputs: [span-verify.json]
schema: references/schemas/span-verdicts.schema.json
after: [prep-span-verify]
gate:
  - python3 tools/schema.py references/schemas/span-verdicts.schema.json "$BRIEF_ROOT/span-verify.json" && python3 tools/back-lane.py rows "$BRIEF_ROOT" "$BRIEF_ROOT/span-verify.json" --by span-verify --need "$BRIEF_ROOT/span-verify-set.json"
lane: back
nodes:
  - node: prep-span-verify
    run: python3 tools/back-lane.py span-verify "$BRIEF_ROOT" --base brief-author.json
    timeout_min: 1
    inputs: [brief.json, brief-author.json, claims.jsonl]
    outputs: [span-verify-in.md, span-verify-set.json]
    after: [final-build]
    lane: back
  - node: verdict
    run: python3 tools/verdict.py "$BRIEF_ROOT" --gate-record "$RUN_ROOT/state/done/final-build"
    timeout_min: 1
    inputs: [brief.json, verify.jsonl, web/index.html]
    after: [span-verify]
    lane: back
    critical: false
  # The repair rounds (S13): run 2 went from 8 failing spans to 2 in one round, so a fixed single
  # round stopped a converging loop. Each round re-reads only the spans still failing.
  - group: repair
    rounds: 3
    nodes:
      - node: prep-arbiter-repair
        when: python3 tools/back-lane.py repair-needed "$BRIEF_ROOT"
        run: python3 tools/back-lane.py arbiter "$BRIEF_ROOT" --repair --out arbiter-repair{round}-in.md
        timeout_min: 1
        outputs: [arbiter-repair{round}-in.md]
        after: [verdict]
        lane: back
      - node: arbiter-repair
        role: arbiter
        model: opus
        effort: high
        max_turns: 10
        timeout_min: 10
        template: references/stages/09-arbiter.md
        inputs: [arbiter-repair{round}-in.md]
        inline: [arbiter-repair{round}-in.md]
        outputs: [patches-repair{round}.json]
        schema: references/schemas/patches.schema.json
        after: [prep-arbiter-repair]
        gate:
          - python3 tools/schema.py references/schemas/patches.schema.json "$BRIEF_ROOT/patches-repair{round}.json"
          - python3 tools/apply-patches.py "$BRIEF_ROOT/patches-repair{round}.json" "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT" --out "$BRIEF_ROOT/brief-proposed.json"
          - python3 tools/span-ids.py --check "$BRIEF_ROOT" --brief brief-proposed.json
        lane: back
      - node: apply-repair
        run: cp "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT/brief-verified{round}.json" && python3 tools/apply-patches.py "$BRIEF_ROOT/patches-repair{round}.json" "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT"
        timeout_min: 1
        outputs: [brief.json, brief-verified{round}.json]
        after: [arbiter-repair]
        lane: back
      - node: final-build-repair
        run: python3 tools/assemble.py --relogo "$BRIEF_ROOT" && python3 tools/span-ids.py "$BRIEF_ROOT" && python3 build/web.py "$BRIEF_ROOT"
        timeout_min: 6
        outputs: [web/index.html]
        after: [apply-repair]
        gate:
          - python3 tools/schema.py build/web/brief.schema.json "$BRIEF_ROOT/brief.json"
          - python3 tools/brief-check.py "$BRIEF_ROOT/brief.json" "$BRIEF_ROOT"
          - python3 build/web.py --text "$BRIEF_ROOT/brief.json" --authored > "$BRIEF_ROOT/final-text.md" && python3 tools/claims-check.py --check "$BRIEF_ROOT/final-text.md" "$BRIEF_ROOT/claims.jsonl"
          - bash tools/voice-lint.sh --page "$BRIEF_ROOT/final-text.md"
          - bash tools/ai-smell.sh "$BRIEF_ROOT/final-text.md"
          - python3 tools/web-check.py "$BRIEF_ROOT"
        lane: back
      - node: prep-span-verify-repair
        run: python3 tools/back-lane.py span-verify "$BRIEF_ROOT" --base brief-verified{round}.json --tag repair{round}
        timeout_min: 1
        outputs: [span-verify-repair{round}-in.md, span-verify-repair{round}-set.json]
        after: [final-build-repair]
        lane: back
      - node: span-verify-repair
        role: span-verify
        model: opus
        effort: high
        max_turns: 15
        timeout_min: 4
        template: references/stages/10-span-verify.md
        inputs: [span-verify-repair{round}-in.md]
        inline: [span-verify-repair{round}-in.md]
        outputs: [span-verify-repair{round}.json]
        schema: references/schemas/span-verdicts.schema.json
        after: [prep-span-verify-repair]
        gate:
          - python3 tools/schema.py references/schemas/span-verdicts.schema.json "$BRIEF_ROOT/span-verify-repair{round}.json" && python3 tools/back-lane.py rows "$BRIEF_ROOT" "$BRIEF_ROOT/span-verify-repair{round}.json" --by span-verify-repair{round} --need "$BRIEF_ROOT/span-verify-repair{round}-set.json"
        lane: back
      - node: verdict-repair
        run: python3 tools/verdict.py "$BRIEF_ROOT" --gate-record "$RUN_ROOT/state/done/final-build-repair{round}"
        timeout_min: 1
        inputs: [brief.json, verify.jsonl, web/index.html]
        after: [span-verify-repair]
        lane: back
        critical: false
  - node: verdict-final
    run: python3 tools/verdict.py "$BRIEF_ROOT" --stop $(for f in "$RUN_ROOT"/state/done/final-build "$RUN_ROOT"/state/done/final-build-repair*; do test -f "$f" && echo --gate-record "$f"; done)
    timeout_min: 1
    inputs: [brief.json, verify.jsonl, web/index.html]
    after: [verdict-repair]
    lane: back
  # --push: D7. Exit 0 or 31 SHAREs; exit 14 (a stale dates.page) re-stamps, rebuilds, re-verdicts.
  - node: publish
    run: python3 tools/publish.py "$BRIEF_ROOT" --push > "$BRIEF_ROOT/11-delivery.md" 2>&1; rc=$?; if [ "$rc" -eq 14 ]; then python3 tools/span-ids.py "$BRIEF_ROOT" && python3 build/web.py "$BRIEF_ROOT" && python3 tools/verdict.py "$BRIEF_ROOT" --gate-record "$RUN_ROOT/state/done/final-build" && python3 tools/publish.py "$BRIEF_ROOT" --push > "$BRIEF_ROOT/11-delivery.md" 2>&1; rc=$?; fi; cat "$BRIEF_ROOT/11-delivery.md"; test "$rc" -eq 0 -o "$rc" -eq 31
    timeout_min: 6
    outputs: [11-delivery.md]
    after: [verdict-final]
    lane: back
---

# Span verify

You give a fresh truth read to the spans a patch touched. SPANS lists each span, why it is listed
and its text before the patch (`was`); PAGE is the whole page; ROWS holds the rows they cite.

## Steps

1. For each span in SPANS, test every factual clause against its cited rows: the figure, the
   qualifier, the date, the quantifier and any absence's bound. A clause with no row behind it
   fails.
2. Read the span in its sentence and section on PAGE: a patch that breaks its neighbour's sense,
   repeats it, or contradicts another span fails.
3. Give every span in SPANS one verdict: PASS, or FAIL with a note naming the clause and the row.

Done when the structured output holds a verdict for every span in SPANS. The gate checks that
coverage and writes each verdict to verify.jsonl at the span's hash.
