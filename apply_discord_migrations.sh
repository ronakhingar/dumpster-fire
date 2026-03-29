#!/bin/bash
# Apply Discord signal enhancement migrations to existing PostgreSQL database

set -e

echo "Applying Discord Signal Enhancements to PostgreSQL..."
echo ""

# Load DATABASE_URL from .env
export $(grep DATABASE_URL .env | xargs)

if [ -z "$DATABASE_URL" ]; then
    echo "✗ DATABASE_URL not found in .env"
    exit 1
fi

echo "Database: $DATABASE_URL"
echo ""

# Apply migrations
echo "1. Applying discord_signals_migration.sql..."
psql "$DATABASE_URL" < db/discord_signals_migration.sql
echo "   ✓ Signal tables created"

echo ""
echo "2. Applying discord_trades_enhancement.sql..."
psql "$DATABASE_URL" < db/discord_trades_enhancement.sql
echo "   ✓ Trade lifecycle tables created"

echo ""
echo "3. Initializing Discord channels..."
python3 discord_db.py --init
echo "   ✓ Channels initialized"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✅ Discord Integration Complete"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Tables created:"
echo "  • discord_channels"
echo "  • discord_signals"
echo "  • discord_trade_lifecycle"
echo "  • message_intents"
echo "  • signal_performance"
echo "  • signal_author_stats"
echo "  • intent_patterns (with seed data)"
echo ""
echo "Views created:"
echo "  • active_discord_signals"
echo "  • open_trades"
echo "  • signal_effectiveness"
echo "  • top_signal_authors"
echo ""
echo "Test the system:"
echo "  python3 discord_db.py --test"
echo "  python3 discord_intent_detector.py --test"
echo ""
