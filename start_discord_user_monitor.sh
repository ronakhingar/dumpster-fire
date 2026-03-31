#!/bin/bash
# Start Discord user token monitor

cd "$(dirname "$0")"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo ""
    echo "❌ Error: .env file not found"
    echo ""
    exit 1
fi

# Run user monitor
echo ""
echo "Starting Discord user monitor..."
echo ""
python3 discord_user_monitor.py
