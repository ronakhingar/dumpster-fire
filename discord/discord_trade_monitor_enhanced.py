#!/usr/bin/env python3
"""
Enhanced Discord Trade Monitor for #day-trade-alerts Channel

Features:
- Multi-message threading - links related messages
- Chart OCR - reads levels from screenshots
- Context understanding - builds trades from partial info
- State tracking - monitors trade lifecycle

Handles real-world patterns:
- Entry → Update → Exit sequences
- Chart images with visual levels
- Position updates (BE, partial exits)
- Invalidations
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

from discord.enhanced_trade_parser import get_parser

ET = ZoneInfo("America/New_York")

# Paths
BASE_DIR = Path(__file__).parent.parent
TRADES_CACHE = BASE_DIR / "journal" / "discord_trades_enhanced.json"
INVALIDATIONS_LOG = BASE_DIR / "journal" / "discord_invalidations.jsonl"
IMAGE_CACHE_DIR = BASE_DIR / "journal" / "discord_charts"

# Discord API configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = "981926799212679248"  # #day-trade-alerts (The Traveling Trader)
API_BASE = "https://discord.com/api/v10"

# Trade signal expiry
SIGNAL_EXPIRY_HOURS = 4


def _get_headers():
    """Get Discord API headers with bot or user token (auto-detected)."""
    if not DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN not set in environment")

    # Auto-detect: user tokens work without "Bot " prefix, bot tokens need it
    # Try as user token first (more common for extracted tokens)
    return {
        "Authorization": DISCORD_BOT_TOKEN,
        "Content-Type": "application/json"
    }


def fetch_recent_messages(limit: int = 100):
    """
    Fetch recent messages from #day-trade-alerts channel.

    Returns:
        List of message dicts with id, content, timestamp, author, attachments
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
                "author": {
                    "id": msg["author"]["id"],
                    "name": msg["author"]["username"],
                    "nickname": msg["author"].get("global_name", msg["author"]["username"])
                },
                "attachments": msg.get("attachments", [])
            })

        return parsed

    except Exception as e:
        print(f"  ⚠️  Error fetching Discord messages: {e}")
        return []


def download_chart_image(attachment: dict) -> Optional[str]:
    """
    Download chart image attachment.

    Returns:
        Path to downloaded image file, or None if failed
    """
    if not attachment.get("url"):
        return None

    # Check if it's an image
    content_type = attachment.get("content_type", "")
    if not content_type.startswith("image/"):
        return None

    try:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Download image
        response = requests.get(attachment["url"], timeout=10)
        response.raise_for_status()

        # Save to cache
        filename = f"{attachment['id']}_{attachment['filename']}"
        filepath = IMAGE_CACHE_DIR / filename

        with open(filepath, 'wb') as f:
            f.write(response.content)

        return str(filepath)

    except Exception as e:
        print(f"  ⚠️  Failed to download image: {e}")
        return None


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


def update_trades_cache(trades: list[dict]):
    """Save active trades to cache file."""
    TRADES_CACHE.parent.mkdir(parents=True, exist_ok=True)

    cache_data = {
        "last_updated": datetime.now(ET).isoformat(),
        "active_trades": trades
    }

    with open(TRADES_CACHE, "w") as f:
        json.dump(cache_data, f, indent=2)


def log_invalidation(trade: dict, reason: str):
    """Log invalidated trade to journal."""
    INVALIDATIONS_LOG.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(ET).isoformat(),
        "symbol": trade["symbol"],
        "direction": trade["direction"],
        "entry": trade["entry"],
        "invalidation_reason": reason,
        "messages": trade.get("messages", [])
    }

    with open(INVALIDATIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def sync_discord_trades():
    """
    Fetch recent messages, process with enhanced parser, check invalidations.
    Updates cache with active trades.
    """
    print(f"\n  📱 Syncing Discord #day-trade-alerts (Enhanced Mode)...")

    # Get parser instance
    parser = get_parser()

    # Fetch recent messages
    messages = fetch_recent_messages(limit=100)
    if not messages:
        print(f"  ⚠️  No messages fetched from Discord")
        return

    print(f"  ✓ Fetched {len(messages)} recent messages")

    # Load existing trades
    active_trades = load_trades_cache()
    existing_ids = {t.get('messages', [[]])[0] if t.get('messages') else None for t in active_trades}

    # Process messages in chronological order (oldest first)
    messages.reverse()

    new_signals = []
    processed_count = 0

    for msg in messages:
        # Skip if already processed
        if msg['id'] in existing_ids:
            continue

        # Download chart images if present
        chart_images = []
        for attachment in msg.get('attachments', []):
            img_path = download_chart_image(attachment)
            if img_path:
                chart_images.append(img_path)
                print(f"  📊 Downloaded chart image: {attachment['filename']}")

        # Process message
        signal = parser.process_message(msg, chart_images=chart_images)

        if signal:
            # Add metadata
            signal['message_id'] = signal['messages'][-1] if signal.get('messages') else msg['id']
            signal['timestamp'] = signal['first_seen']
            signal['expires_at'] = (datetime.fromisoformat(signal['first_seen']) +
                                   timedelta(hours=SIGNAL_EXPIRY_HOURS)).isoformat()
            signal['invalidated'] = False
            signal['risk_reward'] = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])

            new_signals.append(signal)

        processed_count += 1

    # Add new signals to active trades
    active_trades.extend(new_signals)

    if new_signals:
        print(f"  🎯 NEW SIGNALS: {len(new_signals)}")
        for sig in new_signals:
            print(f"     {sig['direction'].upper()} {sig['symbol']} @ {sig['entry']}, "
                  f"SL {sig['stop']}, TP {sig['target']} (R:R {sig['risk_reward']:.1f})")

    # Clean up stale trades
    parser.cleanup_stale_trades(max_age_hours=24)

    # Remove expired trades
    now = datetime.now(ET)
    active_trades = [
        t for t in active_trades
        if datetime.fromisoformat(t["expires_at"]) > now or not t.get("invalidated", False)
    ]

    # Remove invalidated trades older than 1 hour
    one_hour_ago = now - timedelta(hours=1)
    active_trades = [
        t for t in active_trades
        if not t.get("invalidated", False) or
           datetime.fromisoformat(t.get("invalidated_at", t["timestamp"])).astimezone(ET) > one_hour_ago
    ]

    # Update cache
    update_trades_cache(active_trades)

    # Summary
    valid_count = len([t for t in active_trades if not t.get("invalidated", False)])
    print(f"  ✓ Active trades: {valid_count} valid, {len(active_trades) - valid_count} invalidated")
    print(f"  ✓ Processed {processed_count} messages")

    return active_trades


def get_active_discord_trade(symbol: str):
    """
    Get the most recent valid Discord trade for a symbol.

    Returns:
        Trade dict or None if no valid trade exists
    """
    active_trades = load_trades_cache()

    # Filter for symbol and not invalidated
    valid_trades = [
        t for t in active_trades
        if t["symbol"] == symbol and not t.get("invalidated", False)
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
        symbol: SPY, QQQ, or GLD
        entry_price: Optional entry price to match specific trade

    Returns:
        (is_invalidated: bool, reason: str or None)
    """
    active_trades = load_trades_cache()

    # Find matching trade
    for trade in active_trades:
        if trade["symbol"] == symbol:
            if entry_price is None or abs(trade["entry"] - entry_price) < 0.01:
                if trade.get("invalidated", False):
                    return True, trade.get("invalidation_reason", "Setup invalidated")

    return False, None


def get_trade_summary():
    """
    Get a summary of all active Discord trades for display.

    Returns:
        Human-readable string summary
    """
    active_trades = load_trades_cache()
    valid_trades = [t for t in active_trades if not t.get("invalidated", False)]

    if not valid_trades:
        return "No active Discord trades"

    lines = []
    for trade in valid_trades:
        age_minutes = (datetime.now(ET) - datetime.fromisoformat(trade["timestamp"]).astimezone(ET)).total_seconds() / 60
        lines.append(
            f"{trade['symbol']}: {trade['direction'].upper()} @ {trade['entry']}, "
            f"SL {trade['stop']}, TP {trade['target']} "
            f"(R:R {trade.get('risk_reward', 0):.1f}, {int(age_minutes)}m ago)"
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
        print(f"  ACTIVE DISCORD TRADES (Enhanced Parser)")
        print(f"{'='*72}")
        print(f"  {get_trade_summary()}")

        for sym in ["SPY", "QQQ", "GLD"]:
            trade = get_active_discord_trade(sym)
            if trade:
                print(f"\n  {sym}: Valid trade found")
                print(f"    Direction: {trade['direction'].upper()}")
                print(f"    Entry: {trade['entry']}")
                print(f"    Stop: {trade['stop']}")
                print(f"    Target: {trade['target']}")
                print(f"    R:R: {trade.get('risk_reward', 0):.1f}")
                print(f"    Messages: {len(trade.get('messages', []))}")
            else:
                print(f"\n  {sym}: No active trade")

    else:
        print("Enhanced Discord Trade Monitor")
        print("Usage:")
        print("  python3 discord_trade_monitor_enhanced.py --sync   # Sync Discord trades")
        print("  python3 discord_trade_monitor_enhanced.py --test   # Sync and display active trades")
