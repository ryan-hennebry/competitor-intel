#!/usr/bin/env bash
# PreToolUse hook: deny TaskOutput.
#
# WHY IT EXISTS. `references/runbook.md`'s orchestrator rules say the parent never calls TaskOutput,
# never polls and never reads a task's output file: it dispatches, ends the turn, and waits for the
# notification, with sentinel files as the barriers. That rule was written down and then broken,
# because a parent holding a task id can always reach for its output and the pull is strongest
# exactly when a stage is slow. `.claude/settings.json` wires this script to PreToolUse so the rule
# is enforced by the harness instead of remembered by the model.
#
# THE CHECK IS HERE, NOT IN THE MATCHER. `settings.json` already matches `TaskOutput`, so this
# script's own `tool_name` test is redundant today. It is kept because a matcher widened to `*` --
# the shape every other hook in `settings.local.json` uses -- would otherwise deny every tool call
# in the session, which is a far worse failure than the one being prevented.
#
# CONTRACT. Reads the PreToolUse payload as JSON on stdin. On TaskOutput it prints a deny decision
# and exits 0; on anything else it prints nothing and exits 0. It never exits non-zero: a hook that
# dies takes the tool call with it, and a JSON parse this script gets wrong must not be able to
# block an unrelated tool.
#
# NO `jq`, and no `grep -q`. jq is not guaranteed present wherever a run executes, and `grep -q`
# under `set -o pipefail` can SIGPIPE the process feeding it, turning a clean no-match into a
# non-zero exit -- which is the one thing this script may not do.
set -euo pipefail

payload="$(cat)"

# `tr` splits the payload on the JSON structural characters first, so each field lands on its own
# line whether the payload arrived pretty-printed or compact. Without it, the `.*` in the sed
# expression is greedy across a one-line payload and would report the LAST "tool_name" in it.
# No `head -1` in the pipeline for the pipefail reason above; the first match is taken with a
# parameter expansion instead.
tool="$(printf '%s' "$payload" | tr ',{}[]' '\n\n\n\n\n' \
  | sed -n 's/^[[:space:]]*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
tool="${tool%%$'\n'*}"

if [ "$tool" = "TaskOutput" ]; then
  printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",'
  printf '%s' '"permissionDecisionReason":"TaskOutput is denied by references/runbook.md: the '
  printf '%s' 'orchestrator dispatches, ends the turn and waits for the notification. Barriers are '
  printf '%s' 'sentinel files, never a read of a task output."}}'
  printf '\n'
fi

exit 0
