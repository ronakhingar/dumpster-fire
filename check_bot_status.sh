#!/bin/bash
# Check Discord bot setup and status

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Discord Bot Status Check"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check .env file
echo "1. Configuration File (.env):"
if [ -f ".env" ]; then
    echo "   ✅ .env file exists"

    # Check if token is configured
    if grep -q "PASTE_YOUR_TOKEN_HERE" .env; then
        echo "   ⚠️  Token NOT configured yet"
        echo ""
        echo "   → Set your token with:"
        echo "     ./set_discord_token.sh YOUR_TOKEN_HERE"
        echo ""
    else
        TOKEN=$(grep DISCORD_BOT_TOKEN .env | cut -d= -f2)
        if [ -n "$TOKEN" ]; then
            echo "   ✅ Token configured (${#TOKEN} characters)"
        else
            echo "   ⚠️  Token appears empty"
        fi
    fi
else
    echo "   ❌ .env file missing"
    echo ""
    echo "   → Run: ./set_discord_token.sh YOUR_TOKEN_HERE"
    echo ""
fi

echo ""
echo "2. Bot Process:"
if ps aux | grep -v grep | grep -q "discord_bot_monitor.py"; then
    PID=$(ps aux | grep -v grep | grep "discord_bot_monitor.py" | awk '{print $2}')
    echo "   ✅ Bot is RUNNING (PID: $PID)"
    echo ""
    echo "   → View logs: tail -f discord_bot.log"
    echo "   → Stop bot: kill $PID"
else
    echo "   ⚠️  Bot is NOT running"
    echo ""
    echo "   → Start bot: ./start_discord_bot.sh"
    echo "   → Or background: screen -S discord-bot ./start_discord_bot.sh"
fi

echo ""
echo "3. Output Directory:"
if [ -d "discord_history/realtime" ]; then
    echo "   ✅ Output directory exists"

    # Count files
    JSONL_COUNT=$(find discord_history/realtime -name "*.jsonl" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$JSONL_COUNT" -gt 0 ]; then
        echo "   📄 Found $JSONL_COUNT JSONL file(s)"

        # Show file sizes
        for file in discord_history/realtime/*.jsonl; do
            if [ -f "$file" ]; then
                LINES=$(wc -l < "$file" | tr -d ' ')
                echo "      $(basename $file): $LINES messages"
            fi
        done
    else
        echo "   ℹ️  No messages captured yet"
    fi

    # Count image directories
    IMAGE_DIRS=$(find discord_history/realtime -type d -name "*_files" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$IMAGE_DIRS" -gt 0 ]; then
        echo "   🖼️  Found $IMAGE_DIRS image directory(ies)"
    fi
else
    echo "   ℹ️  Output directory will be created on first run"
fi

echo ""
echo "4. Dependencies:"
python3 -c "import discord; import dotenv; import pytz" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ All Python packages installed"
else
    echo "   ⚠️  Missing packages - run: pip3 install discord.py python-dotenv pytz"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Summary
if [ -f ".env" ] && ! grep -q "PASTE_YOUR_TOKEN_HERE" .env; then
    if ps aux | grep -v grep | grep -q "discord_bot_monitor.py"; then
        echo "✅ Everything looks good! Bot is running and monitoring."
    else
        echo "⚠️  Token configured but bot not running."
        echo "   Run: ./start_discord_bot.sh"
    fi
else
    echo "⚠️  Setup incomplete. Set your token first:"
    echo "   ./set_discord_token.sh YOUR_TOKEN_HERE"
fi

echo ""
