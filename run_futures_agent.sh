#!/bin/bash
# Launcher for the futures trading agent — called by cron at killzone opens.
# Runs in loop mode, scanning every 2 minutes during killzones.
# PID lock prevents duplicate processes from cron.
# Requires TWS to be running on port 7497 (paper) or 7496 (live).

DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/journal/futures_agent_cron.log"
PIDFILE="$DIR/journal/futures_agent.pid"
mkdir -p "$DIR/journal"

# Rotate log if > 5MB
if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
    mv "$LOG" "$LOG.old"
fi

# Check if futures agent is already running
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') Futures agent already running (PID $OLD_PID) — skipping" >> "$LOG"
        exit 0
    fi
    rm -f "$PIDFILE"
fi

# Check if TWS is running (required for IBKR connection)
if ! pgrep -f "Trader Workstation" > /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ⚠️  TWS not running — futures agent cannot start" >> "$LOG"
    echo "$(date '+%Y-%m-%d %H:%M:%S')    Start TWS manually and try again" >> "$LOG"
    exit 1
fi

echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

echo "" >> "$LOG"
echo "═══════════════════════════════════════════════════════════" >> "$LOG"
echo "  FUTURES AGENT START: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$LOG"
echo "  MODE: LIVE LOOP (2-min scan interval)" >> "$LOG"
echo "  BROKER: Interactive Brokers (IBKR)" >> "$LOG"
echo "  INSTRUMENTS: MES (Micro E-mini S&P 500), MNQ (Micro Nasdaq 100)" >> "$LOG"
echo "  PID: $$" >> "$LOG"
echo "═══════════════════════════════════════════════════════════" >> "$LOG"

cd "$DIR"
/usr/bin/python3 futures_agent.py --loop --interval 2 >> "$LOG" 2>&1
