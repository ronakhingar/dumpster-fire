#!/bin/bash
# Discord Monitor Control Script
# Manage the Discord notification monitor and signal extractor services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_PLIST="$HOME/Library/LaunchAgents/com.trading.discord.monitor.plist"
EXTRACTOR_PLIST="$HOME/Library/LaunchAgents/com.trading.discord.extractor.plist"

case "$1" in
    start)
        echo "Starting Discord integration services..."

        # Start monitor
        if [ -f "$MONITOR_PLIST" ]; then
            launchctl load "$MONITOR_PLIST" 2>/dev/null || launchctl start com.trading.discord.monitor
            echo "  ✓ Monitor service started"
        else
            echo "  ⚠ Monitor plist not found. Run: ./discord_control.sh install"
        fi

        # Start extractor
        if [ -f "$EXTRACTOR_PLIST" ]; then
            launchctl load "$EXTRACTOR_PLIST" 2>/dev/null || launchctl start com.trading.discord.extractor
            echo "  ✓ Extractor service started"
        else
            echo "  ⚠ Extractor plist not found. Run: ./discord_control.sh install"
        fi
        ;;

    stop)
        echo "Stopping Discord integration services..."
        launchctl stop com.trading.discord.monitor 2>/dev/null
        launchctl unload "$MONITOR_PLIST" 2>/dev/null
        echo "  ✓ Monitor stopped"

        launchctl stop com.trading.discord.extractor 2>/dev/null
        launchctl unload "$EXTRACTOR_PLIST" 2>/dev/null
        echo "  ✓ Extractor stopped"
        ;;

    restart)
        echo "Restarting Discord integration services..."
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        echo "Discord Integration Status:"
        echo "=========================="

        # Check monitor
        if launchctl list | grep -q com.trading.discord.monitor; then
            echo "✓ Monitor: LOADED"
            PID=$(pgrep -f "discord_monitor.py" | head -1)
            if [ -n "$PID" ]; then
                echo "✓ Monitor Process: RUNNING (PID: $PID)"
            else
                echo "⚠ Monitor Process: NOT RUNNING"
            fi
        else
            echo "✗ Monitor: NOT LOADED"
        fi

        # Check extractor
        if launchctl list | grep -q com.trading.discord.extractor; then
            echo "✓ Extractor: LOADED"
        else
            echo "✗ Extractor: NOT LOADED"
        fi

        echo ""
        echo "Recent Activity:"
        echo "---------------"

        # Check for recent signals
        SIGNALS_FILE="$SCRIPT_DIR/journal/discord_signals.json"
        if [ -f "$SIGNALS_FILE" ]; then
            echo "Active signals:"
            python3 -c "import json; data=json.load(open('$SIGNALS_FILE')); print(f\"  {data.get('active_signal_count', 0)} signals active\"); print(f\"  Last updated: {data.get('last_updated', 'Never')[:19]}\")"
        else
            echo "  No signals file found"
        fi
        ;;

    test)
        echo "Testing Discord integration..."
        echo ""

        # Test notification capture
        echo "1. Testing notification monitor (single capture):"
        cd "$SCRIPT_DIR"
        python3 discord_monitor.py --once

        echo ""
        echo "2. Testing signal extraction:"
        python3 discord_signal_extractor.py

        echo ""
        echo "3. Testing integration module:"
        python3 discord_integration.py
        ;;

    install)
        echo "Installing Discord integration LaunchAgent services..."

        # Create monitor plist
        cat > "$MONITOR_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.discord.monitor</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/discord_monitor.py</string>
        <string>--loop</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/logs/discord_monitor.log</string>

    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/logs/discord_monitor_error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        # Create extractor plist (runs every 2 minutes)
        cat > "$EXTRACTOR_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.discord.extractor</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/discord_signal_extractor.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>

    <key>StartInterval</key>
    <integer>120</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/logs/discord_extractor.log</string>

    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/logs/discord_extractor_error.log</string>
</dict>
</plist>
EOF

        echo "  ✓ LaunchAgent plist files created"
        echo ""
        echo "To start the services:"
        echo "  ./discord_control.sh start"
        ;;

    *)
        echo "Discord Integration Control"
        echo "Usage: $0 {start|stop|restart|status|test|install}"
        echo ""
        echo "Commands:"
        echo "  install - Install LaunchAgent services"
        echo "  start   - Start Discord monitoring and extraction"
        echo "  stop    - Stop services"
        echo "  restart - Restart services"
        echo "  status  - Show service status and recent signals"
        echo "  test    - Run one-time capture and extraction test"
        exit 1
        ;;
esac
