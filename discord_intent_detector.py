#!/usr/bin/env python3
"""
Discord Intent Detection & Trade Lifecycle Tracking

Handles multi-message trade sequences:
1. Detects intent of each message (entry, update, exit)
2. Links related messages to track complete trade lifecycle
3. Extracts P&L, price levels, and context from each update
4. Works with chart screenshots using OCR

Example sequence:
  Message 1: "ES short here @everyone" → ENTRY detected
  Message 2: "Up $600 per con" → UPDATE detected, linked to trade
  Message 3: "Taking it off at $950" → EXIT detected, trade closed
"""

import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor

from discord_db import get_conn

ET = ZoneInfo("America/New_York")

# Symbol mapping (Discord traders often use different tickers)
SYMBOL_ALIASES = {
    "ES": "SPY",    # E-mini S&P 500 futures → SPY ETF
    "NQ": "QQQ",    # E-mini Nasdaq futures → QQQ ETF
    "SPX": "SPY",   # S&P 500 index → SPY ETF
    "NDX": "QQQ",   # Nasdaq index → QQQ ETF
    "SPY": "SPY",
    "QQQ": "QQQ",
}


def normalize_symbol(symbol: str) -> Optional[str]:
    """Convert Discord symbol to agent-compatible symbol."""
    return SYMBOL_ALIASES.get(symbol.upper())


# ═══ INTENT DETECTION ════════════════════════════════════════════════════════

def detect_intent(message_text: str, author_id: int, has_chart: bool = False) -> Dict:
    """
    Detect the intent of a Discord message.

    Returns dict with:
        - intent_type: entry, update, partial_exit, full_exit, stopped, analysis
        - confidence: 0.0 - 1.0
        - symbols: list of detected symbols
        - direction: long/short (if applicable)
        - price_levels: dict of extracted prices
        - pnl_amount: extracted P&L
        - keywords: matched keywords
    """

    result = {
        "intent_type": "unknown",
        "confidence": 0.0,
        "symbols": [],
        "direction": None,
        "price_levels": {},
        "pnl_amount": None,
        "pnl_per_contract": None,
        "keywords": [],
        "mentions_everyone": "@everyone" in message_text,
        "has_chart": has_chart
    }

    text_lower = message_text.lower()

    # Load intent patterns from database
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM intent_patterns
            WHERE active = TRUE
            ORDER BY priority DESC
        """)
        patterns = cur.fetchall()
    conn.close()

    best_match = None
    best_confidence = 0.0

    # Match against patterns
    for pattern in patterns:
        matched_keywords = []
        keyword_matches = 0

        # Check keyword regex patterns
        for keyword_pattern in pattern['keyword_regex']:
            if re.search(keyword_pattern, text_lower, re.IGNORECASE):
                keyword_matches += 1
                matched_keywords.append(keyword_pattern)

        # Must match at least one keyword
        if keyword_matches == 0:
            continue

        # Check context words (optional boosters)
        context_score = 0
        if pattern['context_words']:
            for context_word in pattern['context_words']:
                if context_word.lower() in text_lower:
                    context_score += 0.1

        # Check exclusion words (disqualifiers)
        if pattern['exclusion_words']:
            excluded = False
            for exclusion_word in pattern['exclusion_words']:
                if exclusion_word.lower() in text_lower:
                    excluded = True
                    break
            if excluded:
                continue

        # Calculate confidence
        base_confidence = pattern['confidence_score']
        keyword_boost = min(0.1 * (keyword_matches - 1), 0.2)
        total_confidence = min(base_confidence + keyword_boost + context_score, 1.0)

        # Track best match
        if total_confidence > best_confidence:
            best_confidence = total_confidence
            best_match = {
                "intent_type": pattern['intent_type'],
                "confidence": total_confidence,
                "pattern_name": pattern['pattern_name'],
                "keywords": matched_keywords
            }

    # Apply best match if found
    if best_match:
        result["intent_type"] = best_match["intent_type"]
        result["confidence"] = best_match["confidence"]
        result["keywords"] = best_match["keywords"]

    # Extract additional entities
    result["symbols"] = extract_symbols(message_text)
    result["direction"] = extract_direction(message_text)
    result["price_levels"] = extract_price_levels(message_text)

    pnl_data = extract_pnl(message_text)
    result["pnl_amount"] = pnl_data.get("total")
    result["pnl_per_contract"] = pnl_data.get("per_contract")

    # Boost confidence if key signals present
    if result["intent_type"] == "entry" and result["symbols"] and result["direction"]:
        result["confidence"] = min(result["confidence"] + 0.1, 1.0)

    return result


def extract_symbols(text: str) -> List[str]:
    """Extract trading symbols from text."""
    symbols = []

    # Common patterns: ES, NQ, SPY, QQQ, SPX, NDX
    symbol_pattern = r'\b(ES|NQ|SPY|QQQ|SPX|NDX)\b'
    matches = re.findall(symbol_pattern, text, re.IGNORECASE)

    for match in matches:
        normalized = normalize_symbol(match)
        if normalized and normalized not in symbols:
            symbols.append(normalized)

    return symbols


def extract_direction(text: str) -> Optional[str]:
    """Extract trade direction (long/short)."""
    text_lower = text.lower()

    # Short indicators
    if re.search(r'\b(short|shorting|shorted|sell|selling|sold|puts?)\b', text_lower):
        return "short"

    # Long indicators
    if re.search(r'\b(long|buy|buying|bought|calls?)\b', text_lower):
        return "long"

    return None


def extract_price_levels(text: str) -> Dict[str, float]:
    """Extract price levels mentioned in text."""
    levels = {}

    # Pattern: $XXX.XX or XXXX (for indices)
    price_patterns = [
        (r'\$(\d{2,5}\.?\d{0,2})', 'mentioned'),
        (r'\b(\d{4,5})\b', 'index_level'),  # For SPX 6500, etc.
    ]

    for pattern, label in price_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                price = float(match.replace(',', ''))
                if 100 < price < 100000:  # Reasonable price range
                    if label not in levels:
                        levels[label] = []
                    levels[label].append(price)
            except ValueError:
                continue

    # Target/Stop specific patterns
    if re.search(r'\btarget\b', text.lower()):
        # Find numbers near "target"
        target_match = re.search(r'target\s*(?:is\s*|at\s*|:)?\s*\$?(\d{2,5}\.?\d{0,2})', text.lower())
        if target_match:
            levels['target'] = float(target_match.group(1).replace(',', ''))

    if re.search(r'\bstop\b', text.lower()):
        stop_match = re.search(r'stop\s*(?:loss\s*|at\s*|:)?\s*\$?(\d{2,5}\.?\d{0,2})', text.lower())
        if stop_match:
            levels['stop'] = float(stop_match.group(1).replace(',', ''))

    return levels


def extract_pnl(text: str) -> Dict[str, Optional[float]]:
    """
    Extract P&L amounts from text.

    Examples:
        "Up $600 per con" → {"per_contract": 600}
        "$950 per contract" → {"per_contract": 950}
        "Made $5000 on this" → {"total": 5000}
    """
    pnl = {"total": None, "per_contract": None}

    # Per contract pattern
    per_con_pattern = r'\$(\d{1,5}(?:,\d{3})?)\s*(?:per|/)\s*(?:con|contract)'
    per_con_match = re.search(per_con_pattern, text, re.IGNORECASE)
    if per_con_match:
        pnl["per_contract"] = float(per_con_match.group(1).replace(',', ''))

    # Total P&L pattern (if not per contract)
    if not pnl["per_contract"]:
        total_pattern = r'\$(\d{1,6}(?:,\d{3})?)\b'
        total_match = re.search(total_pattern, text)
        if total_match:
            pnl["total"] = float(total_match.group(1).replace(',', ''))

    return pnl


# ═══ TRADE LIFECYCLE MANAGEMENT ══════════════════════════════════════════════

def create_trade(message_id: int, author_id: int, author_name: str,
                 channel_id: int, intent_data: Dict, message_timestamp: datetime) -> int:
    """
    Create new trade in lifecycle tracking.

    Called when entry intent is detected.
    """
    conn = get_conn()

    symbols = intent_data.get("symbols", [])
    symbol = symbols[0] if symbols else "UNKNOWN"
    direction = intent_data.get("direction", "unknown")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO discord_trade_lifecycle (
                symbol, author_id, author_name, channel_id,
                status, direction,
                entry_message_id, entry_timestamp,
                entry_reasoning, chart_entry_path
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            symbol, author_id, author_name, channel_id,
            'open', direction,
            message_id, message_timestamp,
            None,  # entry_reasoning (can be filled later)
            None   # chart_entry_path (if has screenshot)
        ))
        trade_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    print(f"  ✓ Created trade #{trade_id}: {symbol} {direction} by {author_name}")

    return trade_id


def find_open_trade(author_id: int, symbol: str = None,
                    lookback_hours: int = 24) -> Optional[int]:
    """
    Find an open trade by author (and optionally symbol).

    Used to link update/exit messages to existing trades.
    """
    conn = get_conn()

    query = """
        SELECT id FROM discord_trade_lifecycle
        WHERE author_id = %s
          AND status IN ('open', 'partial_close')
          AND entry_timestamp > NOW() - INTERVAL '%s hours'
    """
    params = [author_id, lookback_hours]

    if symbol:
        query += " AND symbol = %s"
        params.append(symbol)

    query += " ORDER BY entry_timestamp DESC LIMIT 1"

    with conn.cursor() as cur:
        cur.execute(query, params)
        result = cur.fetchone()

    conn.close()

    return result[0] if result else None


def update_trade(trade_id: int, intent_data: Dict, message_id: int,
                 message_timestamp: datetime):
    """
    Update existing trade with new message data.

    Called for update, partial_exit, full_exit intents.
    """
    conn = get_conn()

    intent_type = intent_data["intent_type"]
    pnl = intent_data.get("pnl_amount") or intent_data.get("pnl_per_contract")

    # Prepare update JSON entry
    update_entry = {
        "timestamp": message_timestamp.isoformat(),
        "message_id": message_id,
        "intent": intent_type,
        "pnl": pnl,
        "price_levels": intent_data.get("price_levels", {})
    }

    with conn.cursor() as cur:
        if intent_type == "update":
            # Add to updates array
            cur.execute("""
                UPDATE discord_trade_lifecycle
                SET
                    updates = COALESCE(updates, '[]'::jsonb) || %s::jsonb,
                    pnl_updates = jsonb_set(
                        COALESCE(pnl_updates, '{}'::jsonb),
                        ARRAY[%s],
                        %s::text::jsonb
                    )
                WHERE id = %s
            """, (json.dumps(update_entry), str(message_id), pnl or 0, trade_id))

        elif intent_type == "partial_exit":
            # Update status to partial_close
            cur.execute("""
                UPDATE discord_trade_lifecycle
                SET
                    status = 'partial_close',
                    exit_message_ids = array_append(COALESCE(exit_message_ids, ARRAY[]::bigint[]), %s),
                    exit_timestamps = array_append(COALESCE(exit_timestamps, ARRAY[]::timestamptz[]), %s),
                    exit_reasons = array_append(COALESCE(exit_reasons, ARRAY[]::text[]), 'partial_profit'),
                    updates = COALESCE(updates, '[]'::jsonb) || %s::jsonb
                WHERE id = %s
            """, (message_id, message_timestamp, json.dumps(update_entry), trade_id))

        elif intent_type in ("full_exit", "stopped"):
            # Close the trade
            exit_reason = 'stopped_out' if intent_type == 'stopped' else 'target_hit'

            cur.execute("""
                UPDATE discord_trade_lifecycle
                SET
                    status = 'closed',
                    exit_message_ids = array_append(COALESCE(exit_message_ids, ARRAY[]::bigint[]), %s),
                    exit_timestamps = array_append(COALESCE(exit_timestamps, ARRAY[]::timestamptz[]), %s),
                    exit_reasons = array_append(COALESCE(exit_reasons, ARRAY[]::text[]), %s),
                    final_pnl = %s,
                    updates = COALESCE(updates, '[]'::jsonb) || %s::jsonb,
                    closed_at = %s
                WHERE id = %s
            """, (message_id, message_timestamp, exit_reason, pnl,
                  json.dumps(update_entry), message_timestamp, trade_id))

    conn.commit()
    conn.close()

    print(f"  ✓ Updated trade #{trade_id}: {intent_type} (PnL: ${pnl or 0})")


def save_message_intent(message_id: int, intent_data: Dict, trade_id: int = None):
    """Save detected intent to database for tracking."""
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO message_intents (
                message_id, intent_type, confidence,
                trade_lifecycle_id,
                symbols, direction, price_levels,
                pnl_amount, pnl_per_contract,
                keywords, mentions_everyone, has_chart
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            message_id,
            intent_data["intent_type"],
            intent_data["confidence"],
            trade_id,
            intent_data.get("symbols", []),
            intent_data.get("direction"),
            json.dumps(intent_data.get("price_levels", {})),
            intent_data.get("pnl_amount"),
            intent_data.get("pnl_per_contract"),
            intent_data.get("keywords", []),
            intent_data.get("mentions_everyone", False),
            intent_data.get("has_chart", False)
        ))

    conn.commit()
    conn.close()


# ═══ MESSAGE PROCESSING WORKFLOW ═════════════════════════════════════════════

def process_discord_message(message_id: int, author_id: int, author_name: str,
                           content: str, timestamp: datetime, channel_id: int,
                           has_chart: bool = False) -> Dict:
    """
    Complete workflow to process a Discord message:
    1. Save message to database
    2. Detect intent
    3. Create/update trade lifecycle
    4. Save intent to database

    Returns dict with processing results.
    """

    # Step 0: Save message to discord_messages table
    from discord_db import save_message
    save_message(message_id, author_id, author_name, content, timestamp, channel_id)

    # Step 1: Detect intent
    intent_data = detect_intent(content, author_id, has_chart)

    print(f"\n  Message: {content[:80]}...")
    print(f"  Intent: {intent_data['intent_type']} (confidence: {intent_data['confidence']:.2f})")
    print(f"  Symbols: {intent_data['symbols']}")
    print(f"  Direction: {intent_data['direction']}")
    if intent_data['pnl_amount'] or intent_data['pnl_per_contract']:
        pnl = intent_data['pnl_amount'] or intent_data['pnl_per_contract']
        print(f"  P&L: ${pnl}")

    # Step 2: Handle based on intent type
    trade_id = None

    if intent_data["intent_type"] == "entry":
        # Create new trade
        trade_id = create_trade(
            message_id, author_id, author_name, channel_id,
            intent_data, timestamp
        )

    elif intent_data["intent_type"] in ("update", "partial_exit", "full_exit", "stopped"):
        # Find and update existing trade
        symbols = intent_data.get("symbols", [])
        symbol = symbols[0] if symbols else None

        trade_id = find_open_trade(author_id, symbol)

        if trade_id:
            update_trade(trade_id, intent_data, message_id, timestamp)
        else:
            print(f"  ⚠ No open trade found for {author_name} ({symbol or 'any symbol'})")

    # Step 3: Save intent
    save_message_intent(message_id, intent_data, trade_id)

    return {
        "intent": intent_data,
        "trade_id": trade_id,
        "processed": True
    }


# ═══ TESTING ══════════════════════════════════════════════════════════════════

def test_intent_detection():
    """Test intent detection on example messages."""

    test_messages = [
        # Entry messages
        ("ES short here @everyone", "entry"),
        ("SPY long here", "entry"),
        ("Buying QQQ calls here", "entry"),

        # Update messages
        ("Up $600 per con here at low hanging fruit (1:1). Take it if you wish @everyone", "update"),
        ("$950 per con here. SPX is almost at 6500", "update"),

        # Exit messages
        ("Taking it off here. Great trade @everyone", "full_exit"),
        ("Stopped out", "stopped"),
        ("Target hit at 6500", "full_exit"),

        # Analysis messages
        ("DOL is fake news pump from Monday premarket", "analysis"),
        ("Support at $650, looking for bounce", "analysis"),
    ]

    print("\n" + "═" * 70)
    print("  INTENT DETECTION TEST")
    print("═" * 70)

    for message, expected_intent in test_messages:
        print(f"\nMessage: \"{message}\"")
        intent = detect_intent(message, author_id=123, has_chart=False)
        print(f"  Detected: {intent['intent_type']} (confidence: {intent['confidence']:.2f})")
        print(f"  Expected: {expected_intent}")
        print(f"  Symbols: {intent['symbols']}")
        print(f"  Direction: {intent['direction']}")
        if intent['pnl_amount'] or intent['pnl_per_contract']:
            print(f"  P&L: ${intent['pnl_amount'] or intent['pnl_per_contract']}")

        match = "✓" if intent['intent_type'] == expected_intent else "✗"
        print(f"  {match}")


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_intent_detection()
    else:
        print("Discord Intent Detector")
        print("Usage:")
        print("  python3 discord_intent_detector.py --test    # Test intent detection")
