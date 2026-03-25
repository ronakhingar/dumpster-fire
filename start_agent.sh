#!/bin/bash
# Trading Agent Wrapper Script
# This script runs the agent continuously and handles logging

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set up logging
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/agent_$(date +%Y%m%d).log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Load environment variables if .env exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(cat "$SCRIPT_DIR/.env" | grep -v '^#' | xargs)
fi

log "================================================"
log "Starting Trading Agent"
log "Mode: Live Paper Trading"
log "Interval: 2 minutes"
log "Working Directory: $SCRIPT_DIR"
log "Python: $(which python3)"
log "================================================"

# Run the agent in loop mode
# The agent will auto-sleep outside killzones
python3 "$SCRIPT_DIR/agent.py" --loop --interval 2 2>&1 | while IFS= read -r line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line" | tee -a "$LOG_FILE"
done

# If the agent exits, log it
EXIT_CODE=$?
log "================================================"
log "Agent stopped with exit code: $EXIT_CODE"
log "================================================"

exit $EXIT_CODE
