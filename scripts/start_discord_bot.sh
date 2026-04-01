#!/bin/bash
# Start Discord bot monitor

# Go to project directory
cd "$(dirname "$0")"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo ""
    echo "❌ Error: .env file not found"
    echo ""
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# Discord Bot Configuration
DISCORD_BOT_TOKEN=PASTE_YOUR_TOKEN_HERE
EOF
    echo "✅ Created .env file"
    echo ""
    echo "Please edit .env and add your Discord bot token, then run again."
    echo ""
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run bot
echo ""
echo "Starting Discord bot monitor..."
echo ""
python3 discord_bot_monitor.py
