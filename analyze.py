#!/usr/bin/env python3
"""
analyze(symbol) — full trade analysis with deterministic indicators.

Fetches bars, computes every indicator, applies rule-based detection for
trend state / setups / entry-stop-target levels, and returns the complete
schema an LLM (or human) needs to make a decision.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from alpaca_trader import get_historical_bars, get_quote, ALLOWED_SYMBOLS
from indicator_engine import (
    compute_ema, compute_rsi, compute_macd, compute_atr, compute_vwap,
)
from journal import log_analysis


# ─── Internals ───────────────────────────────────────────────────────────────

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


def _fmt(v):
    return f"${v:,.2f}" if v is not None else "—"


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

    if trend == "strong_downtrend" and rsi <= 30:
        return "oversold_watch", None

    if trend == "strong_uptrend" and rsi >= 70:
        return "overbought_watch", None

    if ema9 is not None and ema21 is not None:
        if trend in ("uptrend", "strong_uptrend") and abs(price - ema9) / ema9 < 0.003:
            return "ema9_touch_long", "buy"
        if trend in ("downtrend", "strong_downtrend") and abs(price - ema9) / ema9 < 0.003:
            return "ema9_touch_short", "sell"

    return None, None


def _build_reasons(side, price, ema9, ema21, ema50, rsi, macd, atr, vwap):
    """Generate specific, indicator-backed reasons for and against the trade."""
    reasons_for = []
    reasons_against = []

    if side == "buy":
        if ema9 and price > ema9:
            reasons_for.append(f"Price ${price:,.2f} above EMA-9 ${ema9:,.2f} — short-term momentum supports entry")
        if ema21 and ema50 and ema21 > ema50:
            reasons_for.append(f"EMA-21 (${ema21:,.2f}) > EMA-50 (${ema50:,.2f}) — intermediate trend bullish")
        if rsi and rsi < 40:
            reasons_for.append(f"RSI {rsi:.1f} approaching oversold — mean reversion upside likely")
        if rsi and 40 <= rsi <= 55:
            reasons_for.append(f"RSI {rsi:.1f} mid-range — room to run higher before overbought")
        if macd and macd["histogram"] > 0:
            reasons_for.append(f"MACD histogram +{macd['histogram']:.4f} — bullish momentum")
        if macd and macd["histogram"] < 0 and macd["macd"] > macd["signal"]:
            reasons_for.append(f"MACD line above signal — bearish momentum fading")
        if vwap and price < vwap:
            pct = (vwap - price) / vwap * 100
            reasons_for.append(f"Price {pct:.1f}% below VWAP ${vwap:,.2f} — discount to fair value")

        if ema9 and price < ema9:
            reasons_against.append(f"Price below EMA-9 (${ema9:,.2f}) — short-term trend still down")
        if ema50 and price < ema50:
            reasons_against.append(f"Price below EMA-50 (${ema50:,.2f}) — major trend resistance overhead")
        if rsi and rsi > 65:
            reasons_against.append(f"RSI {rsi:.1f} already elevated — limited upside before overbought")
        if macd and macd["histogram"] < 0:
            reasons_against.append(f"MACD histogram {macd['histogram']:.4f} negative — momentum still bearish")
        if atr and atr > price * 0.025:
            reasons_against.append(f"ATR ${atr:,.2f} ({atr/price*100:.1f}% of price) — high volatility increases risk")

    elif side == "sell":
        if ema9 and price < ema9:
            reasons_for.append(f"Price ${price:,.2f} below EMA-9 ${ema9:,.2f} — short-term trend bearish")
        if ema21 and ema50 and ema21 < ema50:
            reasons_for.append(f"EMA-21 (${ema21:,.2f}) < EMA-50 (${ema50:,.2f}) — intermediate trend bearish")
        if rsi and rsi > 60:
            reasons_for.append(f"RSI {rsi:.1f} elevated — mean reversion downside likely")
        if macd and macd["histogram"] < 0:
            reasons_for.append(f"MACD histogram {macd['histogram']:.4f} — bearish momentum confirmed")
        if vwap and price > vwap:
            pct = (price - vwap) / vwap * 100
            reasons_for.append(f"Price {pct:.1f}% above VWAP ${vwap:,.2f} — premium to fair value")

        if ema9 and price > ema9:
            reasons_against.append(f"Price above EMA-9 (${ema9:,.2f}) — short-term strength still intact")
        if rsi and rsi < 35:
            reasons_against.append(f"RSI {rsi:.1f} already oversold — limited downside, bounce risk")
        if macd and macd["histogram"] > 0:
            reasons_against.append(f"MACD histogram +{macd['histogram']:.4f} — momentum still bullish")
        if atr and atr > price * 0.025:
            reasons_against.append(f"ATR ${atr:,.2f} ({atr/price*100:.1f}% of price) — volatility could whipsaw the short")

    return reasons_for, reasons_against


def _compute_trade_levels(side, price, atr, rr_target=2.0):
    """Derive entry, stop, target from ATR. Returns dict or None-filled dict."""
    if atr is None:
        return {"entry": None, "stop_loss": None, "take_profit": None,
                "risk_reward": None, "position_size_suggestion": None}

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
        return {"entry": None, "stop_loss": None, "take_profit": None,
                "risk_reward": None, "position_size_suggestion": None}

    return {
        "entry": entry,
        "stop_loss": stop,
        "take_profit": target,
        "risk_reward": rr_target,
        "position_size_suggestion": f"Risk ${stop_distance:.2f}/share (1.5x ATR). "
                                    f"For $500 risk: {int(500 / stop_distance)} shares.",
    }


def _confidence(setup, side, trend, rsi, macd, atr, price, ema9):
    """Heuristic confidence score 0-100."""
    if setup is None or side is None:
        return 0

    score = 50

    if side == "buy":
        if trend in ("strong_uptrend", "uptrend", "pullback_in_uptrend"):
            score += 15
        elif trend in ("strong_downtrend",):
            score -= 15

        if rsi and rsi < 35:
            score += 10
        if rsi and rsi > 65:
            score -= 10

        if macd and macd["histogram"] > 0:
            score += 10
        elif macd and macd["histogram"] < 0:
            hist_mag = abs(macd["histogram"])
            if hist_mag > 3:
                score -= 10
            else:
                score -= 5

    elif side == "sell":
        if trend in ("strong_downtrend", "downtrend", "bounce_in_downtrend"):
            score += 15
        elif trend in ("strong_uptrend",):
            score -= 15

        if rsi and rsi > 65:
            score += 10
        if rsi and rsi < 35:
            score -= 10

        if macd and macd["histogram"] < 0:
            score += 10
        elif macd and macd["histogram"] > 0:
            score -= 5

    if atr and price and atr / price > 0.025:
        score -= 5

    return max(0, min(100, score))


def _market_summary(price, ema9, ema21, ema50, rsi, macd, atr, vwap, trend):
    parts = []

    ema_positions = []
    for label, val in [("EMA-9", ema9), ("EMA-21", ema21), ("EMA-50", ema50)]:
        if val is not None:
            rel = "above" if price > val else "below"
            ema_positions.append(f"{rel} {label} (${val:,.2f})")
    if ema_positions:
        parts.append(f"Price ${price:,.2f} is {', '.join(ema_positions)}.")

    trend_words = {
        "strong_uptrend": "Strong uptrend — all EMAs stacked bullish.",
        "uptrend": "Uptrend — price holding above EMA-21/50.",
        "pullback_in_uptrend": "Pulling back within a broader uptrend.",
        "strong_downtrend": "Strong downtrend — all EMAs stacked bearish.",
        "downtrend": "Downtrend — price below EMA-21/50.",
        "bounce_in_downtrend": "Bouncing within a broader downtrend.",
        "choppy": "Choppy / range-bound — no clear trend.",
        "unknown": "Insufficient data to determine trend.",
    }
    parts.append(trend_words.get(trend, ""))

    if rsi is not None:
        if rsi <= 30:
            parts.append(f"RSI {rsi:.1f} — oversold.")
        elif rsi >= 70:
            parts.append(f"RSI {rsi:.1f} — overbought.")
        else:
            parts.append(f"RSI {rsi:.1f} — neutral zone.")

    if macd:
        direction = "bullish" if macd["histogram"] > 0 else "bearish"
        parts.append(f"MACD histogram {macd['histogram']:+.4f} — {direction} momentum.")

    if atr is not None:
        parts.append(f"ATR ${atr:,.2f} ({atr/price*100:.1f}% of price).")

    return " ".join(parts)


# ─── Public API ──────────────────────────────────────────────────────────────

def analyze(symbol: str, timeframe: str = "1Day", lookback_days: int = 90) -> dict:
    """
    Full trade analysis for a symbol.

    Fetches bars, computes indicators deterministically, detects setups via
    rules, and returns the complete analysis schema.

    Args:
        symbol:        "SPY" or "QQQ"
        timeframe:     bar size — "1Day", "1Hour", "15Min", etc.
        lookback_days: how far back to fetch (default 90 for daily)

    Returns:
        dict matching the analysis response schema
    """
    sym = symbol.upper()
    if sym not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' not allowed. Choose from: {sorted(ALLOWED_SYMBOLS)}")

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    bars = get_historical_bars(sym, timeframe, start=start, end=end)

    if len(bars) < 50:
        print(f"\n  WARNING: Only {len(bars)} bars — some indicators will be None (need ≥50).")

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

    # ── Recommendation ───────────────────────────────────────────────────
    if side and setup and trade["entry"]:
        recommendation = side
    elif setup and not side:
        recommendation = "hold"
    else:
        recommendation = "no_trade"

    # ── Confidence ───────────────────────────────────────────────────────
    conf = _confidence(setup, side, trend, rsi, macd, atr, price, ema9)

    # ── Reasons ──────────────────────────────────────────────────────────
    reasons_for, reasons_against = _build_reasons(
        side or "buy", price, ema9, ema21, ema50, rsi, macd, atr, vwap
    )

    # ── Summary ──────────────────────────────────────────────────────────
    summary_text = _market_summary(price, ema9, ema21, ema50, rsi, macd, atr, vwap, trend)

    # ── Final action ─────────────────────────────────────────────────────
    if recommendation in ("buy", "sell") and trade["entry"]:
        final_action = (
            f'{recommendation}("{sym}", qty=<SIZE>, order_type="limit", '
            f'limit_price={trade["entry"]}, time_in_force="day")  '
            f'| stop={_fmt(trade["stop_loss"])}  target={_fmt(trade["take_profit"])}'
        )
    elif recommendation == "hold":
        final_action = f"no trade — {setup} detected but no confirmed entry trigger yet"
    else:
        final_action = "no trade — no actionable setup on current bars"

    # ── Assemble schema ──────────────────────────────────────────────────
    result = {
        "symbol": sym,
        "timeframe": timeframe,
        "as_of": bars[-1]["time"],
        "market_state": {
            "price": price,
            "ema_9": round(ema9, 2) if ema9 else None,
            "ema_21": round(ema21, 2) if ema21 else None,
            "ema_50": round(ema50, 2) if ema50 else None,
            "rsi_14": round(rsi, 2) if rsi else None,
            "macd": round(macd["macd"], 4) if macd else None,
            "macd_signal": round(macd["signal"], 4) if macd else None,
            "macd_histogram": round(macd["histogram"], 4) if macd else None,
            "atr_14": round(atr, 2) if atr else None,
            "vwap": round(vwap, 2) if vwap else None,
            "summary": summary_text,
        },
        "detected_setup": setup or "none",
        "recommendation": recommendation,
        "confidence": conf,
        "trade": trade,
        "reasons_for": reasons_for,
        "reasons_against": reasons_against,
        "final_action": final_action,
    }

    _print_analysis(result)
    log_analysis(result)
    return result


# ─── Pretty print ────────────────────────────────────────────────────────────

def _print_analysis(r):
    ms = r["market_state"]
    t = r["trade"]

    print(f"\n{'═'*72}")
    print(f"  ANALYSIS: {r['symbol']}  |  {r['timeframe']}  |  {r['as_of']}")
    print(f"{'═'*72}")

    print(f"\n  MARKET STATE")
    print(f"  Price:     {_fmt(ms['price'])}")
    print(f"  EMA:       9={ms['ema_9']}  21={ms['ema_21']}  50={ms['ema_50']}")
    print(f"  RSI-14:    {ms['rsi_14']}")
    print(f"  MACD:      line={ms['macd']}  signal={ms['macd_signal']}  hist={ms['macd_histogram']}")
    print(f"  ATR-14:    {ms['atr_14']}")
    print(f"  VWAP:      {ms['vwap']}")
    print(f"  Summary:   {ms['summary']}")

    print(f"\n  SETUP:          {r['detected_setup']}")
    print(f"  RECOMMENDATION: {r['recommendation'].upper()}")
    print(f"  CONFIDENCE:     {r['confidence']}/100")

    print(f"\n  TRADE LEVELS")
    print(f"  Entry:       {_fmt(t['entry'])}")
    print(f"  Stop Loss:   {_fmt(t['stop_loss'])}")
    print(f"  Take Profit: {_fmt(t['take_profit'])}")
    print(f"  R:R:         {t['risk_reward']}")
    if t.get("position_size_suggestion"):
        print(f"  Sizing:      {t['position_size_suggestion']}")

    print(f"\n  REASONS FOR:")
    for reason in r["reasons_for"]:
        print(f"    + {reason}")
    if not r["reasons_for"]:
        print(f"    (none)")

    print(f"\n  REASONS AGAINST:")
    for reason in r["reasons_against"]:
        print(f"    - {reason}")
    if not r["reasons_against"]:
        print(f"    (none)")

    print(f"\n  FINAL ACTION:  {r['final_action']}")
    print(f"{'═'*72}\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sym = sys.argv[1].upper() if len(sys.argv) > 1 else "SPY"
    tf  = sys.argv[2] if len(sys.argv) > 2 else "1Day"
    analyze(sym, timeframe=tf)
