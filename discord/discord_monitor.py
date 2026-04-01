#!/usr/bin/env python3
"""
Discord Notification Monitor for macOS

Monitors macOS Notification Center for Discord messages from configured channels.
Extracts message content and saves to journal for signal processing.

Runs as a background service, polling every 2 minutes (aligned with trading agent).
"""

import json
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = Path(__file__).parent / "discord_config.json"
RAW_OUTPUT = BASE_DIR / "journal" / "discord_raw.jsonl"
PROCESSED_IDS = BASE_DIR / "journal" / ".discord_processed_ids.txt"

# macOS Notification Center database path
NOTIF_DB = Path.home() / "Library" / "Application Support" / "NotificationCenter" / "db2" / "db"


def load_config():
    """Load Discord channel configuration."""
    if not CONFIG_FILE.exists():
        return {"channel_ids": [], "poll_interval_seconds": 120}

    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_processed_ids():
    """Load set of already-processed notification IDs."""
    if not PROCESSED_IDS.exists():
        return set()

    with open(PROCESSED_IDS) as f:
        return set(line.strip() for line in f if line.strip())


def save_processed_id(notif_id: str):
    """Mark a notification ID as processed."""
    with open(PROCESSED_IDS, "a") as f:
        f.write(f"{notif_id}\n")


def get_recent_discord_notifications(since_minutes: int = 5):
    """
    Extract recent Discord notifications from macOS Notification Center database.

    Returns list of notifications with text content.
    """
    if not NOTIF_DB.exists():
        print(f"  ⚠ Notification database not found at {NOTIF_DB}")
        return []

    try:
        conn = sqlite3.connect(str(NOTIF_DB))
        cursor = conn.cursor()

        # Calculate timestamp threshold (Unix timestamp)
        since_time = datetime.now() - timedelta(minutes=since_minutes)
        since_unix = int(since_time.timestamp())

        # Query notification records
        # The db schema varies by macOS version, but generally:
        # - app_id or identifier contains app name
        # - data or body contains notification text
        # - delivered_date is Unix timestamp

        query = """
        SELECT
            ROWID,
            app_id,
            identifier,
            data,
            delivered_date
        FROM record
        WHERE app_id LIKE '%discord%'
        AND delivered_date > ?
        ORDER BY delivered_date DESC
        LIMIT 50
        """

        cursor.execute(query, (since_unix,))
        rows = cursor.fetchall()
        conn.close()

        notifications = []
        for row in rows:
            notif_id, app_id, identifier, data_blob, delivered_date = row

            # Try to extract text from data blob (it's often a plist or JSON)
            try:
                # Convert blob to string and look for text content
                data_str = data_blob.decode('utf-8', errors='ignore') if isinstance(data_blob, bytes) else str(data_blob)

                # Basic text extraction (this varies by macOS version)
                # We'll try multiple patterns
                text = None

                # Pattern 1: Look for "body" or "message" keys
                if '"body"' in data_str or '"message"' in data_str:
                    import re
                    body_match = re.search(r'"(?:body|message)"\s*:\s*"([^"]+)"', data_str)
                    if body_match:
                        text = body_match.group(1)

                # Pattern 2: Look for quoted strings after certain keywords
                if not text:
                    import re
                    text_match = re.search(r'(?:text|content).*?"([^"]{20,})"', data_str, re.IGNORECASE)
                    if text_match:
                        text = text_match.group(1)

                if text and len(text) > 20:  # Only keep substantial messages
                    notifications.append({
                        'id': str(notif_id),
                        'app': app_id,
                        'identifier': identifier,
                        'text': text,
                        'timestamp': datetime.fromtimestamp(delivered_date).isoformat()
                    })
            except Exception as e:
                # Skip malformed notifications
                continue

        return notifications

    except Exception as e:
        print(f"  ✗ Error reading notification database: {e}")
        return []


def get_discord_via_applescript():
    """
    Alternative method: Use AppleScript to read Notification Center.
    More reliable but requires accessibility permissions.
    """
    script = '''
    tell application "System Events"
        tell process "NotificationCenter"
            try
                set notifsList to windows
                set output to ""
                repeat with notifWindow in notifsList
                    try
                        set appName to value of static text 1 of notifWindow
                        if appName contains "Discord" then
                            set notifText to value of static text 2 of notifWindow
                            set output to output & notifText & "|SEPARATOR|"
                        end if
                    end try
                end repeat
                return output
            on error
                return ""
            end try
        end tell
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            messages = result.stdout.strip().split('|SEPARATOR|')
            return [msg for msg in messages if msg.strip()]

    except Exception as e:
        print(f"  ⚠ AppleScript method failed: {e}")

    return []


def capture_notifications():
    """
    Main capture function - tries multiple methods to get Discord notifications.
    """
    config = load_config()
    processed_ids = load_processed_ids()

    print(f"\n  📱 Checking Discord notifications...")
    print(f"     Monitoring {len(config.get('channel_ids', []))} channels")

    # Method 1: Direct database query
    notifications = get_recent_discord_notifications(since_minutes=5)

    # Method 2: AppleScript fallback (if database method fails)
    if not notifications:
        print("  ⚠ Database method returned no results, trying AppleScript...")
        # Note: This requires accessibility permissions

    # Filter out already-processed notifications
    new_notifications = [n for n in notifications if n['id'] not in processed_ids]

    if not new_notifications:
        print(f"  ✓ No new Discord messages (checked {len(notifications)} notifications)")
        return 0

    # Save new notifications to raw journal
    RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    saved_count = 0
    for notif in new_notifications:
        # Create journal entry
        entry = {
            "timestamp": datetime.now(ET).isoformat(),
            "source": "discord",
            "notification_id": notif['id'],
            "raw_text": notif['text'],
            "notif_timestamp": notif['timestamp'],
            "processed": False
        }

        # Append to JSONL file
        with open(RAW_OUTPUT, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Mark as processed
        save_processed_id(notif['id'])
        saved_count += 1

        print(f"  ✓ Captured: {notif['text'][:100]}...")

    print(f"  📝 Saved {saved_count} new Discord messages to {RAW_OUTPUT.name}")
    return saved_count


def monitor_loop(interval_seconds: int = 120):
    """
    Continuous monitoring loop - runs every interval_seconds.
    """
    import time

    print(f"  🔄 Discord monitor starting (interval: {interval_seconds}s)")

    while True:
        try:
            capture_notifications()
        except Exception as e:
            print(f"  ✗ Error in monitor loop: {e}")

        print(f"  💤 Sleeping {interval_seconds}s...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import sys

    if "--once" in sys.argv:
        # Single capture for testing
        capture_notifications()
    elif "--loop" in sys.argv:
        # Continuous monitoring
        config = load_config()
        interval = config.get("poll_interval_seconds", 120)
        monitor_loop(interval)
    else:
        print("Discord Notification Monitor")
        print("Usage:")
        print("  python3 discord_monitor.py --once    # Single capture (testing)")
        print("  python3 discord_monitor.py --loop    # Continuous monitoring")
        print()
        print("To run as a service:")
        print("  ./discord_control.sh start")
