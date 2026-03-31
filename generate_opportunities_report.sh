#!/bin/bash
# Generate daily opportunities report
# Called by cron at 6 AM PT (9 AM ET)

cd /Users/rhingar/Projects/dumpster-fire

# Ensure output directories exist
mkdir -p trade_opportunities logs

# Categorize messages
/usr/bin/python3 discord_message_categorizer.py

# Generate filtered report
REPORT_FILE="trade_opportunities/daily_report_$(date +%Y-%m-%d).txt"
./opportunities_filtered.sh > "$REPORT_FILE"

# Keep a 'latest' symlink
ln -sf "daily_report_$(date +%Y-%m-%d).txt" trade_opportunities/latest.txt

echo "Opportunities report generated at $(date)" >> logs/opportunities.log

# Send notification
/usr/bin/python3 notify_macos.py "Daily opportunities report generated" "Check trade_opportunities/latest.txt"
