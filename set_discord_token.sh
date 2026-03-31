#!/bin/bash
# Quick script to set Discord bot token

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Discord Bot Token Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ -z "$1" ]; then
    echo "Usage:"
    echo "  ./set_discord_token.sh YOUR_TOKEN_HERE"
    echo ""
    echo "Or manually edit .env file and replace PASTE_YOUR_TOKEN_HERE"
    echo ""
    exit 1
fi

TOKEN="$1"

# Create .env file
cat > .env << EOF
# Discord Bot Configuration
# Generated on $(date)

DISCORD_BOT_TOKEN=$TOKEN
EOF

echo "✅ Token saved to .env file"
echo ""
echo "Ready to start! Run:"
echo "  ./start_discord_bot.sh"
echo ""
