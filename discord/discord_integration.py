#!/usr/bin/env python3
"""
Discord Signal Integration for Trading Agent

Reads processed Discord signals and provides scoring modifiers for the agent.

Called by agent.py during each trading cycle to factor in Discord insights.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

BASE_DIR = Path(__file__).parent.parent
SIGNALS_FILE = BASE_DIR / "journal" / "discord_signals.json"
SIGNALS_HISTORY = BASE_DIR / "journal" / "discord_signals_history.jsonl"


def load_active_signals():
    """Load active Discord signals."""
    if not SIGNALS_FILE.exists():
        return []

    try:
        with open(SIGNALS_FILE) as f:
            data = json.load(f)
            return data.get("active_signals", [])
    except Exception as e:
        print(f"  ⚠ Error loading Discord signals: {e}")
        return []


def get_signal_for_symbol(symbol: str):
    """
    Get the most recent active signal for a given symbol.

    Returns signal dict or None if no active signal.
    """
    signals = load_active_signals()

    # Filter by symbol and check expiry
    now = datetime.now(ET)
    relevant_signals = []

    for sig in signals:
        # Check if signal mentions this symbol
        sig_symbols = sig.get("signals", {}).get("symbols", [])

        if symbol in sig_symbols:
            # Check if not expired
            expires_at = datetime.fromisoformat(sig["expires_at"])
            if expires_at > now:
                relevant_signals.append(sig)

    if not relevant_signals:
        return None

    # Return most recent
    relevant_signals.sort(key=lambda x: x["timestamp"], reverse=True)
    return relevant_signals[0]


def check_discord_conflict(symbol: str, side: str, setup: str) -> tuple[bool, int, str]:
    """
    Check if proposed trade conflicts with Discord signals (e.g., Discord says bounce, agent wants to short).

    Args:
        symbol: SPY or QQQ
        side: "buy" or "sell"
        setup: Setup type (e.g., "overbought_reversal")

    Returns:
        (has_conflict, penalty_points, conflict_description)
    """
    signal = get_signal_for_symbol(symbol)

    if not signal:
        return False, 0, "No Discord signal to conflict with"

    sig_data = signal.get("signals", {})
    sentiment = sig_data.get("sentiment", "neutral")
    key_insights = sig_data.get("key_insights", sig_data.get("key_points", []))

    # Check for explicit conflict signals in the text
    signal_text = " ".join(key_insights).lower() if key_insights else ""
    raw_text = signal.get("raw_text", "").lower()
    full_text = signal_text + " " + raw_text

    # Patterns that indicate expecting a bounce/reversal UP
    bounce_patterns = [
        "expecting bounce", "bounce expected", "expect bounce", "looking for bounce",
        "should bounce", "bounce from", "support here", "reversal up",
        "buy the dip", "dca", "adding", "good entry"
    ]

    # Patterns that indicate expecting drop/weakness
    drop_patterns = [
        "expecting drop", "more downside", "break down", "sell rally",
        "resistance", "topping", "distribution", "expecting lower", "heading lower"
    ]

    has_bounce_signal = any(pattern in full_text for pattern in bounce_patterns)
    has_drop_signal = any(pattern in full_text for pattern in drop_patterns)

    # Check for direct conflicts
    conflict = False
    penalty = 0
    description = ""

    # CONFLICT: Discord expects bounce but agent wants to SHORT
    if has_bounce_signal and side == "sell":
        conflict = True
        penalty = -25  # Heavy penalty
        description = f"⚠️ DISCORD CONFLICT: Discord expects bounce, but agent wants to SHORT. Signal: '{key_insights[0][:100] if key_insights else raw_text[:100]}...'"

    # CONFLICT: Discord expects drop but agent wants to LONG
    elif has_drop_signal and side == "buy":
        conflict = True
        penalty = -25  # Heavy penalty
        description = f"⚠️ DISCORD CONFLICT: Discord expects drop, but agent wants to LONG. Signal: '{key_insights[0][:100] if key_insights else raw_text[:100]}...'"

    # CONFLICT: Reversal setup against Discord directional bias
    elif setup in ("overbought_reversal", "oversold_reversal"):
        if side == "sell" and sentiment == "bullish":
            conflict = True
            penalty = -15
            description = f"⚠️ REVERSAL CONFLICT: Shorting overbought but Discord is BULLISH ({sentiment})"
        elif side == "buy" and sentiment == "bearish":
            conflict = True
            penalty = -15
            description = f"⚠️ REVERSAL CONFLICT: Buying oversold but Discord is BEARISH ({sentiment})"

    # General sentiment mismatch (lighter penalty)
    elif (side == "buy" and sentiment == "bearish") or (side == "sell" and sentiment == "bullish"):
        conflict = True
        penalty = -10
        description = f"⚠️ Discord sentiment {sentiment.upper()}, agent wants to {side.upper()}"

    return conflict, penalty, description


def calculate_signal_bonus(symbol: str, side: str, price: float) -> tuple[int, str]:
    """
    Calculate A+ scoring bonus based on Discord signals.

    Args:
        symbol: SPY or QQQ
        side: "buy" or "sell"
        price: Current price

    Returns:
        (bonus_points, reason_text)
    """
    signal = get_signal_for_symbol(symbol)

    if not signal:
        return 0, "No active Discord signal"

    sig_data = signal.get("signals", {})
    sentiment = sig_data.get("sentiment", "neutral")
    confidence = sig_data.get("confidence", "medium")
    price_targets = sig_data.get("price_targets", {}).get(symbol, {})

    bonus = 0
    reasons = []

    # Sentiment alignment
    if side == "buy" and sentiment == "bullish":
        if confidence == "high":
            bonus += 10
            reasons.append("High-confidence bullish signal")
        elif confidence == "medium":
            bonus += 5
            reasons.append("Medium-confidence bullish signal")
    elif side == "sell" and sentiment == "bearish":
        if confidence == "high":
            bonus += 10
            reasons.append("High-confidence bearish signal")
        elif confidence == "medium":
            bonus += 5
            reasons.append("Medium-confidence bearish signal")
    elif (side == "buy" and sentiment == "bearish") or (side == "sell" and sentiment == "bullish"):
        # Counter-signal penalty (now handled by check_discord_conflict)
        bonus -= 5
        reasons.append("⚠ Counter to Discord sentiment")

    # Price level alignment
    supports = price_targets.get("support", [])
    resistances = price_targets.get("resistance", [])

    for support_level in supports:
        # If buying near support
        if side == "buy" and abs(price - support_level) / price < 0.01:  # Within 1%
            bonus += 8
            reasons.append(f"At support level ${support_level:.2f}")

    for resistance_level in resistances:
        # If selling near resistance
        if side == "sell" and abs(price - resistance_level) / price < 0.01:  # Within 1%
            bonus += 8
            reasons.append(f"At resistance level ${resistance_level:.2f}")

    # Risk factor warnings
    risk_factors = sig_data.get("risk_factors", [])
    if risk_factors:
        reasons.append(f"⚠ Risk factors: {len(risk_factors)} mentioned")

    reason_text = " | ".join(reasons) if reasons else "No alignment"

    return bonus, reason_text


def get_signal_summary(symbol: str) -> str:
    """
    Get a human-readable summary of active Discord signals for a symbol.
    """
    signal = get_signal_for_symbol(symbol)

    if not signal:
        return "No active Discord signals"

    sig_data = signal.get("signals", {})
    sentiment = sig_data.get("sentiment", "neutral")
    confidence = sig_data.get("confidence", "medium")

    # Get key insights
    key_insights = sig_data.get("key_insights", sig_data.get("key_points", []))
    first_insight = key_insights[0] if key_insights else "No details"

    # Truncate if too long
    if len(first_insight) > 100:
        first_insight = first_insight[:97] + "..."

    age_minutes = (datetime.now(ET) - datetime.fromisoformat(signal["timestamp"])).total_seconds() / 60

    return f"{sentiment.upper()} ({confidence} conf.) - {first_insight} [{int(age_minutes)}m ago]"


def log_signal_usage(symbol: str, trade_id: str):
    """
    Log that a Discord signal influenced a trade.

    Updates the signal record to track which trades it affected.
    """
    signal = get_signal_for_symbol(symbol)
    if not signal:
        return

    # Load all signals
    if not SIGNALS_FILE.exists():
        return

    with open(SIGNALS_FILE) as f:
        data = json.load(f)

    # Find and update the signal
    for sig in data.get("active_signals", []):
        if sig.get("notification_id") == signal.get("notification_id"):
            if "applied_to_trades" not in sig:
                sig["applied_to_trades"] = []
            sig["applied_to_trades"].append({
                "trade_id": trade_id,
                "symbol": symbol,
                "timestamp": datetime.now(ET).isoformat()
            })
            break

    # Save updated data
    with open(SIGNALS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Backtesting Support - Historical Signal Loading
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_historical_signals():
    """
    Load all historical Discord signals from the archive.

    Returns list of signal records sorted by timestamp.
    """
    if not SIGNALS_HISTORY.exists():
        return []

    signals = []
    try:
        with open(SIGNALS_HISTORY) as f:
            for line in f:
                if line.strip():
                    signals.append(json.loads(line))

        # Sort by timestamp
        signals.sort(key=lambda x: x.get("timestamp", ""))
        return signals

    except Exception as e:
        print(f"  ⚠ Error loading historical signals: {e}")
        return []


def get_historical_signal_for_time(symbol: str, target_time: datetime):
    """
    Get the most recent Discord signal for a symbol at a given historical time.

    For backtesting - finds signals that were active at target_time.

    Args:
        symbol: SPY or QQQ
        target_time: The historical moment to check (timezone-aware)

    Returns:
        Signal dict or None if no active signal at that time
    """
    historical_signals = load_historical_signals()

    if not historical_signals:
        return None

    # Find signals that were active at target_time
    # (created before target_time, expires after target_time)
    relevant_signals = []

    for sig in historical_signals:
        sig_symbols = sig.get("signals", {}).get("symbols", [])

        if symbol not in sig_symbols:
            continue

        # Check if signal was active at target_time
        try:
            signal_timestamp = datetime.fromisoformat(sig["timestamp"])
            expires_at = datetime.fromisoformat(sig["expires_at"])

            # Ensure timezone awareness
            if signal_timestamp.tzinfo is None:
                signal_timestamp = signal_timestamp.replace(tzinfo=ET)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=ET)
            if target_time.tzinfo is None:
                target_time = target_time.replace(tzinfo=ET)

            # Signal must be created before target time and not yet expired
            if signal_timestamp <= target_time < expires_at:
                relevant_signals.append(sig)

        except (ValueError, KeyError) as e:
            # Skip malformed signals
            continue

    if not relevant_signals:
        return None

    # Return most recent signal that was active at target_time
    relevant_signals.sort(key=lambda x: x["timestamp"], reverse=True)
    return relevant_signals[0]


def calculate_historical_signal_bonus(symbol: str, side: str, price: float, target_time: datetime) -> tuple[int, str]:
    """
    Calculate Discord signal bonus for backtesting at a historical time.

    Same logic as calculate_signal_bonus() but uses historical signals.

    Args:
        symbol: SPY or QQQ
        side: "buy" or "sell"
        price: Price at that moment
        target_time: Historical moment (timezone-aware datetime)

    Returns:
        (bonus_points, reason_text)
    """
    signal = get_historical_signal_for_time(symbol, target_time)

    if not signal:
        return 0, "No active Discord signal"

    sig_data = signal.get("signals", {})
    sentiment = sig_data.get("sentiment", "neutral")
    confidence = sig_data.get("confidence", "medium")
    price_targets = sig_data.get("price_targets", {}).get(symbol, {})

    bonus = 0
    reasons = []

    # Sentiment alignment
    if side == "buy" and sentiment == "bullish":
        if confidence == "high":
            bonus += 10
            reasons.append("High-confidence bullish signal")
        elif confidence == "medium":
            bonus += 5
            reasons.append("Medium-confidence bullish signal")
    elif side == "sell" and sentiment == "bearish":
        if confidence == "high":
            bonus += 10
            reasons.append("High-confidence bearish signal")
        elif confidence == "medium":
            bonus += 5
            reasons.append("Medium-confidence bearish signal")
    elif (side == "buy" and sentiment == "bearish") or (side == "sell" and sentiment == "bullish"):
        # Counter-signal penalty
        bonus -= 5
        reasons.append("⚠ Counter to Discord sentiment")

    # Price level alignment
    supports = price_targets.get("support", [])
    resistances = price_targets.get("resistance", [])

    for support_level in supports:
        # If buying near support
        if side == "buy" and abs(price - support_level) / price < 0.01:  # Within 1%
            bonus += 8
            reasons.append(f"At support ${support_level:.2f}")

    for resistance_level in resistances:
        # If selling near resistance
        if side == "sell" and abs(price - resistance_level) / price < 0.01:  # Within 1%
            bonus += 8
            reasons.append(f"At resistance ${resistance_level:.2f}")

    # Risk factor warnings
    risk_factors = sig_data.get("risk_factors", [])
    if risk_factors:
        reasons.append(f"⚠ {len(risk_factors)} risk factors")

    reason_text = " | ".join(reasons) if reasons else "No alignment"

    return bonus, reason_text


if __name__ == "__main__":
    # Test the integration
    print("Testing Discord Integration:\n")

    signals = load_active_signals()
    print(f"Active signals: {len(signals)}")

    for symbol in ["SPY", "QQQ"]:
        print(f"\n{symbol}:")
        print(f"  Summary: {get_signal_summary(symbol)}")

        for side in ["buy", "sell"]:
            bonus, reason = calculate_signal_bonus(symbol, side, 650 if symbol == "SPY" else 580)
            print(f"  {side.upper()}: +{bonus} points - {reason}")
