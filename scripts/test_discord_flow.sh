#!/bin/bash
# Test the complete Discord integration flow

echo "Testing Discord Integration Flow"
echo "================================="
echo ""

cd "$(dirname "$0")"

# Step 1: Add a test signal
echo "Step 1: Adding test Discord message..."
./add_discord_signal.sh "QQQ is officially in a correction down 10% from highs almost at the 300MA. Next level is \$538. realistic targets for SPY are \$613 and \$590. QQQ targets are \$540 and \$520. Short-term bounce expected at support."

echo ""
echo "Step 2: Extracting signals..."
python3 discord_signal_extractor.py

echo ""
echo "Step 3: Testing integration..."
python3 discord_integration.py

echo ""
echo "Step 4: Checking active signals file..."
cat journal/discord_signals.json | python3 -m json.tool

echo ""
echo "✓ Test complete!"
echo ""
echo "To add real signals:"
echo "  ./add_discord_signal.sh \"Your Discord message\""
echo "  python3 discord_signal_extractor.py"
echo ""
echo "Agent will automatically read signals during trading cycles."
