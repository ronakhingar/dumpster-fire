#!/bin/bash
# Migration script: LaunchAgents → Cron (AWS-ready)
# Run this to switch from LaunchAgent services to cron-only setup

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$HOME/Library/LaunchAgents/backup_$(date +%Y%m%d_%H%M%S)"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Dumpster Fire: Migrate to Cron (AWS-Ready Setup)         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Backup current crontab
echo "📦 Step 1: Backing up current crontab..."
if crontab -l > /dev/null 2>&1; then
    crontab -l > "$SCRIPT_DIR/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
    echo "   ✓ Current crontab backed up"
else
    echo "   ℹ No existing crontab found"
fi

# Step 2: Stop and unload all LaunchAgent services
echo ""
echo "🛑 Step 2: Stopping LaunchAgent services..."

SERVICES=(
    "com.trading.agent"
    "com.trading.discord.monitor"
    "com.trading.discord.extractor"
    "com.trading.review"
    "com.dumpsterfire.imagecleanup"
)

for service in "${SERVICES[@]}"; do
    plist="$HOME/Library/LaunchAgents/${service}.plist"
    if [ -f "$plist" ]; then
        echo "   Stopping $service..."
        launchctl stop "$service" 2>/dev/null || true
        launchctl unload "$plist" 2>/dev/null || true
        launchctl remove "$service" 2>/dev/null || true
        echo "   ✓ $service stopped"
    fi
done

# Kill any running processes
echo ""
echo "🔪 Step 3: Killing running processes..."
pkill -f "agent.py --loop" 2>/dev/null && echo "   ✓ Killed agent.py" || echo "   ℹ No agent.py running"
pkill -f "discord_monitor.py --loop" 2>/dev/null && echo "   ✓ Killed discord_monitor.py" || echo "   ℹ No discord_monitor.py running"

# Step 4: Backup LaunchAgent plist files
echo ""
echo "💾 Step 4: Backing up LaunchAgent plist files..."
mkdir -p "$BACKUP_DIR"

for service in "${SERVICES[@]}"; do
    plist="$HOME/Library/LaunchAgents/${service}.plist"
    if [ -f "$plist" ]; then
        mv "$plist" "$BACKUP_DIR/"
        echo "   ✓ Backed up $service.plist"
    fi
done

echo "   📁 Backup location: $BACKUP_DIR"

# Step 5: Create logs directory
echo ""
echo "📝 Step 5: Setting up log directories..."
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/journal"
echo "   ✓ Log directories ready"

# Step 6: Install new crontab
echo ""
echo "⚙️  Step 6: Installing new crontab..."

if [ -f "$SCRIPT_DIR/crontab_aws_ready.txt" ]; then
    crontab "$SCRIPT_DIR/crontab_aws_ready.txt"
    echo "   ✓ New crontab installed"
else
    echo "   ✗ ERROR: crontab_aws_ready.txt not found!"
    echo "   Run this script from the dumpster-fire directory"
    exit 1
fi

# Step 7: Verify installation
echo ""
echo "✅ Step 7: Verifying installation..."
echo ""
echo "Current crontab:"
echo "─────────────────────────────────────────────────────────────"
crontab -l | grep -v "^#" | grep -v "^$"
echo "─────────────────────────────────────────────────────────────"

# Step 8: Start Discord monitor immediately
echo ""
echo "🚀 Step 8: Starting Discord monitor..."
cd "$SCRIPT_DIR"
/usr/bin/python3 discord_monitor.py --loop >> logs/discord_monitor.log 2>&1 &
DISCORD_PID=$!
echo "   ✓ Discord monitor started (PID: $DISCORD_PID)"

# Step 9: Display next scheduled jobs
echo ""
echo "📅 Next scheduled jobs (Eastern Time):"
echo "─────────────────────────────────────────────────────────────"

# Get current ET time
TZ=America/New_York date

echo ""
echo "Next agent runs:"
echo "  • Asia killzone:  20:00 ET (Mon-Fri)"
echo "  • London killzone: 02:00 ET (Tue-Sat)"
echo "  • NY AM killzone:  09:30 ET (Mon-Fri)"
echo "  • NY Lunch:        12:00 ET (Mon-Fri)"
echo "  • NY PM killzone:  13:30 ET (Mon-Fri)"
echo ""
echo "Other jobs:"
echo "  • Daily pipeline:        17:05 ET"
echo "  • Weekly review:         16:30 ET (Saturdays)"
echo "  • Discord report:        09:00 ET (Mon-Fri)"
echo "  • Discord monitor check: Every 5 minutes"
echo "  • Image cleanup:         Every 15 minutes"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                 MIGRATION COMPLETE! ✓                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ LaunchAgents → Cron migration successful"
echo ""
echo "📋 What changed:"
echo "  • All LaunchAgent services stopped and backed up"
echo "  • New cron-based schedule installed (AWS-ready)"
echo "  • All times now in Eastern Time (market timezone)"
echo "  • Works on macOS, Linux, AWS - no changes needed"
echo ""
echo "📁 Files created:"
echo "  • crontab_aws_ready.txt - Your new crontab"
echo "  • crontab_backup_*.txt - Backup of old crontab"
echo "  • $BACKUP_DIR/ - LaunchAgent plist backups"
echo ""
echo "🔍 Monitor logs:"
echo "  tail -f $SCRIPT_DIR/journal/agent_cron.log"
echo "  tail -f $SCRIPT_DIR/logs/discord_monitor.log"
echo ""
echo "⚠️  Current mode: DRY-RUN (paper trading)"
echo "  To go live: Edit run_agent.sh and remove --dry-run flag"
echo ""
echo "🚀 Ready for AWS migration!"
echo "  Just change AGENT_DIR in crontab when deploying to AWS"
echo ""
