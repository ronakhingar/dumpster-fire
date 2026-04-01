#!/usr/bin/env python3
"""
Discord Bot - Real-time Signal Monitor

Monitors Discord channels for trading signals during market hours.
Runs every 2 minutes from 9 AM - 4 PM EST.

Usage:
    1. Add your token to .env file
    2. Run: python3 discord_bot_monitor.py
"""

import discord
from discord.ext import tasks
import os
import json
from datetime import datetime, time
from pathlib import Path
import pytz
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")

# Channels to monitor
MONITORED_CHANNELS = [
    "stock-alerts",
    "day-trade-alerts",
    "swings"
]

# Market hours (EST)
MARKET_OPEN = time(9, 0)   # 9:00 AM EST
MARKET_CLOSE = time(16, 0)  # 4:00 PM EST

# Output directory
OUTPUT_DIR = Path(__file__).parent / "discord_history" / "realtime"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Track last message ID per channel to avoid duplicates
LAST_MESSAGE_IDS = {}

# ─── Discord Bot Setup ────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)


def is_market_hours() -> bool:
    """Check if current time is during market hours (9 AM - 4 PM EST)."""
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)

    # Skip weekends
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


async def save_message(message: discord.Message):
    """Save message to JSONL file."""

    # Determine output file based on channel
    channel_name = message.channel.name
    output_file = OUTPUT_DIR / f"{channel_name}.jsonl"

    # Build message data
    msg_data = {
        "id": str(message.id),
        "timestamp": message.created_at.isoformat(),
        "author": message.author.name,
        "author_id": str(message.author.id),
        "content": message.content,
        "channel": channel_name,
        "attachments": []
    }

    # Download attachments if present
    if message.attachments:
        attachments_dir = OUTPUT_DIR / f"{channel_name}_files"
        attachments_dir.mkdir(exist_ok=True)

        for attachment in message.attachments:
            # Only save images
            if any(attachment.filename.lower().endswith(ext)
                   for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):

                file_path = attachments_dir / f"{message.id}_{attachment.filename}"

                try:
                    await attachment.save(file_path)

                    msg_data["attachments"].append({
                        "filename": attachment.filename,
                        "url": attachment.url,
                        "local_path": str(file_path)
                    })

                    print(f"    📎 Saved: {attachment.filename}")
                except Exception as e:
                    print(f"    ⚠ Failed to save {attachment.filename}: {e}")

    # Append to JSONL
    with open(output_file, 'a') as f:
        f.write(json.dumps(msg_data) + '\n')

    print(f"  ✅ Saved message {message.id} to {output_file.name}")


@tasks.loop(minutes=2)
async def check_channels():
    """Check monitored channels for new messages every 2 minutes."""

    if not is_market_hours():
        print(f"  💤 Outside market hours - skipping scan")
        return

    print(f"\n🔍 Scanning channels at {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}")

    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.name in MONITORED_CHANNELS:

                try:
                    # Get last message ID we've seen
                    last_id = LAST_MESSAGE_IDS.get(channel.id, None)

                    # Fetch messages after last seen ID
                    if last_id:
                        messages = [msg async for msg in channel.history(limit=100, after=discord.Object(id=last_id))]
                    else:
                        # First run - get last 10 messages
                        messages = [msg async for msg in channel.history(limit=10)]

                    messages.reverse()  # Process oldest first

                    if messages:
                        print(f"  📢 #{channel.name}: {len(messages)} new message(s)")

                        for message in messages:
                            await save_message(message)
                            LAST_MESSAGE_IDS[channel.id] = message.id

                except discord.Forbidden:
                    print(f"  ⚠ No access to #{channel.name}")
                except Exception as e:
                    print(f"  ⚠ Error reading #{channel.name}: {e}")


@client.event
async def on_ready():
    """Called when bot successfully connects."""
    print()
    print("="*70)
    print("  DISCORD BOT MONITOR - STARTED")
    print("="*70)
    print(f"  Bot User: {client.user.name}")
    print(f"  Connected to {len(client.guilds)} server(s)")
    print()

    # List monitored channels
    print(f"  📡 Monitoring channels:")
    for guild in client.guilds:
        print(f"     Server: {guild.name}")
        for channel in guild.text_channels:
            if channel.name in MONITORED_CHANNELS:
                print(f"       ✓ #{channel.name}")

    print()
    print(f"  ⏰ Market Hours: {MARKET_OPEN.strftime('%I:%M %p')} - {MARKET_CLOSE.strftime('%I:%M %p')} EST")
    print(f"  🔄 Check Interval: 2 minutes")
    print(f"  💾 Output: {OUTPUT_DIR}")
    print()
    print("="*70)
    print()

    # Start the periodic task
    if not check_channels.is_running():
        check_channels.start()


@client.event
async def on_message(message):
    """Real-time message handler (optional - for immediate capture)."""

    # Ignore bot's own messages
    if message.author == client.user:
        return

    # Only monitor specific channels
    if message.channel.name not in MONITORED_CHANNELS:
        return

    # Only during market hours
    if not is_market_hours():
        return

    print(f"\n  📩 Real-time message in #{message.channel.name}")
    await save_message(message)
    LAST_MESSAGE_IDS[message.channel.id] = message.id


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not DISCORD_USER_TOKEN or DISCORD_USER_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        print("❌ Error: DISCORD_USER_TOKEN not configured")
        print()
        print("Add your Discord bot token to the .env file:")
        print("  1. Open .env file in this directory")
        print("  2. Replace PASTE_YOUR_TOKEN_HERE with your actual token")
        print("  3. Save and run again")
        print()
        return

    try:
        client.run(DISCORD_USER_TOKEN)
    except discord.LoginFailure:
        print("❌ Error: Invalid Discord bot token")
    except KeyboardInterrupt:
        print("\n\n  🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
