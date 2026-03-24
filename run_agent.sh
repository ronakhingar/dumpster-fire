#!/bin/bash
# Launcher for the trading agent — called by cron at killzone opens.
# Logs output to journal/agent_cron.log with rotation.

DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/journal/agent_cron.log"
mkdir -p "$DIR/journal"

# Rotate log if > 5MB
if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
    mv "$LOG" "$LOG.old"
fi

echo "" >> "$LOG"
echo "═══════════════════════════════════════════════════════════" >> "$LOG"
echo "  CRON TRIGGER: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$LOG"
echo "═══════════════════════════════════════════════════════════" >> "$LOG"

cd "$DIR"
/usr/bin/python3 agent.py >> "$LOG" 2>&1
