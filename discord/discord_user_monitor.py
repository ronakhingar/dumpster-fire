#!/usr/bin/env python3
"""
Discord User Token Monitor - Real-time Signal Monitor

Monitors Discord channels using your personal user token.
Runs every 2 minutes from 9 AM - 4 PM EST.

⚠️ NOTE: This uses your personal Discord account token.
   - Read-only monitoring only
   - Does not send messages or interact
   - For personal use only
"""

import discord
from discord.ext import tasks
import os
import json
from datetime import datetime, time
from pathlib import Path
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")

# Channels to monitor (exact names from The Traveling Trader)
MONITORED_CHANNELS = [
    "🚨┃stock-alerts",
    "🎯┃day-trade-alerts",
    "🏌🏻┃swings"
]

# Simplified names for output files (without emojis)
CHANNEL_SIMPLE_NAMES = {
    "🚨┃stock-alerts": "stock-alerts",
    "🎯┃day-trade-alerts": "day-trade-alerts",
    "🏌🏻┃swings": "swings"
}

# Market hours (EST)
MARKET_OPEN = time(9, 0)   # 9:00 AM EST
MARKET_CLOSE = time(16, 0)  # 4:00 PM EST

# Output directory
OUTPUT_DIR = Path(__file__).parent / "discord_history" / "realtime"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Track last message ID per channel
LAST_MESSAGE_IDS = {}

# ─── Discord Client Setup ─────────────────────────────────────────────────────

class UserClient(discord.Client):
    def __init__(self):
        print("Initializing client...")
        super().__init__()

    async def on_ready(self):
        """Called when user client successfully connects."""
        print()
        print("="*70)
        print("  DISCORD USER MONITOR - STARTED")
        print("="*70)
        print(f"  Logged in as: {self.user.name}")
        print(f"  User ID: {self.user.id}")
        print(f"  Connected to {len(self.guilds)} server(s)")
        print()

        # List all available channels and monitored ones
        print(f"  📡 Available Servers & Channels:")
        found_monitored = False
        for guild in self.guilds:
            print(f"     Server: {guild.name}")
            monitored_in_guild = []
            all_channels = []
            for channel in guild.text_channels:
                all_channels.append(channel.name)
                if channel.name in MONITORED_CHANNELS:
                    monitored_in_guild.append(channel.name)
                    found_monitored = True

            if monitored_in_guild:
                for ch in monitored_in_guild:
                    print(f"       ✅ #{ch} (MONITORING)")

            # Show first few channels for reference
            other_channels = [ch for ch in all_channels[:5] if ch not in monitored_in_guild]
            if other_channels:
                print(f"       ℹ️  Other channels: {', '.join(['#' + ch for ch in other_channels])}")

        if not found_monitored:
            print()
            print(f"  ⚠️  WARNING: None of the target channels found!")
            print(f"     Looking for: {', '.join(['#' + ch for ch in MONITORED_CHANNELS])}")
            print(f"     Check channel names are exact matches.")

        print()
        print(f"  ⏰ Market Hours: {MARKET_OPEN.strftime('%I:%M %p')} - {MARKET_CLOSE.strftime('%I:%M %p')} EST")
        print(f"  🔄 Check Interval: 2 minutes")
        print(f"  💾 Output: {OUTPUT_DIR}")
        print()
        print("="*70)
        print()

        # Start periodic task
        if not check_channels.is_running():
            check_channels.start()

    async def on_message(self, message):
        """Real-time message handler."""

        # Ignore own messages
        if message.author.id == self.user.id:
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


client = UserClient()


def is_market_hours() -> bool:
    """Check if current time is during market hours."""
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)

    # Skip weekends
    if now.weekday() >= 5:
        return False

    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


async def save_message(message: discord.Message):
    """Save message to JSONL file."""

    channel_name = message.channel.name
    # Use simplified name for output files
    simple_name = CHANNEL_SIMPLE_NAMES.get(channel_name, channel_name)
    output_file = OUTPUT_DIR / f"{simple_name}.jsonl"

    # Build message data
    msg_data = {
        "id": str(message.id),
        "timestamp": message.created_at.isoformat(),
        "author": message.author.name,
        "author_id": str(message.author.id),
        "content": message.content,
        "channel": simple_name,  # Use simplified name
        "attachments": []
    }

    # Download attachments
    if message.attachments:
        attachments_dir = OUTPUT_DIR / f"{simple_name}_files"
        attachments_dir.mkdir(exist_ok=True)

        for attachment in message.attachments:
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
    """Check monitored channels every 2 minutes."""

    if not is_market_hours():
        print(f"  💤 Outside market hours - skipping scan")
        return

    print(f"\n🔍 Scanning channels at {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}")

    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.name in MONITORED_CHANNELS:
                try:
                    last_id = LAST_MESSAGE_IDS.get(channel.id, None)

                    # Fetch new messages
                    if last_id:
                        messages = [msg async for msg in channel.history(limit=100, after=discord.Object(id=last_id))]
                    else:
                        messages = [msg async for msg in channel.history(limit=10)]

                    messages.reverse()

                    if messages:
                        print(f"  📢 #{channel.name}: {len(messages)} new message(s)")

                        for message in messages:
                            await save_message(message)
                            LAST_MESSAGE_IDS[channel.id] = message.id

                except discord.Forbidden:
                    print(f"  ⚠ No access to #{channel.name}")
                except Exception as e:
                    print(f"  ⚠ Error reading #{channel.name}: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not DISCORD_USER_TOKEN or DISCORD_USER_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        print("❌ Error: Discord user token not configured")
        print()
        print("Add your Discord user token to .env file:")
        print("  DISCORD_BOT_TOKEN=your_user_token_here")
        print()
        return

    try:
        # Run with user token
        client.run(DISCORD_USER_TOKEN)
    except discord.LoginFailure:
        print("❌ Error: Invalid Discord user token")
        print()
        print("Make sure you're using your USER token, not a bot token.")
        print("User tokens look like: MTM0MT...long string...xyz")
        print()
    except KeyboardInterrupt:
        print("\n\n  🛑 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
