#!/bin/bash
# Launcher for the trading agent — called by cron at killzone opens.
# Runs in loop mode, scanning every 2 minutes during killzones.
# PID lock prevents duplicate processes from cron.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG="$PROJECT_DIR/journal/agent_cron.log"
PIDFILE="$PROJECT_DIR/journal/agent.pid"
mkdir -p "$PROJECT_DIR/journal"

# Rotate log if > 5MB
if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
    mv "$LOG" "$LOG.old"
fi

# Check if agent is already running
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') Agent already running (PID $OLD_PID) — skipping" >> "$LOG"
        exit 0
    fi
    rm -f "$PIDFILE"
fi

echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

echo "" >> "$LOG"
echo "═══════════════════════════════════════════════════════════" >> "$LOG"
echo "  AGENT START: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$LOG"
echo "  MODE: LIVE LOOP (2-min scan interval)" >> "$LOG"
echo "  PID: $$" >> "$LOG"
echo "═══════════════════════════════════════════════════════════" >> "$LOG"

cd "$PROJECT_DIR"
/usr/bin/python3 -m src.agent --loop --interval 2 >> "$LOG" 2>&1
