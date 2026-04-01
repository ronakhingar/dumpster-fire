#!/bin/bash
# Quick script to manually add Discord signals when you see important messages

# Usage:
#   ./add_discord_signal.sh "Your Discord message text here"
#   or just run it and paste the text when prompted

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_FILE="$SCRIPT_DIR/journal/discord_raw.jsonl"

# Create journal directory if needed
mkdir -p "$SCRIPT_DIR/journal"

if [ -z "$1" ]; then
    echo "Paste Discord message (Ctrl+D when done):"
    message=$(cat)
else
    message="$1"
fi

if [ -z "$message" ]; then
    echo "No message provided"
    exit 1
fi

# Create JSON entry
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S")
entry=$(cat <<EOF
{"timestamp": "$timestamp", "source": "discord_manual", "notification_id": "manual_$(date +%s)", "raw_text": "$message", "processed": false}
EOF
)

# Append to raw file
echo "$entry" >> "$RAW_FILE"

echo "✓ Signal added. Run extraction:"
echo "  python3 discord_signal_extractor.py"
