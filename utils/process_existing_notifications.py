#!/usr/bin/env python3
"""
Process existing Discord notifications from macOS notification system.
Only processes messages from the 3 monitored channels.
"""

import os
import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from discord_intent_detector import process_discord_message
from discord_db import get_conn

ET = ZoneInfo("America/New_York")

# Your 3 monitored channels
MONITORED_CHANNELS = {
    545047039084593163: "stock-alerts",
    981926799212679248: "day-trade-alerts",
    661023267439509536: "swings"
}

def find_notification_databases():
    """Find macOS notification database locations."""
    possible_paths = [
        Path.home() / "Library/Application Support/NotificationCenter/db2/db",
        Path.home() / "Library/Application Support/NotificationCenter/db/db",
        Path.home() / "Library/Caches/com.apple.notificationcenterui/db",
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return None


def extract_channel_id_from_notification(content: str, identifier: str) -> int:
    """
    Extract Discord channel ID from notification content or identifier.

    Discord notifications often include channel URL or ID in metadata.
    """
    # Pattern 1: URL in content
    url_pattern = r'discord\.com/channels/\d+/(\d+)'
    match = re.search(url_pattern, content)
    if match:
        return int(match.group(1))

    # Pattern 2: Channel ID in identifier
    if identifier:
        id_match = re.search(r'(\d{17,19})', identifier)
        if id_match:
            channel_id = int(id_match.group(1))
            if channel_id in MONITORED_CHANNELS:
                return channel_id

    return None


def process_notifications_from_db(db_path: str):
    """
    Read Discord notifications from macOS notification database.
    Only process notifications from monitored channels.
    """
    print(f"\n📱 Reading notifications from: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get Discord notifications
        # Note: Schema varies by macOS version
        cursor.execute("""
            SELECT DISTINCT
                identifier,
                bundleid,
                data
            FROM record
            WHERE bundleid LIKE '%discord%'
            ORDER BY date DESC
            LIMIT 200
        """)

        rows = cursor.fetchall()
        conn.close()

        print(f"  Found {len(rows)} Discord notifications")

        processed = 0
        skipped = 0

        for identifier, bundleid, data_blob in rows:
            try:
                # Extract text from data blob
                if isinstance(data_blob, bytes):
                    data_str = data_blob.decode('utf-8', errors='ignore')
                else:
                    data_str = str(data_blob)

                # Try to extract message content
                # Look for text patterns in notification data
                content_match = re.search(r'"body":\s*"([^"]+)"', data_str)
                if not content_match:
                    content_match = re.search(r'<string>([^<]{20,})</string>', data_str)

                if not content_match:
                    continue

                content = content_match.group(1)

                # Extract channel ID
                channel_id = extract_channel_id_from_notification(content, identifier)

                if not channel_id or channel_id not in MONITORED_CHANNELS:
                    skipped += 1
                    continue

                print(f"\n  ✓ Found message in {MONITORED_CHANNELS[channel_id]}:")
                print(f"    {content[:80]}...")

                # Process the notification
                # Note: We don't have full Discord message data, so using placeholders
                process_discord_message(
                    message_id=hash(content) % (10 ** 15),  # Generate pseudo-ID
                    author_id=0,  # Unknown
                    author_name="HistoricalMessage",
                    content=content,
                    timestamp=datetime.now(ET),
                    channel_id=channel_id,
                    has_chart=False
                )

                processed += 1

            except Exception as e:
                print(f"  ⚠ Error processing notification: {e}")
                continue

        print(f"\n  📊 Summary:")
        print(f"     Processed: {processed} messages")
        print(f"     Skipped: {skipped} (not from monitored channels)")

    except Exception as e:
        print(f"  ✗ Error reading notification database: {e}")


def process_manual_test_data():
    """
    Process the example messages from your documentation for testing.
    """
    print("\n📝 Processing example trade sequence...")

    # Your example from day-trade-alerts
    messages = [
        {
            "content": "ES short here @everyone\nDOL is fake news pump from Monday premarket",
            "author": "TraderExample",
            "author_id": 999999999,
            "channel_id": 981926799212679248,  # day-trade-alerts
            "timestamp": datetime.now(ET)
        },
        {
            "content": "Up $600 per con here at low hanging fruit (1:1). Take it if you wish @everyone\nI want to see SPX hit 6500",
            "author": "TraderExample",
            "author_id": 999999999,
            "channel_id": 981926799212679248,
            "timestamp": datetime.now(ET)
        },
        {
            "content": "$950 per con here. SPX is almost at 6500. Taking it off here. Great trade @everyone",
            "author": "TraderExample",
            "author_id": 999999999,
            "channel_id": 981926799212679248,
            "timestamp": datetime.now(ET)
        }
    ]

    for i, msg in enumerate(messages, 1):
        print(f"\n  Message {i}:")
        print(f"    {msg['content'][:60]}...")

        process_discord_message(
            message_id=1000 + i,
            author_id=msg['author_id'],
            author_name=msg['author'],
            content=msg['content'],
            timestamp=msg['timestamp'],
            channel_id=msg['channel_id'],
            has_chart=False
        )


if __name__ == "__main__":
    import sys

    print("="*80)
    print("  DISCORD NOTIFICATION PROCESSOR")
    print("="*80)
    print(f"\nMonitored channels:")
    for ch_id, name in MONITORED_CHANNELS.items():
        print(f"  • {name} (ID: {ch_id})")

    if "--test" in sys.argv:
        # Process example data
        process_manual_test_data()
    else:
        # Try to find and process actual notifications
        db_path = find_notification_databases()

        if db_path:
            process_notifications_from_db(db_path)
        else:
            print("\n⚠ macOS notification database not found")
            print("  This may require Full Disk Access for Python")
            print("\nProcessing example data instead:")
            process_manual_test_data()

    # Show database status
    print("\n" + "="*80)
    print("  DATABASE STATUS AFTER PROCESSING")
    print("="*80)

    conn = get_conn()
    cur = conn.cursor()

    tables_to_check = [
        'discord_channels',
        'discord_messages',
        'discord_trade_lifecycle',
        'message_intents',
        'intent_patterns'
    ]

    for table in tables_to_check:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table:<30} {count:>5} rows")

    conn.close()

    print("\n✅ Processing complete!")
    print("\nNext steps:")
    print("  • View trades: SELECT * FROM discord_trade_lifecycle;")
    print("  • View intents: SELECT * FROM message_intents;")
    print("  • Test agent: python3 discord_db.py --test")
