#!/bin/bash
# Quick status check for the competitor intelligence agent

cd "$(dirname "$0")" || exit 1

echo "=== Competitor Intelligence Agent Status ==="
echo ""

# Check configuration
if grep -q "^name: ." context.md 2>/dev/null; then
  COMPANY=$(grep "^name:" context.md | cut -d: -f2 | xargs)
  echo "Company: $COMPANY"

  COMPETITORS=$(grep -c "^\- " context.md 2>/dev/null || echo 0)
  echo "Competitors tracked: $COMPETITORS"
else
  echo "Status: NOT CONFIGURED"
  echo "Run 'claude' interactively to set up."
  exit 0
fi

# Check last run
if [ -f output/last_run.json ]; then
  LAST_STATUS=$(grep -o '"status": *"[^"]*"' output/last_run.json | cut -d'"' -f4)
  LAST_DATE=$(grep -o '"date": *"[^"]*"' output/last_run.json | cut -d'"' -f4)
  echo "Last run: $LAST_DATE ($LAST_STATUS)"
else
  echo "Last run: Never"
fi

# Check latest briefing
LATEST=$(ls -t output/briefings/*.md 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
  echo "Latest briefing: $(basename "$LATEST")"
fi

# Check lock
if [ -d ".agent.lock.d" ]; then
  echo "Agent: RUNNING"
else
  echo "Agent: Idle"
fi
