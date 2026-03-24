#!/usr/bin/env python3
"""
Deterministic technical indicator layer.

All functions accept a list of bar dicts (as returned by alpaca_trader.get_bars /
get_historical_bars) with keys: time, open, high, low, close, volume.

Every compute_* function returns a list the same length as the input bars.
Positions where the indicator is not yet defined are filled with None.

summarize_indicators() returns a single dict of the most recent values —
ready to be consumed by an LLM or decision layer without guessing from raw candles.
"""

from __future__ import annotations


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _closes(bars: list[dict]) -> list[float]:
    return [float(b["close"]) for b in bars]


def _ema_on_values(values: list[float], period: int) -> list[float | None]:
    """Core EMA over a plain float list. Seed with SMA of first *period* values."""
    n = len(values)
    if n < period:
        return [None] * n

    result: list[float | None] = [None] * n
    sma = sum(values[:period]) / period
    result[period - 1] = sma
    k = 2.0 / (period + 1)
    for i in range(period, n):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


# ─── Public API ──────────────────────────────────────────────────────────────

def compute_ema(bars: list[dict], period: int) -> list[float | None]:
    """
    Exponential Moving Average on close prices.

    Returns list[float|None] aligned 1:1 with bars.
    First (period-1) entries are None.
    """
    return _ema_on_values(_closes(bars), period)


def compute_rsi(bars: list[dict], period: int = 14) -> list[float | None]:
    """
    Relative Strength Index (Wilder-smoothed).

    Returns values in [0, 100].  First *period* entries are None.
    """
    closes = _closes(bars)
    n = len(closes)
    if n < period + 1:
        return [None] * n

    deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    result: list[float | None] = [None] * n

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(ag, al):
        if al == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + ag / al)

    result[period] = _rsi(avg_gain, avg_loss)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result[i + 1] = _rsi(avg_gain, avg_loss)

    return result


def compute_macd(
    bars: list[dict],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> list[dict | None]:
    """
    MACD (12/26/9 by default).

    Returns list of {macd, signal, histogram} dicts (or None where undefined).
    """
    closes = _closes(bars)
    n = len(closes)

    ema_fast = _ema_on_values(closes, fast)
    ema_slow = _ema_on_values(closes, slow)

    macd_line: list[float | None] = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    macd_defined = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    if len(macd_defined) < signal_period:
        return [None] * n

    signal_values = [v for _, v in macd_defined]
    signal_ema = _ema_on_values(signal_values, signal_period)

    result: list[dict | None] = [None] * n
    for j, (bar_idx, _) in enumerate(macd_defined):
        if signal_ema[j] is not None:
            m = macd_line[bar_idx]
            s = signal_ema[j]
            result[bar_idx] = {"macd": round(m, 4), "signal": round(s, 4), "histogram": round(m - s, 4)}

    return result


def compute_atr(bars: list[dict], period: int = 14) -> list[float | None]:
    """
    Average True Range (Wilder-smoothed).

    First *period* entries are None.
    """
    n = len(bars)
    if n < 2:
        return [None] * n

    tr: list[float] = [float(bars[0]["high"]) - float(bars[0]["low"])]
    for i in range(1, n):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])
        pc = float(bars[i - 1]["close"])
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))

    result: list[float | None] = [None] * n
    if n < period:
        return result

    result[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period

    return result


def compute_vwap(bars: list[dict]) -> list[float | None]:
    """
    Volume-Weighted Average Price (cumulative over the supplied bars).

    Pass a single session of intraday bars for a true intraday VWAP.
    For daily bars this is cumulative over the window — still useful as a
    relative anchor but not the classic intraday VWAP.
    """
    n = len(bars)
    result: list[float | None] = [None] * n
    cum_tp_vol = 0.0
    cum_vol = 0

    for i, b in enumerate(bars):
        tp = (float(b["high"]) + float(b["low"]) + float(b["close"])) / 3.0
        v = int(b["volume"])
        cum_tp_vol += tp * v
        cum_vol += v
        result[i] = round(cum_tp_vol / cum_vol, 4) if cum_vol > 0 else None

    return result


# ─── Liquidity Level Detection ────────────────────────────────────────────────

def detect_swing_levels(bars: list[dict], lookback: int = 3) -> dict:
    """
    Find swing highs and swing lows — candles where the high/low is the
    highest/lowest within `lookback` bars on each side.

    Returns {"swing_highs": [(index, price, time), ...],
             "swing_lows":  [(index, price, time), ...]}
    """
    n = len(bars)
    highs = []
    lows = []

    for i in range(lookback, n - lookback):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])

        is_swing_high = all(
            h >= float(bars[i + d]["high"])
            for d in range(-lookback, lookback + 1) if d != 0
        )
        is_swing_low = all(
            l <= float(bars[i + d]["low"])
            for d in range(-lookback, lookback + 1) if d != 0
        )

        if is_swing_high:
            highs.append((i, round(h, 2), bars[i]["time"]))
        if is_swing_low:
            lows.append((i, round(l, 2), bars[i]["time"]))

    return {"swing_highs": highs, "swing_lows": lows}


def detect_equal_levels(bars: list[dict], tolerance_pct: float = 0.002) -> dict:
    """
    Find equal highs and equal lows — two or more bars with highs/lows
    within `tolerance_pct` of each other. These are liquidity pools where
    stops accumulate.

    Returns {"equal_highs": [(price, count, bar_times), ...],
             "equal_lows":  [(price, count, bar_times), ...]}
    sorted by count (most touches first).
    """
    from collections import defaultdict

    n = len(bars)
    if n < 2:
        return {"equal_highs": [], "equal_lows": []}

    def _cluster(values_with_meta, tol_pct):
        if not values_with_meta:
            return []
        sorted_vals = sorted(values_with_meta, key=lambda x: x[0])
        clusters = []
        current = [sorted_vals[0]]

        for i in range(1, len(sorted_vals)):
            price, _ = sorted_vals[i]
            anchor = current[0][0]
            if anchor > 0 and abs(price - anchor) / anchor <= tol_pct:
                current.append(sorted_vals[i])
            else:
                if len(current) >= 2:
                    avg_price = round(sum(p for p, _ in current) / len(current), 2)
                    times = [t for _, t in current]
                    clusters.append((avg_price, len(current), times))
                current = [sorted_vals[i]]

        if len(current) >= 2:
            avg_price = round(sum(p for p, _ in current) / len(current), 2)
            times = [t for _, t in current]
            clusters.append((avg_price, len(current), times))

        return sorted(clusters, key=lambda x: -x[1])

    highs = [(float(b["high"]), b["time"]) for b in bars]
    lows = [(float(b["low"]), b["time"]) for b in bars]

    return {
        "equal_highs": _cluster(highs, tolerance_pct),
        "equal_lows": _cluster(lows, tolerance_pct),
    }


def detect_weekly_liquidity(weekly_bars: list[dict], current_price: float) -> dict:
    """
    Build the weekly liquidity map from weekly bars.

    Identifies:
      - Prior week high/low (PWH/PWL)
      - Current week high/low developing
      - Swing highs/lows on the weekly
      - Equal highs/lows (stacked liquidity)
      - Weekly FVGs (gaps between non-adjacent candle wicks)
      - Nearest liquidity levels above and below current price

    Args:
        weekly_bars: list of weekly bar dicts
        current_price: latest price for proximity calculations

    Returns dict with all identified levels and proximity info.
    """
    if len(weekly_bars) < 3:
        return {"levels": [], "nearest_above": None, "nearest_below": None,
                "pwh": None, "pwl": None}

    levels = []

    # Prior week high/low
    pw = weekly_bars[-2]
    pwh = round(float(pw["high"]), 2)
    pwl = round(float(pw["low"]), 2)
    levels.append({"price": pwh, "type": "pwh", "label": "Prior Week High"})
    levels.append({"price": pwl, "type": "pwl", "label": "Prior Week Low"})

    # 2-weeks-ago high/low
    if len(weekly_bars) >= 3:
        pw2 = weekly_bars[-3]
        levels.append({"price": round(float(pw2["high"]), 2), "type": "pw2h",
                        "label": "2-Week-Ago High"})
        levels.append({"price": round(float(pw2["low"]), 2), "type": "pw2l",
                        "label": "2-Week-Ago Low"})

    # Current week developing H/L
    cw = weekly_bars[-1]
    cwh = round(float(cw["high"]), 2)
    cwl = round(float(cw["low"]), 2)

    # Swing levels on weekly
    swings = detect_swing_levels(weekly_bars, lookback=2)
    for _, price, time in swings["swing_highs"][-5:]:
        levels.append({"price": price, "type": "weekly_swing_high",
                        "label": f"Weekly Swing High ({time})"})
    for _, price, time in swings["swing_lows"][-5:]:
        levels.append({"price": price, "type": "weekly_swing_low",
                        "label": f"Weekly Swing Low ({time})"})

    # Equal highs/lows on weekly
    equals = detect_equal_levels(weekly_bars, tolerance_pct=0.003)
    for price, count, times in equals["equal_highs"][:3]:
        levels.append({"price": price, "type": "equal_highs",
                        "label": f"Equal Highs x{count} (liquidity pool)"})
    for price, count, times in equals["equal_lows"][:3]:
        levels.append({"price": price, "type": "equal_lows",
                        "label": f"Equal Lows x{count} (liquidity pool)"})

    # Weekly FVGs — gap between bar[i] high and bar[i+2] low (bullish)
    #               or bar[i] low and bar[i+2] high (bearish)
    for i in range(len(weekly_bars) - 2):
        b0_high = float(weekly_bars[i]["high"])
        b0_low = float(weekly_bars[i]["low"])
        b2_high = float(weekly_bars[i + 2]["high"])
        b2_low = float(weekly_bars[i + 2]["low"])

        if b2_low > b0_high:
            gap_mid = round((b2_low + b0_high) / 2, 2)
            gap_pct = (b2_low - b0_high) / b0_high
            if gap_pct > 0.003:
                levels.append({"price": gap_mid, "type": "weekly_fvg_bullish",
                                "label": f"Weekly Bullish FVG ({weekly_bars[i+1]['time']})"})
        elif b0_low > b2_high:
            gap_mid = round((b0_low + b2_high) / 2, 2)
            gap_pct = (b0_low - b2_high) / b2_high
            if gap_pct > 0.003:
                levels.append({"price": gap_mid, "type": "weekly_fvg_bearish",
                                "label": f"Weekly Bearish FVG ({weekly_bars[i+1]['time']})"})

    # Deduplicate levels within 0.1% of each other
    unique = []
    for lvl in sorted(levels, key=lambda x: x["price"]):
        if not unique or abs(lvl["price"] - unique[-1]["price"]) / max(lvl["price"], 0.01) > 0.001:
            unique.append(lvl)
        else:
            if lvl["type"] in ("pwh", "pwl", "equal_highs", "equal_lows"):
                unique[-1] = lvl

    # Find nearest above and below current price
    above = [l for l in unique if l["price"] > current_price]
    below = [l for l in unique if l["price"] < current_price]
    nearest_above = min(above, key=lambda x: x["price"]) if above else None
    nearest_below = max(below, key=lambda x: x["price"]) if below else None

    # Proximity scoring
    for lvl in unique:
        dist_pct = abs(lvl["price"] - current_price) / current_price * 100
        lvl["distance_pct"] = round(dist_pct, 2)
        lvl["proximity"] = (
            "AT_LEVEL" if dist_pct < 0.15 else
            "VERY_CLOSE" if dist_pct < 0.5 else
            "CLOSE" if dist_pct < 1.0 else
            "NEARBY" if dist_pct < 2.0 else
            "FAR"
        )

    return {
        "levels": unique,
        "nearest_above": nearest_above,
        "nearest_below": nearest_below,
        "pwh": pwh,
        "pwl": pwl,
        "current_week_high": cwh,
        "current_week_low": cwl,
    }


# ─── Summary ─────────────────────────────────────────────────────────────────

def summarize_indicators(bars: list[dict]) -> dict:
    """
    Compute all indicators and return only the latest value of each.

    Intended to be the single deterministic snapshot handed to an LLM so it
    never has to infer moving averages or RSI from raw numbers.

    Returns dict with keys:
        price, ema_9, ema_21, ema_50, rsi_14,
        macd  {macd, signal, histogram},
        atr_14, vwap,
        bar_count, time
    """
    if not bars:
        return {}

    def _last(series):
        for v in reversed(series):
            if v is not None:
                return v
        return None

    latest = bars[-1]
    ema9  = _last(compute_ema(bars, 9))
    ema21 = _last(compute_ema(bars, 21))
    ema50 = _last(compute_ema(bars, 50))
    rsi   = _last(compute_rsi(bars, 14))
    macd  = _last(compute_macd(bars))
    atr   = _last(compute_atr(bars, 14))
    vwap  = _last(compute_vwap(bars))

    summary = {
        "time":      latest["time"],
        "price":     float(latest["close"]),
        "ema_9":     round(ema9, 2) if ema9 is not None else None,
        "ema_21":    round(ema21, 2) if ema21 is not None else None,
        "ema_50":    round(ema50, 2) if ema50 is not None else None,
        "rsi_14":    round(rsi, 2) if rsi is not None else None,
        "macd":      macd,
        "atr_14":    round(atr, 2) if atr is not None else None,
        "vwap":      round(vwap, 2) if vwap is not None else None,
        "bar_count": len(bars),
    }

    print(f"\n  ── Indicator Summary ({summary['time']}) ──")
    print(f"  Price:  {_fmt(summary['price'])}")
    print(f"  EMA:    9={_nf(summary['ema_9'])}   21={_nf(summary['ema_21'])}   50={_nf(summary['ema_50'])}")
    print(f"  RSI:    {_nf(summary['rsi_14'])}")
    if macd:
        print(f"  MACD:   line={macd['macd']}  signal={macd['signal']}  hist={macd['histogram']}")
    else:
        print(f"  MACD:   —  (need ≥35 bars)")
    print(f"  ATR:    {_nf(summary['atr_14'])}")
    print(f"  VWAP:   {_nf(summary['vwap'])}")
    print(f"  Bars:   {summary['bar_count']}")

    return summary


def _fmt(v):
    return f"${v:,.2f}" if v is not None else "—"

def _nf(v):
    return f"{v}" if v is not None else "—"


# ─── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from alpaca_trader import get_bars, get_historical_bars

    print("Fetching 60 daily bars for SPY...")
    bars = get_historical_bars("SPY", "1Day",
                               start="2026-01-02", end="2026-03-23")

    print("\n── Full indicator run ──")
    s = summarize_indicators(bars)

    print("\n── RSI series (last 10) ──")
    rsi = compute_rsi(bars, 14)
    for b, r in zip(bars[-10:], rsi[-10:]):
        rv = f"{r:.2f}" if r is not None else "—"
        print(f"  {b['time']:<28} close={_fmt(float(b['close']))}  RSI={rv}")

    print("\n── MACD series (last 10) ──")
    macd = compute_macd(bars)
    for b, m in zip(bars[-10:], macd[-10:]):
        if m:
            print(f"  {b['time']:<28} macd={m['macd']:>8.4f}  signal={m['signal']:>8.4f}  hist={m['histogram']:>8.4f}")
        else:
            print(f"  {b['time']:<28} —")
