#!/bin/bash

echo "═══════════════════════════════════════════════════════════════"
echo "  DISCORD DEVTOOLS - LET'S TRY TOGETHER"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Step 1: Is Discord running?"
if pgrep -x "Discord" > /dev/null; then
    echo "  ✅ Discord is running"
else
    echo "  ❌ Discord is NOT running - please open Discord first"
    exit 1
fi

echo ""
echo "Step 2: Click on Discord to make sure it's the active app"
echo "        (Click anywhere in the Discord window)"
echo ""
echo "        Press Enter when ready..."
read

echo ""
echo "Step 3: Now look at the VERY TOP of your screen"
echo "        You should see a menu bar with:"
echo "        Discord | File | Edit | View | Window | Help"
echo ""
echo "Step 4: Click 'View' in the menu bar"
echo ""
echo "Step 5: Look for one of these options:"
echo "        • Toggle Developer Tools"
echo "        • Developer → Toggle Developer Tools"  
echo "        • Show Developer Tools"
echo ""
echo "Step 6: Click it!"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Did DevTools open? (It's a new window/panel with tabs like"
echo "Console, Network, Elements)"
echo ""
echo "If YES:"
echo "  1. Click the 'Console' tab"
echo "  2. Type: help"
echo "  3. Press Enter"
echo "  4. Come back here and I'll give you the token extraction code"
echo ""
echo "If NO (nothing happened):"
echo "  Let me know and we'll try the GUI version instead"
echo ""
echo "═══════════════════════════════════════════════════════════════"

