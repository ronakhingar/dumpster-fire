#!/bin/bash
# Quick Start Script - Start agent in current terminal or background

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory
mkdir -p logs

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Trading Agent - Quick Start                             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if already running
if pgrep -f "python3.*agent.py.*--loop" > /dev/null; then
    echo "⚠  Agent is already running!"
    echo ""
    PID=$(pgrep -f "python3.*agent.py.*--loop" | head -1)
    echo "   PID: $PID"
    ps -p "$PID" -o pid,etime,command | tail -1
    echo ""
    echo "To stop: pkill -f 'python3.*agent.py.*--loop'"
    echo "Or use: ./agent_control.sh stop"
    exit 1
fi

# Check .env file exists
if [ ! -f ".env" ]; then
    echo "✗ Error: .env file not found"
    echo "  Create it with your Alpaca API keys:"
    echo "  cp .env.example .env"
    exit 1
fi

# Show current time and killzone status
python3 -c "
from datetime import datetime
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
now_et = datetime.now(ET)
print(f'Current Time (ET): {now_et.strftime(\"%H:%M\")}')

killzones = {
    'NY AM': ('09:30', '11:00'),
    'NY Lunch': ('12:00', '13:00'),
    'NY PM': ('13:30', '16:00'),
}
hour_min = now_et.strftime('%H:%M')
for name, (start, end) in killzones.items():
    if start <= hour_min <= end:
        print(f'✓ Inside {name} killzone')
        break
else:
    print('⏰ Outside killzones - agent will sleep until next one')
"
echo ""

# Prompt for mode
echo "Choose mode:"
echo "  1) Foreground (see output, Ctrl+C to stop)"
echo "  2) Background (runs silently, check logs)"
echo ""
read -p "Mode [1]: " MODE
MODE=${MODE:-1}

LOG_FILE="logs/agent_$(date +%Y%m%d).log"

if [ "$MODE" = "2" ]; then
    echo ""
    echo "Starting agent in background..."
    nohup python3 agent.py --loop --interval 2 > "$LOG_FILE" 2>&1 &
    PID=$!
    sleep 2

    if ps -p $PID > /dev/null; then
        echo "✓ Agent started successfully!"
        echo "   PID: $PID"
        echo "   Log: $LOG_FILE"
        echo ""
        echo "Monitor with: tail -f $LOG_FILE"
        echo "Stop with:    pkill -f 'python3.*agent.py.*--loop'"
    else
        echo "✗ Agent failed to start. Check $LOG_FILE for errors."
        exit 1
    fi
else
    echo ""
    echo "Starting agent in foreground..."
    echo "Press Ctrl+C to stop"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    python3 agent.py --loop --interval 2
fi
