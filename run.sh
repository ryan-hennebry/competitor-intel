#!/bin/bash
# Run the competitor intelligence agent (agent-native)

cd "$(dirname "$0")" || { echo "Failed to change directory"; exit 1; }

# Check if configured
if ! grep -q "^name: ." context.md 2>/dev/null; then
  echo "Not configured. Run 'claude' interactively first."
  exit 1
fi

LOCKDIR=".agent.lock.d"

# Atomic lock acquisition using mkdir
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  if [ -f "$LOCKDIR/pid" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -f %m "$LOCKDIR/pid")))
    if [ "$LOCK_AGE" -lt 3600 ]; then
      echo "Agent already running (lock age: ${LOCK_AGE}s). Exiting."
      exit 1
    else
      echo "Stale lock detected (${LOCK_AGE}s old). Removing."
      rm -rf "$LOCKDIR"
      mkdir "$LOCKDIR" || { echo "Failed to acquire lock"; exit 1; }
    fi
  else
    rm -rf "$LOCKDIR"
    mkdir "$LOCKDIR" || { echo "Failed to acquire lock"; exit 1; }
  fi
fi

echo $$ > "$LOCKDIR/pid"

cleanup() {
  rm -rf "$LOCKDIR"
}
trap cleanup EXIT

# Agent-native: goal-oriented prompt, agent decides everything including delivery
claude -p "Run your scheduled task. Check context.md and output/last_run.json for state. Decide what action is needed. If appropriate, generate a briefing, create HTML/PDF outputs, and handle delivery. Signal completion by writing to output/last_run.json and updating context.md Last Run section." \
  --allowedTools "WebFetch,WebSearch,Read,Write,Glob,Bash,Skill"
