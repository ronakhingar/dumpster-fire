#!/usr/bin/env python3
"""
Backfill chart data to existing Discord signals.

Processes historical signals and adds chart TP/SL data.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from discord_signal_extractor_enhanced import (
    extract_signals_with_chart,
    is_trading_chart,
    CHART_OCR_AVAILABLE
)

ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).parent
SIGNALS_HISTORY = BASE_DIR / "journal" / "discord_signals_history.jsonl"
OUTPUT_FILE = BASE_DIR / "journal" / "discord_signals_enhanced.jsonl"


def backfill_chart_data():
    """Process historical signals and enhance with chart data."""

    print("\n" + "="*70)
    print("  BACKFILLING CHART DATA TO HISTORICAL SIGNALS")
    print("="*70)

    if not CHART_OCR_AVAILABLE:
        print("\n  ✗ Chart OCR not available")
        return

    if not SIGNALS_HISTORY.exists():
        print("\n  ✗ No signals history file")
        return

    # Load all historical signals
    signals = []
    with open(SIGNALS_HISTORY) as f:
        for line in f:
            if line.strip():
                signals.append(json.loads(line))

    print(f"\n  📊 Processing {len(signals)} historical signals...")

    enhanced_count = 0
    chart_found_count = 0

    with open(OUTPUT_FILE, 'w') as out_f:
        for i, signal in enumerate(signals):
            raw_text = signal.get('raw_text', '')
            timestamp = signal.get('source_timestamp') or signal.get('timestamp')

            if not raw_text or not timestamp:
                # Write original signal
                out_f.write(json.dumps(signal) + '\n')
                continue

            print(f"\n  [{i+1}/{len(signals)}] Processing signal from {timestamp[:10]}...")
            print(f"    Text: {raw_text[:80]}...")

            # Re-extract with chart enhancement
            enhanced_signals = extract_signals_with_chart(raw_text, timestamp)

            # Check if chart was found
            if enhanced_signals.get('chart_processed'):
                chart_found_count += 1
                enhanced_count += 1

                # Update signal record
                signal['signals'] = enhanced_signals
                print(f"    ✓ Enhanced with chart data!")
            else:
                print(f"    ○ No chart found or low confidence")

            # Write enhanced signal
            out_f.write(json.dumps(signal) + '\n')

    print(f"\n" + "="*70)
    print(f"  ✅ BACKFILL COMPLETE")
    print(f"     Total signals: {len(signals)}")
    print(f"     Charts found: {chart_found_count}")
    print(f"     Enhanced: {enhanced_count}")
    print(f"     Output: {OUTPUT_FILE}")
    print("="*70)


if __name__ == "__main__":
    backfill_chart_data()
