#!/bin/bash
# Generate daily opportunities report
# Called by cron at 6 AM PT (9 AM ET)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Ensure output directories exist
mkdir -p trade_opportunities logs

# Categorize messages
/usr/bin/python3 -m discord.discord_message_categorizer

# Generate filtered report
REPORT_FILE="trade_opportunities/daily_report_$(date +%Y-%m-%d).txt"
./scripts/opportunities_filtered.sh > "$REPORT_FILE"

# Keep a 'latest' symlink
ln -sf "daily_report_$(date +%Y-%m-%d).txt" trade_opportunities/latest.txt

echo "Opportunities report generated at $(date)" >> logs/opportunities.log

# Send notification
/usr/bin/python3 -m utils.notify_macos "Daily opportunities report generated" "Check trade_opportunities/latest.txt"
