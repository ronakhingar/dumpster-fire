#!/usr/bin/env python3
"""
Discord HTML Export Converter

Converts Discord export JSON to signal format for backtesting.
Filters for trading signals and identifies stock chart images.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

ET = ZoneInfo("America/New_York")

BASE_DIR = Path(__file__).parent
EXPORT_FILE = BASE_DIR / "discord_history" / "DISCORD_.html"
IMAGE_DIR = BASE_DIR / "discord_history" / "DISCORD_.html_Files"
OUTPUT_FILE = BASE_DIR / "journal" / "discord_signals_history.jsonl"
CHARTS_LIST = BASE_DIR / "discord_history" / "stock_charts.txt"

# Trading keywords to identify signals
SIGNAL_KEYWORDS = [
    r'\b(SPY|QQQ)\b',  # Symbols
    r'\$\d+',  # Price levels
    r'\b(support|resistance|target|entry|stop)\b',  # Levels
    r'\b(bullish|bearish|long|short|calls?|puts?)\b',  # Direction
    r'\b(bounce|breakdown|breakout|rejection)\b',  # Action
]

# Image size threshold for stock charts (in bytes)
CHART_SIZE_MIN = 100_000  # 100KB+ likely charts
CHART_SIZE_MAX = 5_000_000  # 5MB max reasonable chart size


def is_trading_signal(text: str) -> bool:
    """Check if message contains trading signal keywords."""
    if not text or len(text) < 20:
        return False

    text_lower = text.lower()

    # Must contain at least one keyword from each category
    matches = sum(1 for pattern in SIGNAL_KEYWORDS if re.search(pattern, text_lower, re.IGNORECASE))

    return matches >= 2  # At least 2 keyword matches


def is_likely_stock_chart(attachment: dict) -> bool:
    """Check if attachment is likely a stock chart vs emoji/avatar."""
    file_size = attachment.get('fileSizeBytes', 0)
    file_name = attachment.get('fileName', '')

    # Size-based filtering
    if file_size < CHART_SIZE_MIN or file_size > CHART_SIZE_MAX:
        return False

    # File name patterns
    if any(x in file_name.lower() for x in ['screenshot', 'image', 'chart', 'spy', 'qqq']):
        return True

    # PNG files in size range are likely charts
    if file_name.lower().endswith('.png') and file_size > 150_000:
        return True

    return False


def convert_to_signal(message: dict) -> Optional[dict]:
    """Convert Discord message to signal format."""
    content = message.get('content', '').strip()

    if not is_trading_signal(content):
        return None

    timestamp_str = message.get('timestamp', '')
    author = message.get('author', {}).get('name', 'unknown')
    message_id = message.get('id', '')

    # Parse timestamp (format: "2026-03-28T01:05:53.104+05:30")
    try:
        dt = datetime.fromisoformat(timestamp_str)
        dt_et = dt.astimezone(ET)
    except (ValueError, AttributeError):
        return None

    # Check for attachments (potential charts)
    attachments = message.get('attachments', [])
    chart_images = [
        att['url'] for att in attachments
        if is_likely_stock_chart(att)
    ]

    signal = {
        "timestamp": dt_et.isoformat(),
        "source_timestamp": timestamp_str,
        "notification_id": f"history_{message_id}",
        "raw_text": content,
        "author": author,
        "message_id": message_id,
        "processed": False,
        "chart_images": chart_images  # For reference
    }

    return signal


def load_json_robust(file_path: Path) -> dict:
    """
    Load JSON file that may be incomplete.
    Try to salvage as much data as possible.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Try normal parsing first
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parse error at position {e.pos}")
        print(f"   Attempting to salvage partial data...")

        # Find the last complete message
        # Strategy: find last complete message object by searching backward
        lines = content.split('\n')

        # Try to find closing array bracket for messages
        for i in range(len(lines) - 1, -1, -1):
            if '"messages": [' in content[:i * 100]:  # Rough position
                # Try parsing up to this point with manual closure
                partial = content[:i * 100]

                # Add closing brackets to make valid JSON
                # Close messages array and root object
                test_content = partial.rstrip().rstrip(',') + '\n]\n}'

                try:
                    data = json.loads(test_content)
                    print(f"   ✅ Recovered {len(data.get('messages', []))} messages")
                    return data
                except json.JSONDecodeError:
                    continue

        # If all else fails, extract messages manually
        print("   ⚠️  Attempting manual message extraction...")
        messages = []

        # Find all complete message objects
        message_pattern = r'\{\s*"id":\s*"(\d+)".*?"content":\s*"([^"]*)".*?"timestamp":\s*"([^"]*)"'
        for match in re.finditer(message_pattern, content, re.DOTALL):
            msg_id, msg_content, msg_timestamp = match.groups()
            messages.append({
                "id": msg_id,
                "content": msg_content,
                "timestamp": msg_timestamp,
                "author": {"name": "unknown"}
            })

        print(f"   ✅ Manually extracted {len(messages)} messages")
        return {"messages": messages}


def main():
    """Main entry point."""
    print(f"\n{'='*80}")
    print(f"  DISCORD EXPORT CONVERTER")
    print(f"{'='*80}\n")

    print(f"  Input: {EXPORT_FILE}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Charts: {CHARTS_LIST}\n")

    # Load JSON export
    print(f"  📥 Loading Discord export...")
    try:
        data = load_json_robust(EXPORT_FILE)
    except Exception as e:
        print(f"  ❌ Error loading JSON: {e}")
        return

    messages = data.get('messages', [])
    print(f"  ✅ Loaded {len(messages)} messages\n")

    # Convert to signals
    print(f"  🔍 Filtering for trading signals...")
    signals = []
    chart_files = []

    for msg in messages:
        signal = convert_to_signal(msg)
        if signal:
            signals.append(signal)

            # Track chart images
            if signal.get('chart_images'):
                for img in signal['chart_images']:
                    chart_files.append(f"{signal['timestamp']}: {img}")

    print(f"  ✅ Found {len(signals)} trading signals\n")

    # Save signals
    if signals:
        print(f"  💾 Saving signals to {OUTPUT_FILE}...")
        OUTPUT_FILE.parent.mkdir(exist_ok=True)

        with open(OUTPUT_FILE, 'a') as f:  # Append mode
            for signal in signals:
                # Remove chart_images before saving (not needed in signal format)
                chart_imgs = signal.pop('chart_images', [])
                f.write(json.dumps(signal) + '\n')

        print(f"  ✅ Saved {len(signals)} signals\n")

    # Save chart file list
    if chart_files:
        print(f"  📊 Saving chart file list to {CHARTS_LIST}...")
        with open(CHARTS_LIST, 'w') as f:
            f.write('\n'.join(chart_files))
        print(f"  ✅ Saved {len(chart_files)} chart references\n")

    # Summary
    print(f"{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}\n")
    print(f"  Total messages: {len(messages)}")
    print(f"  Trading signals: {len(signals)}")
    print(f"  Chart images: {len(chart_files)}")

    if signals:
        # Show sample signals
        print(f"\n  Sample signals:")
        for signal in signals[:5]:
            dt = datetime.fromisoformat(signal['timestamp'])
            text = signal['raw_text'][:100] + ('...' if len(signal['raw_text']) > 100 else '')
            print(f"    • {dt.strftime('%Y-%m-%d %H:%M')} - {text}")

    print(f"\n{'='*80}\n")
    print(f"  ✅ Conversion complete!")
    print(f"\n  Next steps:")
    print(f"    1. Review signals: cat {OUTPUT_FILE}")
    print(f"    2. Process with extractor: python3 discord_signal_extractor.py")
    print(f"    3. Run backtest: python3 backtest.py 2026-03-26")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
