#!/usr/bin/env python3
"""
Enhanced Discord Signal Extractor with Chart OCR Integration

Combines text extraction with chart image analysis for complete TP/SL data.

Process:
1. Extract signals from message text (existing)
2. Find associated chart images
3. Extract TP/SL from charts if available
4. Merge chart data with text signals
5. Fallback to text if no chart data
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

ET = ZoneInfo("America/New_York")

# Paths
BASE_DIR = Path(__file__).parent
RAW_INPUT = BASE_DIR / "journal" / "discord_raw.jsonl"
SIGNALS_OUTPUT = BASE_DIR / "journal" / "discord_signals.json"
SIGNALS_HISTORY = BASE_DIR / "journal" / "discord_signals_history.jsonl"
CHARTS_DIR = BASE_DIR / "discord_history" / "DISCORD_.html_Files"

# Import chart processor
try:
    from discord_chart_processor import extract_enhanced_chart_levels, DEPS_AVAILABLE as CHART_OCR_AVAILABLE
except ImportError:
    CHART_OCR_AVAILABLE = False


def is_trading_chart(file_path: Path) -> bool:
    """
    Filter out junk files (emojis, avatars, reactions).

    Trading charts are usually:
    - > 100KB (substantial size)
    - Screenshot or image- prefix
    - Not GIF/SVG
    """
    if file_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
        return False

    # Size filter
    try:
        size_kb = file_path.stat().st_size / 1024
        if size_kb < 100:  # Less than 100KB likely junk
            return False
    except:
        return False

    # Filename patterns (prefer screenshots and named images)
    name = file_path.name.lower()
    if any(junk in name for junk in ['emoji', 'avatar', 'reaction', 'icon']):
        return False

    return True


def find_chart_for_message(msg_timestamp: datetime) -> Optional[str]:
    """
    Find chart image associated with a message by timestamp proximity.

    Returns chart path or None.
    """
    if not CHARTS_DIR.exists():
        return None

    # Find charts created within 5 minutes of message
    best_match = None
    best_diff = float('inf')

    for chart_path in CHARTS_DIR.glob("*.png"):
        # Filter junk
        if not is_trading_chart(chart_path):
            continue

        try:
            chart_time = datetime.fromtimestamp(chart_path.stat().st_mtime, tz=ET)
            time_diff = abs((chart_time - msg_timestamp).total_seconds())

            if time_diff < 300 and time_diff < best_diff:  # Within 5 minutes
                best_match = str(chart_path)
                best_diff = time_diff
        except:
            continue

    return best_match


def extract_signals_with_chart(text: str, timestamp: str) -> dict:
    """
    Extract signals from text and enhance with chart data if available.

    Args:
        text: Message text
        timestamp: Message timestamp ISO format

    Returns:
        Enhanced signal dict with chart data
    """
    # First, use existing text-based extraction
    from discord_signal_extractor import extract_signals_pattern_matching

    signals = extract_signals_pattern_matching(text)

    # Try to find associated chart
    if not CHART_OCR_AVAILABLE:
        signals['chart_processed'] = False
        return signals

    try:
        msg_time = datetime.fromisoformat(timestamp)
        if msg_time.tzinfo is None:
            msg_time = msg_time.replace(tzinfo=ET)
    except:
        signals['chart_processed'] = False
        return signals

    chart_path = find_chart_for_message(msg_time)

    if not chart_path:
        signals['chart_processed'] = False
        return signals

    # Extract levels from chart
    print(f"    📊 Found chart: {Path(chart_path).name}")
    chart_levels = extract_enhanced_chart_levels(chart_path)

    if chart_levels.get('confidence', 0) < 0.3:
        print(f"       Low confidence ({chart_levels.get('confidence', 0):.2f}), using text only")
        signals['chart_processed'] = False
        return signals

    # Merge chart data with text signals
    signals['chart_processed'] = True
    signals['chart_path'] = chart_path
    signals['chart_confidence'] = chart_levels['confidence']

    # Enhance price targets with chart data
    for symbol in signals.get('symbols', []):
        if symbol not in signals['targets']:
            signals['targets'][symbol] = []

        # Add chart TP levels
        if chart_levels.get('take_profit'):
            signals['targets'][symbol].extend(chart_levels['take_profit'])

        # Add chart SL levels
        if chart_levels.get('stop_loss'):
            if 'stop_loss' not in signals:
                signals['stop_loss'] = {}
            signals['stop_loss'][symbol] = chart_levels['stop_loss']

    # Add all detected prices for context
    if chart_levels.get('all_prices'):
        signals['chart_price_range'] = {
            'min': min(chart_levels['all_prices']),
            'max': max(chart_levels['all_prices']),
            'levels': chart_levels['all_prices']
        }

    print(f"       ✓ Enhanced with chart data (conf: {chart_levels['confidence']:.2f})")
    print(f"         TP levels: {chart_levels.get('take_profit', [])}")
    print(f"         SL levels: {chart_levels.get('stop_loss', [])}")

    return signals


def process_raw_notifications_enhanced():
    """
    Enhanced notification processing with chart integration.
    """
    if not RAW_INPUT.exists():
        print(f"  ⚠ No raw notifications file at {RAW_INPUT}")
        return []

    # Read all raw entries
    raw_entries = []
    with open(RAW_INPUT) as f:
        for line in f:
            if line.strip():
                raw_entries.append(json.loads(line))

    # Filter unprocessed
    unprocessed = [e for e in raw_entries if not e.get("processed", False)]

    if not unprocessed:
        print(f"  ✓ No unprocessed notifications")
        return []

    print(f"  📊 Processing {len(unprocessed)} notifications with chart integration...")

    if CHART_OCR_AVAILABLE:
        print(f"  ✓ Chart OCR enabled")
    else:
        print(f"  ⚠ Chart OCR not available (text-only extraction)")

    processed_signals = []

    for entry in unprocessed:
        text = entry.get("raw_text", "")

        if len(text) < 50:  # Skip very short messages
            continue

        print(f"\n  Processing: {text[:80]}...")

        # Extract with chart enhancement
        timestamp = entry.get("timestamp", datetime.now(ET).isoformat())
        signals = extract_signals_with_chart(text, timestamp)

        # Create signal record
        signal_record = {
            "timestamp": datetime.now(ET).isoformat(),
            "source_timestamp": entry.get("timestamp"),
            "notification_id": entry.get("notification_id"),
            "raw_text": text,
            "signals": signals,
            "expires_at": (datetime.now(ET) + timedelta(hours=4)).isoformat(),
            "applied_to_trades": []
        }

        processed_signals.append(signal_record)

        # Save to history
        with open(SIGNALS_HISTORY, "a") as f:
            f.write(json.dumps(signal_record) + "\n")

        # Summary
        chart_marker = "📊" if signals.get('chart_processed') else "📝"
        print(f"  {chart_marker} Extracted: {signals.get('symbols', [])} - {signals.get('sentiment', 'neutral')}")

    # Mark as processed in raw file
    with open(RAW_INPUT, "w") as f:
        for entry in raw_entries:
            entry["processed"] = True
            f.write(json.dumps(entry) + "\n")

    return processed_signals


def update_active_signals(new_signals: list):
    """
    Update the active signals file that the agent reads.

    Removes expired signals, adds new ones.
    """
    active_signals = []

    # Load existing active signals
    if SIGNALS_OUTPUT.exists():
        with open(SIGNALS_OUTPUT) as f:
            data = json.load(f)
            active_signals = data.get("active_signals", [])

    # Remove expired signals
    now = datetime.now(ET)
    active_signals = [
        s for s in active_signals
        if datetime.fromisoformat(s["expires_at"]) > now
    ]

    # Add new signals
    active_signals.extend(new_signals)

    # Save updated active signals
    output_data = {
        "last_updated": now.isoformat(),
        "active_signal_count": len(active_signals),
        "active_signals": active_signals
    }

    with open(SIGNALS_OUTPUT, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n  ✓ Updated active signals: {len(active_signals)} signals active")

    # Print summary
    if active_signals:
        print(f"\n  Active Signals:")
        chart_count = sum(1 for s in active_signals if s['signals'].get('chart_processed'))
        print(f"    {len(active_signals)} total ({chart_count} with chart data)")

        for sig in active_signals[-3:]:  # Show last 3
            symbols = sig["signals"].get("symbols", [])
            sentiment = sig["signals"].get("sentiment", "neutral")
            confidence = sig["signals"].get("confidence", "medium")
            chart_marker = "📊" if sig['signals'].get('chart_processed') else "📝"
            print(f"    {chart_marker} {', '.join(symbols)}: {sentiment} ({confidence} confidence)")


def run_extraction_enhanced():
    """
    Main extraction routine - process raw notifications with chart integration.
    """
    print(f"\n  🔍 Enhanced Discord Signal Extraction (with Charts)")
    print(f"     Time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")

    # Process raw notifications
    new_signals = process_raw_notifications_enhanced()

    if new_signals:
        # Update active signals file
        update_active_signals(new_signals)
        print(f"\n  ✅ Extracted {len(new_signals)} new signals")
    else:
        print(f"\n  ✓ No new signals to extract")

    return len(new_signals)


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        # Test on sample
        sample_text = """QQQ at support $538, expect bounce to $545. Stop loss $535."""
        sample_timestamp = datetime.now(ET).isoformat()

        print("Testing enhanced extraction:")
        print("\nInput:", sample_text)

        signals = extract_signals_with_chart(sample_text, sample_timestamp)
        print("\nExtracted:", json.dumps(signals, indent=2))
    else:
        run_extraction_enhanced()
