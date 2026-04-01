#!/bin/bash
# Schedule Weekly Review - Run every Saturday

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Run review on Saturday at 4:30 PM ET (1:30 PM PT)
# Market is closed on weekends, so no need to wait

echo "[$(date)] Starting weekly review..."
python3 -m src.daily_review

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Daily review completed successfully"
else
    echo "[$(date)] Daily review failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
