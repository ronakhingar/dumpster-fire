#!/bin/bash
# Auto-run Gemini transcript analysis daily until all sources are complete.
# Intended for cron: runs after free tier quota resets (midnight UTC / 5 PM PDT).
# Self-removes from cron once all work is done.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG="$PROJECT_DIR/journal/pipeline_cron.log"
PIDFILE="$PROJECT_DIR/journal/pipeline.pid"
mkdir -p "$PROJECT_DIR/journal"

# Rotate log if > 2MB
if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 2097152 ]; then
    mv "$LOG" "$LOG.old"
fi

# Prevent duplicate runs
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') Pipeline already running (PID $OLD_PID) — skipping" >> "$LOG"
        exit 0
    fi
    rm -f "$PIDFILE"
fi

echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# Check if there's still work to do
cd "$PROJECT_DIR"
REMAINING=$(/usr/bin/python3 -c "
from dotenv import load_dotenv; load_dotenv()
import psycopg2
conn = psycopg2.connect(host='localhost', port=25433, dbname='trading',
                        user='trading_agent', password='tr4d1ng_s3cur3_2026')
cur = conn.cursor()
cur.execute(\"\"\"
    SELECT COUNT(*) FROM media_sources ms
    WHERE NOT EXISTS (
        SELECT 1 FROM pipeline_state ps
        WHERE ps.source_ref = ms.file_path
          AND ps.stage = 'transcript_analysis'
          AND ps.status = 'completed'
    )
\"\"\")
print(cur.fetchone()[0])
conn.close()
" 2>/dev/null)

if [ "$REMAINING" = "0" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') All sources analyzed — removing cron job" >> "$LOG"
    crontab -l 2>/dev/null | grep -v "run_pipeline.sh" | crontab -
    exit 0
fi

echo "" >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') Starting analysis — $REMAINING sources remaining" >> "$LOG"

PYTHONUNBUFFERED=1 /usr/bin/python3 -m src.pipeline analyze >> "$LOG" 2>&1
EXIT_CODE=$?

echo "$(date '+%Y-%m-%d %H:%M:%S') Pipeline exited with code $EXIT_CODE" >> "$LOG"
