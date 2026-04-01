#!/usr/bin/env python3
"""
Discord History Fetcher

Fetches message history from Discord channels using your personal token.
No bot required - uses your own Discord session.

Usage:
    1. Get your Discord token (see instructions below)
    2. Run: python3 discord_history_fetcher.py YOUR_TOKEN
    3. Script fetches history from all configured channels
"""

import sys
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Load channel IDs from config
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "discord_config.json"

# Output files
OUTPUT_DIR = BASE_DIR / "discord_history"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_channel_config():
    """Load channel IDs from discord_config.json"""
    if not CONFIG_FILE.exists():
        print(f"❌ Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    return config.get("monitored_channels", [])


def fetch_messages(channel_id: str, token: str, limit: int = 100, before: str = None) -> list:
    """
    Fetch messages from a Discord channel.

    Args:
        channel_id: Discord channel ID
        token: Your Discord authorization token
        limit: Number of messages per batch (max 100)
        before: Message ID to fetch messages before (for pagination)

    Returns:
        List of message objects
    """
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    params = {"limit": limit}

    if before:
        params["before"] = before

    headers = {
        "authorization": token,
        "user-agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 401:
            print(f"❌ Invalid token. Please check your Discord token.")
            sys.exit(1)

        if response.status_code == 403:
            print(f"❌ Access denied to channel {channel_id}. Check permissions.")
            return []

        if response.status_code == 429:
            # Rate limited
            retry_after = response.json().get("retry_after", 5)
            print(f"⚠️  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            return fetch_messages(channel_id, token, limit, before)

        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        print(f"❌ Error fetching messages: {e}")
        return []


def fetch_channel_history(channel_id: str, channel_name: str, token: str, max_messages: int = 1000) -> list:
    """
    Fetch complete history from a channel.

    Args:
        channel_id: Discord channel ID
        channel_name: Human-readable channel name
        token: Discord authorization token
        max_messages: Maximum messages to fetch

    Returns:
        List of all fetched messages
    """
    print(f"\n📥 Fetching history from #{channel_name} ({channel_id})...")

    all_messages = []
    last_id = None
    batch_num = 0

    while len(all_messages) < max_messages:
        batch_num += 1
        print(f"   Batch {batch_num}: ", end="", flush=True)

        batch = fetch_messages(channel_id, token, limit=100, before=last_id)

        if not batch or len(batch) == 0:
            print("No more messages")
            break

        all_messages.extend(batch)
        last_id = batch[-1]["id"]

        print(f"Fetched {len(batch)} messages (total: {len(all_messages)})")

        # Rate limit: wait between requests
        time.sleep(1)

    print(f"✓ Fetched {len(all_messages)} messages from #{channel_name}")

    return all_messages


def save_raw_history(messages: list, channel_name: str, channel_id: str):
    """Save raw Discord messages to JSON file."""
    output_file = OUTPUT_DIR / f"{channel_name}_{channel_id}_raw.json"

    with open(output_file, "w") as f:
        json.dump(messages, f, indent=2)

    print(f"   Saved to: {output_file}")


def convert_to_signals(messages: list) -> list:
    """
    Convert Discord messages to signal format.

    Filters for messages that look like trading signals.
    """
    signals = []

    for msg in messages:
        content = msg.get("content", "").strip()
        timestamp = msg.get("timestamp", "")

        # Skip empty messages
        if not content or len(content) < 20:
            continue

        # Look for signal keywords
        signal_keywords = ["spy", "qqq", "target", "support", "resistance",
                          "bullish", "bearish", "$", "entry", "stop"]

        content_lower = content.lower()
        if not any(keyword in content_lower for keyword in signal_keywords):
            continue

        # Create signal entry
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            dt_et = dt.astimezone(ET)

            signal = {
                "timestamp": dt_et.isoformat(),
                "source_timestamp": timestamp,
                "notification_id": f"history_{msg['id']}",
                "raw_text": content,
                "author": msg.get("author", {}).get("username", "unknown"),
                "message_id": msg["id"],
                "processed": False
            }

            signals.append(signal)

        except (ValueError, KeyError) as e:
            continue

    return signals


def save_as_signals(messages: list, channel_name: str):
    """
    Convert messages to signal format and save.

    Saves in format compatible with discord_signal_extractor.py
    """
    signals = convert_to_signals(messages)

    if not signals:
        print(f"   ⚠️  No signals found in #{channel_name}")
        return

    # Save to discord_raw.jsonl format
    output_file = OUTPUT_DIR / f"{channel_name}_signals.jsonl"

    with open(output_file, "w") as f:
        for signal in signals:
            f.write(json.dumps(signal) + "\n")

    print(f"   ✓ Converted {len(signals)} messages to signals: {output_file}")


def print_instructions():
    """Print instructions for getting Discord token."""
    print("""
═══════════════════════════════════════════════════════════════
  HOW TO GET YOUR DISCORD TOKEN
═══════════════════════════════════════════════════════════════

1. Open Discord desktop app

2. Press: Cmd + Option + I  (opens DevTools)

3. Click "Network" tab

4. In Discord, click any channel

5. In Network tab:
   - Filter: type "api" in the filter box
   - Click any request that appears
   - Click "Headers" tab
   - Scroll to "Request Headers"
   - Find "authorization:" line
   - Copy the value (long string starting with "mfa." or similar)

6. Run this script:
   python3 discord_history_fetcher.py YOUR_TOKEN_HERE

7. Script will fetch history from all 3 configured channels

═══════════════════════════════════════════════════════════════

IMPORTANT:
- Keep your token private (like a password)
- Token expires when you log out of Discord
- This uses YOUR Discord session (not a bot)
- Respects Discord rate limits

═══════════════════════════════════════════════════════════════
""")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("❌ Missing Discord token")
        print_instructions()
        sys.exit(1)

    token = sys.argv[1]

    # Optional: limit number of messages
    max_messages = 1000
    if len(sys.argv) > 2:
        max_messages = int(sys.argv[2])

    print(f"""
═══════════════════════════════════════════════════════════════
  DISCORD HISTORY FETCHER
═══════════════════════════════════════════════════════════════

  Fetching up to {max_messages} messages per channel
  Output directory: {OUTPUT_DIR}

""")

    # Load channel configuration
    channels = load_channel_config()

    if not channels:
        print("❌ No channels configured in discord_config.json")
        sys.exit(1)

    print(f"📋 Found {len(channels)} configured channels:")
    for ch in channels:
        print(f"   • #{ch['name']} (priority: {ch.get('priority', 'normal')})")

    # Fetch history from each channel
    all_results = {}

    for channel in channels:
        channel_id = channel['url'].split('/')[-1]
        channel_name = channel['name']

        messages = fetch_channel_history(channel_id, channel_name, token, max_messages)

        if messages:
            # Save raw messages
            save_raw_history(messages, channel_name, channel_id)

            # Convert to signal format
            save_as_signals(messages, channel_name)

            all_results[channel_name] = len(messages)

    # Summary
    print(f"""
═══════════════════════════════════════════════════════════════
  SUMMARY
═══════════════════════════════════════════════════════════════
""")

    total = 0
    for channel_name, count in all_results.items():
        print(f"  #{channel_name}: {count} messages")
        total += count

    print(f"""
  Total: {total} messages fetched

  Output files in: {OUTPUT_DIR}/

═══════════════════════════════════════════════════════════════
  NEXT STEPS
═══════════════════════════════════════════════════════════════

1. Review signal files:
   cat discord_history/*_signals.jsonl

2. Process signals with extractor:
   python3 discord_signal_extractor.py

3. Import to history for backtesting:
   cat discord_history/*_signals.jsonl >> journal/discord_signals_history.jsonl

4. Run backtests with historical signals:
   python3 backtest.py 2024-03-26

═══════════════════════════════════════════════════════════════
""")


if __name__ == "__main__":
    main()
