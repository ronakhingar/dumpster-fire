#!/usr/bin/env python3
"""
Discord Trade Monitor for #day-trade-alerts Channel

Monitors Discord #day-trade-alerts channel for explicit trade signals.
Priority: Discord trades > chart analysis

Features:
  - Parses trade messages (entry, stop, target, direction, symbol)
  - Validates setup is still active (not invalidated)
  - Monitors for invalidation messages
  - Returns ready-to-trade signals for futures agent

Usage:
  from discord.discord_trade_monitor import get_active_discord_trade, check_invalidation

  # Get active trade
  trade = get_active_discord_trade(symbol="SPY")
  if trade:
      # Use Discord trade instead of chart analysis
      execute_trade(trade)

  # Check if position should be exited
  if check_invalidation(symbol="SPY", position_id=pos_id):
      exit_position(pos_id)
"""

import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ET = ZoneInfo("America/New_York")

# Paths
BASE_DIR = Path(__file__).parent.parent
TRADES_CACHE = BASE_DIR / "journal" / "discord_trades.json"
INVALIDATIONS_LOG = BASE_DIR / "journal" / "discord_invalidations.jsonl"

# Discord API configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = "1336773655095111801"  # #day-trade-alerts
API_BASE = "https://discord.com/api/v10"

# Trade signal expiry (how long a signal stays valid without explicit invalidation)
SIGNAL_EXPIRY_HOURS = 4  # Intraday trades expire after 4 hours


def _get_headers():
    """Get Discord API headers with bot token."""
    if not DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN not set in environment")
    return {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }


def fetch_recent_messages(limit: int = 50):
    """
    Fetch recent messages from #day-trade-alerts channel.

    Returns:
        List of message dicts with id, content, timestamp, author
    """
    try:
        url = f"{API_BASE}/channels/{CHANNEL_ID}/messages?limit={limit}"
        response = requests.get(url, headers=_get_headers(), timeout=10)
        response.raise_for_status()

        messages = response.json()

        # Parse into simpler format
        parsed = []
        for msg in messages:
            parsed.append({
                "id": msg["id"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "author": msg["author"]["username"],
                "author_id": msg["author"]["id"]
            })

        return parsed

    except Exception as e:
        print(f"  ⚠️  Error fetching Discord messages: {e}")
        return []


def parse_trade_signal(content: str, message_id: str, timestamp: str):
    """
    Parse a Discord message for explicit trade signals.

    Expected patterns:
      - "SELL SPY @ 650.50, SL 651.00, TP 648.00"
      - "BUY QQQ 580.25 stop 579.50 target 582.00"
      - "SHORT MES 6350, stop 6355, target 6340"
      - Various casual formats with entry/stop/target levels

    Returns:
        Trade signal dict or None if not a valid trade signal
    """
    content_lower = content.lower()

    # Check if message contains trade keywords
    trade_keywords = ["buy", "sell", "long", "short", "entry", "stop", "target", "tp", "sl"]
    if not any(kw in content_lower for kw in trade_keywords):
        return None

    # Extract symbol - E-mini S&P, Nasdaq, and Gold futures
    # Ignore: CL (crude oil), other commodities
    symbols = re.findall(r'\b(SPY|QQQ|GLD|MES|MNQ|MGC|ES|NQ|GC|S&P|NASDAQ|GOLD|SPX|NDX)\b', content, re.IGNORECASE)
    if not symbols:
        return None

    symbol = symbols[0].upper()

    # Filter: Reject crude oil and other unsupported commodities
    if "CL" in content.upper() or "CRUDE" in content.upper() or "OIL" in content.upper():
        return None  # Ignore crude oil trades

    # Normalize for futures agent (all variants → SPY, QQQ, or GLD)
    if symbol in ("MES", "ES", "S&P", "SPX", "SPY"):
        symbol = "SPY"  # E-mini S&P 500
    elif symbol in ("MNQ", "NQ", "NASDAQ", "NDX", "QQQ"):
        symbol = "QQQ"  # E-mini Nasdaq 100
    elif symbol in ("MGC", "GC", "GOLD", "GLD"):
        symbol = "GLD"  # Micro Gold (via GLD ETF)
    else:
        # Unknown or unsupported symbol
        return None

    # Determine direction
    direction = None
    if any(kw in content_lower for kw in ["buy", "long", "dca", "add"]):
        direction = "buy"
    elif any(kw in content_lower for kw in ["sell", "short"]):
        direction = "sell"

    if not direction:
        return None

    # Extract price levels
    # Look for patterns like: 650.50, 651.00, $650, etc.
    prices = re.findall(r'[\$]?(\d{2,4}(?:\.\d{1,2})?)', content)
    prices = [float(p) for p in prices if 100 < float(p) < 10000]  # Reasonable price range

    if len(prices) < 2:  # Need at least entry and one other level
        return None

    # Try to identify entry, stop, target
    # Common pattern: first price is entry, then stop, then target
    entry = None
    stop = None
    target = None

    # Look for explicit labels
    entry_match = re.search(r'(?:entry|@|at|price)[:\s]*[\$]?(\d{2,4}(?:\.\d{1,2})?)', content_lower)
    stop_match = re.search(r'(?:stop|sl|stop\s*loss)[:\s]*[\$]?(\d{2,4}(?:\.\d{1,2})?)', content_lower)
    target_match = re.search(r'(?:target|tp|take\s*profit)[:\s]*[\$]?(\d{2,4}(?:\.\d{1,2})?)', content_lower)

    if entry_match:
        entry = float(entry_match.group(1))
    if stop_match:
        stop = float(stop_match.group(1))
    if target_match:
        target = float(target_match.group(1))

    # Fallback: use sequential prices
    if not entry and len(prices) >= 1:
        entry = prices[0]

    if direction == "buy":
        # For LONG: stop < entry < target
        if not stop and len(prices) >= 2:
            stop = min(prices[1:])
        if not target and len(prices) >= 2:
            target = max(prices[1:])
    else:
        # For SHORT: target < entry < stop
        if not stop and len(prices) >= 2:
            stop = max(prices[1:])
        if not target and len(prices) >= 2:
            target = min(prices[1:])

    # Validate we have all three levels
    if not (entry and stop and target):
        return None

    # Validate logic
    if direction == "buy":
        if not (stop < entry < target):
            return None
    else:
        if not (target < entry < stop):
            return None

    # Calculate risk/reward
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr_ratio = reward / risk if risk > 0 else 0

    return {
        "message_id": message_id,
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": round(rr_ratio, 2),
        "raw_content": content,
        "expires_at": (datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(ET) +
                      timedelta(hours=SIGNAL_EXPIRY_HOURS)).isoformat(),
        "invalidated": False,
        "invalidation_reason": None
    }


def check_invalidation_message(content: str, active_trades: list[dict]):
    """
    Check if a message invalidates any active trades.

    Invalidation patterns:
      - "setup invalidated"
      - "scratch that"
      - "cancel [symbol]"
      - "no longer valid"
      - "abort"
      - "exit"

    Returns:
        List of trade message IDs that should be invalidated
    """
    content_lower = content.lower()

    # Invalidation keywords
    invalidation_keywords = [
        "invalidated", "invalid", "scratch", "cancel", "no longer valid",
        "abort", "exit", "get out", "close position", "stop out",
        "setup broke", "setup failed", "wrong", "mistake"
    ]

    if not any(kw in content_lower for kw in invalidation_keywords):
        return []

    # Extract symbols mentioned
    symbols_mentioned = re.findall(r'\b(SPY|QQQ|MES|MNQ|ES|NQ)\b', content, re.IGNORECASE)
    symbols_mentioned = [s.upper() for s in symbols_mentioned]

    # Normalize
    symbols_normalized = []
    for s in symbols_mentioned:
        if s in ("MES", "ES"):
            symbols_normalized.append("SPY")
        elif s in ("MNQ", "NQ"):
            symbols_normalized.append("QQQ")
        else:
            symbols_normalized.append(s)

    # If no specific symbol, invalidate all recent trades
    if not symbols_normalized:
        # Return all trades from last 2 hours
        recent_cutoff = datetime.now(ET) - timedelta(hours=2)
        return [
            t["message_id"] for t in active_trades
            if datetime.fromisoformat(t["timestamp"]).astimezone(ET) > recent_cutoff
        ]

    # Invalidate specific symbols
    return [
        t["message_id"] for t in active_trades
        if t["symbol"] in symbols_normalized
    ]


def update_trades_cache(trades: list[dict]):
    """Save active trades to cache file."""
    TRADES_CACHE.parent.mkdir(parents=True, exist_ok=True)

    cache_data = {
        "last_updated": datetime.now(ET).isoformat(),
        "active_trades": trades
    }

    with open(TRADES_CACHE, "w") as f:
        json.dump(cache_data, f, indent=2)


def load_trades_cache():
    """Load active trades from cache."""
    if not TRADES_CACHE.exists():
        return []

    try:
        with open(TRADES_CACHE) as f:
            data = json.load(f)
            return data.get("active_trades", [])
    except Exception:
        return []


def log_invalidation(trade: dict, reason: str):
    """Log invalidated trade to journal."""
    INVALIDATIONS_LOG.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(ET).isoformat(),
        "message_id": trade["message_id"],
        "symbol": trade["symbol"],
        "direction": trade["direction"],
        "entry": trade["entry"],
        "invalidation_reason": reason,
        "original_content": trade["raw_content"]
    }

    with open(INVALIDATIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def sync_discord_trades():
    """
    Fetch recent messages, parse trades, check invalidations.
    Updates cache with active trades.

    Call this periodically (every 2 min aligned with agent scan).
    """
    print(f"\n  📱 Syncing Discord #day-trade-alerts...")

    # Fetch recent messages
    messages = fetch_recent_messages(limit=50)
    if not messages:
        print(f"  ⚠️  No messages fetched from Discord")
        return

    print(f"  ✓ Fetched {len(messages)} recent messages")

    # Load existing trades
    active_trades = load_trades_cache()

    # Parse new trade signals
    new_trades = []
    skipped_count = 0
    for msg in messages:
        # Skip if we already have this message
        if any(t["message_id"] == msg["id"] for t in active_trades):
            continue

        # Check if message mentions non-supported symbols (for logging)
        content_upper = msg["content"].upper()
        if any(keyword in content_upper for keyword in ["CL", "CRUDE", "OIL"]) and \
             any(kw in content_upper for kw in ["BUY", "SELL", "LONG", "SHORT"]):
            skipped_count += 1
            print(f"  ⏭ Skipped crude oil trade - not supported")
            continue

        # Try to parse as trade signal
        trade = parse_trade_signal(msg["content"], msg["id"], msg["timestamp"])
        if trade:
            print(f"  🎯 NEW TRADE: {trade['direction'].upper()} {trade['symbol']} @ {trade['entry']}, "
                  f"SL {trade['stop']}, TP {trade['target']} (R:R {trade['risk_reward']})")
            new_trades.append(trade)

    # Add new trades to active list
    active_trades.extend(new_trades)

    # Check for invalidation messages
    for msg in messages:
        invalidated_ids = check_invalidation_message(msg["content"], active_trades)

        if invalidated_ids:
            print(f"  ⚠️  INVALIDATION detected: {len(invalidated_ids)} trades affected")
            print(f"      Message: \"{msg['content'][:100]}...\"")

            for trade in active_trades:
                if trade["message_id"] in invalidated_ids and not trade["invalidated"]:
                    trade["invalidated"] = True
                    trade["invalidation_reason"] = msg["content"]
                    trade["invalidated_at"] = datetime.now(ET).isoformat()

                    log_invalidation(trade, msg["content"])
                    print(f"      ✗ {trade['symbol']} {trade['direction'].upper()} invalidated")

    # Remove expired trades (older than expiry time and not explicitly invalidated)
    now = datetime.now(ET)
    active_trades = [
        t for t in active_trades
        if datetime.fromisoformat(t["expires_at"]) > now or not t["invalidated"]
    ]

    # Remove invalidated trades older than 1 hour (keep recent invalidations for logging)
    one_hour_ago = now - timedelta(hours=1)
    active_trades = [
        t for t in active_trades
        if not t["invalidated"] or
           datetime.fromisoformat(t.get("invalidated_at", t["timestamp"])).astimezone(ET) > one_hour_ago
    ]

    # Update cache
    update_trades_cache(active_trades)

    # Summary
    valid_count = len([t for t in active_trades if not t["invalidated"]])
    print(f"  ✓ Active trades: {valid_count} valid, {len(active_trades) - valid_count} invalidated")
    if skipped_count > 0:
        print(f"  ⏭ Skipped {skipped_count} unsupported trades (crude oil, etc.)")

    return active_trades


def get_active_discord_trade(symbol: str):
    """
    Get the most recent valid Discord trade for a symbol.

    Returns:
        Trade dict or None if no valid trade exists

    Trade dict format:
        {
            "symbol": "SPY",
            "direction": "buy" or "sell",
            "entry": 650.50,
            "stop": 649.00,
            "target": 653.00,
            "risk_reward": 1.67,
            "timestamp": "2026-04-01T09:25:00-04:00",
            "expires_at": "2026-04-01T13:25:00-04:00",
            "raw_content": "Original Discord message..."
        }
    """
    active_trades = load_trades_cache()

    # Filter for symbol and not invalidated
    valid_trades = [
        t for t in active_trades
        if t["symbol"] == symbol and not t["invalidated"]
    ]

    if not valid_trades:
        return None

    # Return most recent
    valid_trades.sort(key=lambda x: x["timestamp"], reverse=True)
    return valid_trades[0]


def check_invalidation(symbol: str, entry_price: float = None):
    """
    Check if a specific trade has been invalidated.

    Args:
        symbol: SPY or QQQ
        entry_price: Optional entry price to match specific trade

    Returns:
        (is_invalidated: bool, reason: str or None)
    """
    active_trades = load_trades_cache()

    # Find matching trade
    for trade in active_trades:
        if trade["symbol"] == symbol:
            if entry_price is None or abs(trade["entry"] - entry_price) < 0.01:
                if trade["invalidated"]:
                    return True, trade.get("invalidation_reason", "Setup invalidated")

    return False, None


def get_trade_summary():
    """
    Get a summary of all active Discord trades for display.

    Returns:
        Human-readable string summary
    """
    active_trades = load_trades_cache()
    valid_trades = [t for t in active_trades if not t["invalidated"]]

    if not valid_trades:
        return "No active Discord trades"

    lines = []
    for trade in valid_trades:
        age_minutes = (datetime.now(ET) - datetime.fromisoformat(trade["timestamp"]).astimezone(ET)).total_seconds() / 60
        lines.append(
            f"{trade['symbol']}: {trade['direction'].upper()} @ {trade['entry']}, "
            f"SL {trade['stop']}, TP {trade['target']} "
            f"(R:R {trade['risk_reward']}, {int(age_minutes)}m ago)"
        )

    return "\n    ".join(lines)


if __name__ == "__main__":
    import sys

    if "--sync" in sys.argv:
        # Sync Discord trades
        sync_discord_trades()

    elif "--test" in sys.argv:
        # Test mode: sync and display
        sync_discord_trades()
        print(f"\n{'='*72}")
        print(f"  ACTIVE DISCORD TRADES")
        print(f"{'='*72}")
        print(f"  {get_trade_summary()}")

        for sym in ["SPY", "QQQ"]:
            trade = get_active_discord_trade(sym)
            if trade:
                print(f"\n  {sym}: Valid trade found")
                print(f"    Direction: {trade['direction'].upper()}")
                print(f"    Entry: {trade['entry']}")
                print(f"    Stop: {trade['stop']}")
                print(f"    Target: {trade['target']}")
                print(f"    R:R: {trade['risk_reward']}")
            else:
                print(f"\n  {sym}: No active trade")

    else:
        print("Discord Trade Monitor")
        print("Usage:")
        print("  python3 discord_trade_monitor.py --sync   # Sync Discord trades")
        print("  python3 discord_trade_monitor.py --test   # Sync and display active trades")
