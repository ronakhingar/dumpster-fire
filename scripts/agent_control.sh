#!/bin/bash
# Trading Agent Control Script
# Manage the trading agent service

PLIST_PATH="$HOME/Library/LaunchAgents/com.trading.agent.plist"
SERVICE_NAME="com.trading.agent"

case "$1" in
    start)
        echo "Starting trading agent service..."
        launchctl load "$PLIST_PATH" 2>/dev/null || launchctl start "$SERVICE_NAME"
        echo "✓ Agent service started"
        echo "  Check status with: ./agent_control.sh status"
        ;;

    stop)
        echo "Stopping trading agent service..."
        launchctl stop "$SERVICE_NAME" 2>/dev/null
        launchctl unload "$PLIST_PATH" 2>/dev/null
        echo "✓ Agent service stopped"
        ;;

    restart)
        echo "Restarting trading agent service..."
        launchctl stop "$SERVICE_NAME" 2>/dev/null
        launchctl unload "$PLIST_PATH" 2>/dev/null
        sleep 2
        launchctl load "$PLIST_PATH"
        echo "✓ Agent service restarted"
        ;;

    status)
        echo "Trading Agent Status:"
        echo "===================="

        # Check if launchd job is loaded
        if launchctl list | grep -q "$SERVICE_NAME"; then
            echo "✓ Service: LOADED"

            # Check if process is running
            PID=$(pgrep -f "python3.*agent.py.*--loop" | head -1)
            if [ -n "$PID" ]; then
                echo "✓ Process: RUNNING (PID: $PID)"
                ps -p "$PID" -o pid,ppid,etime,command | tail -1
            else
                echo "⚠ Process: NOT RUNNING (service loaded but process not found)"
            fi
        else
            echo "✗ Service: NOT LOADED"

            # Check if manually running
            PID=$(pgrep -f "python3.*agent.py.*--loop" | head -1)
            if [ -n "$PID" ]; then
                echo "⚠ Process: RUNNING MANUALLY (PID: $PID)"
            else
                echo "✗ Process: NOT RUNNING"
            fi
        fi

        echo ""
        echo "Recent Log Entries:"
        echo "-------------------"
        LOG_DIR="$(dirname "$0")/logs"
        if [ -d "$LOG_DIR" ]; then
            LATEST_LOG=$(ls -t "$LOG_DIR"/agent_*.log 2>/dev/null | head -1)
            if [ -n "$LATEST_LOG" ]; then
                echo "From: $LATEST_LOG"
                tail -5 "$LATEST_LOG"
            else
                echo "No log files found"
            fi
        fi
        ;;

    logs)
        LOG_DIR="$(dirname "$0")/logs"
        LATEST_LOG=$(ls -t "$LOG_DIR"/agent_*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            echo "Tailing: $LATEST_LOG"
            echo "Press Ctrl+C to stop"
            echo ""
            tail -f "$LATEST_LOG"
        else
            echo "No log files found in $LOG_DIR"
        fi
        ;;

    *)
        echo "Trading Agent Control"
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the agent service (auto-starts on boot)"
        echo "  stop    - Stop the agent service"
        echo "  restart - Restart the agent service"
        echo "  status  - Show current status and recent logs"
        echo "  logs    - Follow live logs (Ctrl+C to exit)"
        exit 1
        ;;
esac
