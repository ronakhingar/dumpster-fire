#!/usr/bin/env python3
"""
Backtest engine that integrates with analyze.py for real setup detection.

Provides a modified analyze() that works with pre-loaded historical bars
to avoid look-ahead bias during backtesting.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from indicator_engine import (
    compute_ema, compute_rsi, compute_macd, compute_atr, compute_vwap,
)


# ─── Copy of analyze.py helper functions ─────────────────────────────────────

def _last(series):
    for v in reversed(series):
        if v is not None:
            return v
    return None


def _prev(series, offset=1):
    """Return the value *offset* positions before the last defined value."""
    found = 0
    for v in reversed(series):
        if v is not None:
            if found == offset:
                return v
            found += 1
    return None


def _trend_label(price, ema9, ema21, ema50):
    if None in (ema9, ema21, ema50):
        return "unknown"
    if price > ema9 > ema21 > ema50:
        return "strong_uptrend"
    if price > ema21 > ema50:
        return "uptrend"
    if price < ema9 < ema21 < ema50:
        return "strong_downtrend"
    if price < ema21 < ema50:
        return "downtrend"
    if ema9 > ema21 and price < ema9:
        return "pullback_in_uptrend"
    if ema9 < ema21 and price > ema9:
        return "bounce_in_downtrend"
    return "choppy"


def _detect_setup(trend, rsi, macd_hist, macd_hist_prev, price, ema9, ema21):
    """Return (setup_name, side) or (None, None)."""
    if rsi is None or macd_hist is None:
        return None, None

    if trend == "pullback_in_uptrend" and rsi < 45 and macd_hist < 0:
        return "ema_pullback_long", "buy"

    if trend == "bounce_in_downtrend" and rsi > 55 and macd_hist > 0:
        return "ema_bounce_short", "sell"

    if trend in ("strong_downtrend", "downtrend") and rsi <= 30:
        if macd_hist_prev is not None and macd_hist > macd_hist_prev:
            return "oversold_reversal", "buy"

    if trend in ("strong_uptrend", "uptrend") and rsi >= 70:
        if macd_hist_prev is not None and macd_hist < macd_hist_prev:
            return "overbought_reversal", "sell"

    if ema9 is not None and ema21 is not None:
        if trend in ("uptrend", "strong_uptrend") and abs(price - ema9) / ema9 < 0.003:
            return "ema9_touch_long", "buy"
        if trend in ("downtrend", "strong_downtrend") and abs(price - ema9) / ema9 < 0.003:
            return "ema9_touch_short", "sell"

    return None, None


def _compute_trade_levels(side, price, atr, rr_target=2.0):
    """Derive entry, stop, target from ATR."""
    if atr is None:
        return {"entry": None, "stop_loss": None, "take_profit": None}

    stop_distance = round(atr * 1.5, 2)

    if side == "buy":
        entry = round(price, 2)
        stop = round(entry - stop_distance, 2)
        target = round(entry + stop_distance * rr_target, 2)
    elif side == "sell":
        entry = round(price, 2)
        stop = round(entry + stop_distance, 2)
        target = round(entry - stop_distance * rr_target, 2)
    else:
        return {"entry": None, "stop_loss": None, "take_profit": None}

    return {
        "entry": entry,
        "stop_loss": stop,
        "take_profit": target,
    }


# ─── Backtest-Compatible Analysis ────────────────────────────────────────────

def analyze_with_bars(bars: list[dict], symbol: str = "SPY") -> dict:
    """
    Analyze pre-loaded bars without fetching new data.

    Used for backtesting to avoid look-ahead bias.

    Args:
        bars: List of bar dicts (must have: time, open, high, low, close, volume)
        symbol: Symbol name for reference

    Returns:
        {
            "symbol": "SPY",
            "setup": "ema_pullback_long" or None,
            "side": "buy" | "sell" | None,
            "trend": "strong_uptrend" | ...,
            "entry": 510.50,
            "stop": 508.50,
            "target": 514.50,
            "score": 75,  # Simple score 0-100
            "indicators": {...}
        }
    """
    if len(bars) < 50:
        return {
            "symbol": symbol,
            "setup": None,
            "side": None,
            "trend": "unknown",
            "entry": None,
            "stop": None,
            "target": None,
            "score": 0,
            "indicators": {},
            "error": f"Insufficient bars ({len(bars)}), need >= 50"
        }

    # ── Compute indicators ───────────────────────────────────────────────
    ema9_series  = compute_ema(bars, 9)
    ema21_series = compute_ema(bars, 21)
    ema50_series = compute_ema(bars, 50)
    rsi_series   = compute_rsi(bars, 14)
    macd_series  = compute_macd(bars)
    atr_series   = compute_atr(bars, 14)
    vwap_series  = compute_vwap(bars)

    price = float(bars[-1]["close"])
    ema9  = _last(ema9_series)
    ema21 = _last(ema21_series)
    ema50 = _last(ema50_series)
    rsi   = _last(rsi_series)
    macd  = _last(macd_series)
    atr   = _last(atr_series)
    vwap  = _last(vwap_series)

    macd_hist      = macd["histogram"] if macd else None
    macd_hist_prev = _prev(macd_series)
    macd_hist_prev = macd_hist_prev["histogram"] if macd_hist_prev else None

    # ── Trend + setup detection ──────────────────────────────────────────
    trend = _trend_label(price, ema9, ema21, ema50)
    setup, side = _detect_setup(trend, rsi, macd_hist, macd_hist_prev, price, ema9, ema21)

    # ── Trade levels ─────────────────────────────────────────────────────
    trade = _compute_trade_levels(side, price, atr)

    # ── Simple scoring ───────────────────────────────────────────────────
    score = 0
    if setup and side:
        score = 50  # Base score for any setup

        # Trend alignment
        if side == "buy" and trend in ("strong_uptrend", "uptrend", "pullback_in_uptrend"):
            score += 20
        elif side == "sell" and trend in ("strong_downtrend", "downtrend", "bounce_in_downtrend"):
            score += 20

        # RSI confirmation
        if side == "buy" and rsi and rsi < 45:
            score += 15
        elif side == "sell" and rsi and rsi > 55:
            score += 15

        # MACD confirmation
        if side == "buy" and macd_hist and macd_hist > 0:
            score += 15
        elif side == "sell" and macd_hist and macd_hist < 0:
            score += 15

    return {
        "symbol": symbol,
        "setup": setup,
        "side": side,
        "trend": trend,
        "entry": trade.get("entry"),
        "stop": trade.get("stop_loss"),
        "target": trade.get("take_profit"),
        "score": min(100, max(0, score)),
        "indicators": {
            "price": price,
            "ema9": ema9,
            "ema21": ema21,
            "ema50": ema50,
            "rsi": rsi,
            "macd_histogram": macd_hist,
            "atr": atr,
            "vwap": vwap,
        }
    }
