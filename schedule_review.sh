#!/bin/bash
# Schedule Daily Review - Run after market close

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Market closes at 4:00 PM ET (1:00 PM PT)
# Run review at 4:30 PM ET (1:30 PM PT) to ensure all data is settled

# Wait until market is closed
while true; do
    IS_OPEN=$(python3 -c "from alpaca_trader import api; print('yes' if api.get_clock().is_open else 'no')" 2>/dev/null)

    if [ "$IS_OPEN" = "no" ]; then
        echo "[$(date)] Market is closed. Starting daily review..."
        break
    fi

    echo "[$(date)] Market still open. Waiting 5 minutes..."
    sleep 300
done

# Wait an additional 30 minutes to ensure all settlements are complete
echo "[$(date)] Waiting 30 min for settlement..."
sleep 1800

# Run the review
echo "[$(date)] Running daily review..."
python3 "$SCRIPT_DIR/daily_review.py"

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Daily review completed successfully"
else
    echo "[$(date)] Daily review failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
