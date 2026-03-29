#!/usr/bin/env python3
"""
Discord Signal Extractor

Reads raw Discord notifications and extracts actionable trading signals using Claude API.

Processes messages like:
- Price targets and support/resistance levels
- Market sentiment and bias predictions
- Risk factors and catalysts
- Technical analysis insights

Output: Structured signals ready for agent consumption.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

ET = ZoneInfo("America/New_York")

# Paths
BASE_DIR = Path(__file__).parent
RAW_INPUT = BASE_DIR / "journal" / "discord_raw.jsonl"
SIGNALS_OUTPUT = BASE_DIR / "journal" / "discord_signals.json"
SIGNALS_HISTORY = BASE_DIR / "journal" / "discord_signals_history.jsonl"

# Claude API (optional - if you want AI extraction)
# For now, we'll use pattern matching
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def extract_signals_pattern_matching(text: str) -> dict:
    """
    Extract trading signals using pattern matching.

    Looks for:
    - Symbol mentions (SPY, QQQ, SPX, NDX)
    - Price levels ($XXX, XXX.XX)
    - Directional words (bullish, bearish, long, short, buy, sell)
    - Support/resistance mentions
    - Technical indicators
    """
    import re

    signals = {
        "symbols": [],
        "price_levels": [],
        "sentiment": None,
        "confidence": "medium",
        "key_points": [],
        "targets": {},
        "risk_factors": []
    }

    text_upper = text.upper()

    # Extract symbols
    for symbol in ["SPY", "QQQ", "SPX", "NDX", "NASDAQ", "S&P", "S&P500"]:
        if symbol in text_upper:
            if symbol in ["SPX", "S&P", "S&P500"]:
                signals["symbols"].append("SPY")
            elif symbol in ["NDX", "NASDAQ"]:
                signals["symbols"].append("QQQ")
            else:
                signals["symbols"].append(symbol)

    # Remove duplicates
    signals["symbols"] = list(set(signals["symbols"]))

    # Extract price levels (matches $XXX or XXX.XX)
    price_pattern = r'\$?(\d{2,4}\.?\d{0,2})'
    prices = re.findall(price_pattern, text)
    signals["price_levels"] = [float(p.replace(',', '')) for p in prices if float(p.replace(',', '')) > 100]

    # Sentiment analysis
    bullish_words = ["bullish", "long", "buy", "bounce", "rally", "support", "bottom", "oversold"]
    bearish_words = ["bearish", "short", "sell", "drop", "correction", "resistance", "top", "overbought"]

    bullish_count = sum(1 for word in bullish_words if word in text.lower())
    bearish_count = sum(1 for word in bearish_words if word.lower() in text.lower())

    if bullish_count > bearish_count:
        signals["sentiment"] = "bullish"
    elif bearish_count > bullish_count:
        signals["sentiment"] = "bearish"
    else:
        signals["sentiment"] = "neutral"

    # Confidence heuristics
    if "high confidence" in text.lower() or "strong" in text.lower():
        signals["confidence"] = "high"
    elif "maybe" in text.lower() or "possibly" in text.lower() or "might" in text.lower():
        signals["confidence"] = "low"

    # Extract key phrases (sentences mentioning symbols or price levels)
    sentences = text.split('.')
    for sentence in sentences:
        sentence = sentence.strip()
        if any(sym in sentence.upper() for sym in ["SPY", "QQQ"]) or any(char.isdigit() for char in sentence):
            if len(sentence) > 20:
                signals["key_points"].append(sentence)

    # Extract targets
    target_pattern = r'(?:target|support|resistance|level).*?(\$?\d{2,4}\.?\d{0,2})'
    targets = re.findall(target_pattern, text.lower())
    if targets:
        for symbol in signals["symbols"]:
            if symbol not in signals["targets"]:
                signals["targets"][symbol] = []
            signals["targets"][symbol].extend([float(t.replace('$', '').replace(',', '')) for t in targets])

    # Risk factors
    risk_keywords = ["oil", "war", "recession", "invasion", "spike", "crash", "risk"]
    for keyword in risk_keywords:
        if keyword in text.lower():
            # Extract sentence containing risk factor
            for sentence in sentences:
                if keyword in sentence.lower():
                    signals["risk_factors"].append(sentence.strip())
                    break

    return signals


def extract_signals_with_claude(text: str) -> dict:
    """
    Use Claude API to extract trading signals from natural language.

    This provides more sophisticated understanding of context and nuance.
    """
    if not ANTHROPIC_API_KEY:
        # Fallback to pattern matching
        return extract_signals_pattern_matching(text)

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = f"""Extract trading signals from this Discord message. Return JSON only.

Message:
{text}

Extract:
1. Symbols mentioned (SPY, QQQ)
2. Price levels/targets (support, resistance, targets)
3. Overall sentiment (bullish/bearish/neutral)
4. Confidence level (high/medium/low)
5. Key insights (bullet points)
6. Risk factors mentioned
7. Time horizon if mentioned (short-term, medium-term, long-term)

Return JSON format:
{{
  "symbols": ["SPY", "QQQ"],
  "sentiment": "bearish",
  "confidence": "medium",
  "time_horizon": "short-term",
  "price_targets": {{
    "SPY": {{"support": [613, 590], "resistance": [670]}},
    "QQQ": {{"support": [540, 520], "resistance": [580]}}
  }},
  "key_insights": [
    "QQQ down 10% in correction, at 300MA",
    "Short-term bounce expected before more downside"
  ],
  "risk_factors": [
    "Oil above $100 could trigger recession",
    "Ground invasion would cause initial gap down"
  ]
}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract JSON from response
        content = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content)

    except Exception as e:
        print(f"  ⚠ Claude extraction failed: {e}, falling back to pattern matching")
        return extract_signals_pattern_matching(text)


def process_raw_notifications():
    """
    Process unprocessed raw notifications and extract signals.
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

    print(f"  📊 Processing {len(unprocessed)} new notifications...")

    processed_signals = []

    for entry in unprocessed:
        text = entry.get("raw_text", "")

        if len(text) < 50:  # Skip very short messages
            continue

        print(f"\n  Extracting from: {text[:80]}...")

        # Extract signals (use Claude if API key available, otherwise pattern matching)
        if ANTHROPIC_API_KEY:
            signals = extract_signals_with_claude(text)
        else:
            signals = extract_signals_pattern_matching(text)

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

        print(f"  ✓ Extracted: {signals.get('symbols', [])} - {signals.get('sentiment', 'neutral')}")

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
        for sig in active_signals[-3:]:  # Show last 3
            symbols = sig["signals"].get("symbols", [])
            sentiment = sig["signals"].get("sentiment", "neutral")
            confidence = sig["signals"].get("confidence", "medium")
            print(f"    • {', '.join(symbols)}: {sentiment} ({confidence} confidence)")


def run_extraction():
    """
    Main extraction routine - process raw notifications and update signals.
    """
    print(f"\n  🔍 Discord Signal Extraction")
    print(f"     Time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")

    # Process raw notifications
    new_signals = process_raw_notifications()

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
        # Test extraction on sample text
        sample = """QQQ is officially in a correction down 10% from highs almost at the 300MA (SPY is down 7.5%).
        I make a habit of adding indices to my portfolio if we drop 10%. Next level is $538.
        realistic targets for SPY are $613 and $590. QQQ are $540 and $520."""

        print("Testing signal extraction:")
        print("\nInput:", sample)
        print("\nExtracted:", json.dumps(extract_signals_pattern_matching(sample), indent=2))
    else:
        run_extraction()
