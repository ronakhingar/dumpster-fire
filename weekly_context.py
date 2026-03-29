#!/usr/bin/env python3
"""
Weekly Market Context Analysis

Runs once per week (Saturdays) to assess macro conditions:
  - FOMC meeting detection for the upcoming week
  - Daily chart trend analysis (50/100/200 day MAs)
  - VIX (fear gauge) level
  - Market regime classification

Output: journal/weekly_context.json with scoring modifiers
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca_trader import get_historical_bars, get_quote

ET = ZoneInfo("America/New_York")
CONTEXT_FILE = Path(__file__).parent / "journal" / "weekly_context.json"

# 2026 FOMC Meeting Schedule (from federalreserve.gov)
# Format: (month, day) tuples for decision announcement dates
FOMC_2026_SCHEDULE = [
    (1, 29),   # January 28-29, 2026
    (3, 18),   # March 17-18, 2026
    (5, 6),    # May 5-6, 2026
    (6, 17),   # June 16-17, 2026
    (7, 29),   # July 28-29, 2026
    (9, 16),   # September 15-16, 2026
    (11, 4),   # November 3-4, 2026
    (12, 16),  # December 15-16, 2026
]


def detect_fomc_next_week() -> dict:
    """
    Check if there's an FOMC meeting in the next 7 days.

    Returns:
        {
            "has_fomc": bool,
            "date": str or None,
            "days_until": int or None,
            "impact": "high" | "medium" | "low"
        }
    """
    today = datetime.now(ET).date()
    next_week = today + timedelta(days=7)

    for month, day in FOMC_2026_SCHEDULE:
        fomc_date = datetime(2026, month, day, tzinfo=ET).date()

        if today < fomc_date <= next_week:
            days_until = (fomc_date - today).days

            # Impact assessment based on proximity
            if days_until <= 2:
                impact = "high"
            elif days_until <= 4:
                impact = "medium"
            else:
                impact = "low"

            return {
                "has_fomc": True,
                "date": fomc_date.isoformat(),
                "days_until": days_until,
                "impact": impact,
                "note": f"FOMC meeting {fomc_date.strftime('%B %d, %Y')} ({days_until} days away)"
            }

    return {
        "has_fomc": False,
        "date": None,
        "days_until": None,
        "impact": "none",
        "note": "No FOMC meetings scheduled in the next 7 days"
    }


def analyze_daily_trend(symbol: str) -> dict:
    """
    Analyze daily chart trend and position relative to key moving averages.

    Returns:
        {
            "symbol": str,
            "price": float,
            "ma_50": float,
            "ma_100": float,
            "ma_200": float,
            "above_ma_50": bool,
            "above_ma_100": bool,
            "above_ma_200": bool,
            "trend": "strong_uptrend" | "uptrend" | "neutral" | "downtrend" | "strong_downtrend",
            "momentum": "bullish" | "neutral" | "bearish"
        }
    """
    try:
        # Fetch daily bars (need 200+ for 200-day MA)
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")
        daily_bars = get_historical_bars(symbol, "1Day", start=start_date, end=end_date)

        if not daily_bars or len(daily_bars) < 200:
            return {"error": f"Insufficient data for {symbol}"}

        # Get current price
        quote = get_quote(symbol)
        current_price = (quote["bid"] + quote["ask"]) / 2 if quote else daily_bars[-1]["close"]

        # Calculate moving averages
        closes = [bar["close"] for bar in daily_bars]

        ma_50 = sum(closes[-50:]) / 50
        ma_100 = sum(closes[-100:]) / 100
        ma_200 = sum(closes[-200:]) / 200

        # Position checks
        above_ma_50 = current_price > ma_50
        above_ma_100 = current_price > ma_100
        above_ma_200 = current_price > ma_200

        # Trend classification
        if above_ma_50 and above_ma_100 and above_ma_200:
            if ma_50 > ma_100 > ma_200:
                trend = "strong_uptrend"
                momentum = "bullish"
            else:
                trend = "uptrend"
                momentum = "bullish"
        elif not above_ma_50 and not above_ma_100 and not above_ma_200:
            if ma_50 < ma_100 < ma_200:
                trend = "strong_downtrend"
                momentum = "bearish"
            else:
                trend = "downtrend"
                momentum = "bearish"
        else:
            trend = "neutral"
            momentum = "neutral"

        # Distance from MAs (for context)
        distance_from_50 = ((current_price - ma_50) / ma_50) * 100
        distance_from_200 = ((current_price - ma_200) / ma_200) * 100

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "ma_50": round(ma_50, 2),
            "ma_100": round(ma_100, 2),
            "ma_200": round(ma_200, 2),
            "above_ma_50": above_ma_50,
            "above_ma_100": above_ma_100,
            "above_ma_200": above_ma_200,
            "distance_from_50": round(distance_from_50, 2),
            "distance_from_200": round(distance_from_200, 2),
            "trend": trend,
            "momentum": momentum,
        }

    except Exception as e:
        return {"error": f"Failed to analyze {symbol}: {e}"}


def get_vix_level() -> dict:
    """
    Fetch VIX (fear gauge) level and classify market fear.

    Note: VIX may not be available in paper trading. Using mock data or SPY-based estimate.

    Returns:
        {
            "vix": float,
            "classification": "extreme_fear" | "high_fear" | "elevated" | "normal" | "complacent",
            "note": str
        }
    """
    try:
        # VIX not available in Alpaca paper trading for SPY/QQQ only accounts
        # Use mock data for demonstration (in production, use VIX API or calculate from SPY options)

        # Mock VIX level (would be replaced with actual VIX API call)
        vix = 15.5  # Example: normal level

        if not vix:
            return {"error": "Could not fetch VIX data"}

        vix = (quote["bid"] + quote["ask"]) / 2

        # VIX classification
        if vix >= 40:
            classification = "extreme_fear"
            note = "Extreme fear - expect high volatility and whipsaws"
        elif vix >= 30:
            classification = "high_fear"
            note = "High fear - significant volatility expected"
        elif vix >= 20:
            classification = "elevated"
            note = "Elevated fear - above-normal volatility"
        elif vix >= 12:
            classification = "normal"
            note = "Normal fear levels - typical market conditions"
        else:
            classification = "complacent"
            note = "Low fear - market complacency, watch for sudden moves"

        return {
            "vix": round(vix, 2),
            "classification": classification,
            "note": note
        }

    except Exception as e:
        return {"error": f"Failed to fetch VIX: {e}"}


def classify_market_regime(spy_analysis: dict, qqq_analysis: dict, vix_data: dict,
                          fomc_data: dict, alternative_bias: dict | None = None) -> dict:
    """
    Combine all analyses into a single market regime classification.

    Returns:
        {
            "regime": str,
            "confidence": float,
            "description": str,
            "scoring_modifiers": {
                "risk_adjustment": float,  # multiply position size
                "trend_following_boost": float,  # add to trend setups
                "reversal_penalty": float,  # subtract from counter-trend
            }
        }
    """
    # Default modifiers (neutral regime)
    modifiers = {
        "risk_adjustment": 1.0,
        "trend_following_boost": 0,
        "reversal_penalty": 0,
        "volatility_factor": 1.0,
    }

    # FOMC impact
    if fomc_data["has_fomc"]:
        if fomc_data["impact"] == "high":
            modifiers["risk_adjustment"] = 0.5  # Cut position size in half
            modifiers["volatility_factor"] = 1.5
            regime = "fomc_high_uncertainty"
            description = f"FOMC meeting in {fomc_data['days_until']} days - reduce size, expect volatility"
        elif fomc_data["impact"] == "medium":
            modifiers["risk_adjustment"] = 0.75
            modifiers["volatility_factor"] = 1.2
            regime = "fomc_moderate_uncertainty"
            description = f"FOMC approaching in {fomc_data['days_until']} days - slightly cautious"
        else:
            regime = "fomc_low_impact"
            description = "FOMC later this week - monitor for positioning shifts"

    # Trend alignment
    elif spy_analysis.get("trend") == "strong_uptrend" and qqq_analysis.get("trend") == "strong_uptrend":
        modifiers["trend_following_boost"] = 5  # +5 pts for long setups
        modifiers["reversal_penalty"] = -10  # -10 pts for shorts
        regime = "strong_bullish_trend"
        description = "Both SPY and QQQ in strong uptrends - favor long setups"

    elif spy_analysis.get("trend") == "strong_downtrend" and qqq_analysis.get("trend") == "strong_downtrend":
        modifiers["trend_following_boost"] = 5  # +5 pts for short setups
        modifiers["reversal_penalty"] = -10  # -10 pts for longs
        regime = "strong_bearish_trend"
        description = "Both SPY and QQQ in strong downtrends - favor short setups"

    # VIX impact
    elif vix_data.get("classification") == "extreme_fear":
        modifiers["risk_adjustment"] = 0.6
        modifiers["volatility_factor"] = 2.0
        regime = "extreme_volatility"
        description = f"VIX at {vix_data.get('vix')} - extreme volatility, reduce size significantly"

    elif vix_data.get("classification") == "high_fear":
        modifiers["risk_adjustment"] = 0.8
        modifiers["volatility_factor"] = 1.5
        regime = "high_volatility"
        description = f"VIX at {vix_data.get('vix')} - elevated volatility, trade cautiously"

    # Neutral/ranging
    else:
        regime = "neutral_mixed"
        description = "Mixed signals or neutral trend - standard trading rules apply"

    confidence = 0.8 if fomc_data["has_fomc"] else 0.7

    # Blend in alternative data bias if available
    if alternative_bias:
        alt_adjustments = alternative_bias.get("weight_adjustments", {})
        long_boost = alt_adjustments.get("long_boost", 0)
        short_boost = alt_adjustments.get("short_boost", 0)

        # Add alternative data signals to existing modifiers
        if "trend_following_boost" not in modifiers or modifiers["trend_following_boost"] == 0:
            # If no trend signal, use alternative data directly
            modifiers["alt_data_long_bias"] = long_boost
            modifiers["alt_data_short_bias"] = short_boost
        else:
            # If trend signal exists, blend (but don't override FOMC caution)
            if not fomc_data["has_fomc"] or fomc_data["impact"] == "low":
                modifiers["alt_data_long_bias"] = long_boost // 2
                modifiers["alt_data_short_bias"] = short_boost // 2

        description += f" | Alt data: {alternative_bias.get('directional_bias', 'neutral')}"

    return {
        "regime": regime,
        "confidence": confidence,
        "description": description,
        "scoring_modifiers": modifiers,
        "alternative_data_integrated": alternative_bias is not None
    }


def generate_weekly_context() -> dict:
    """
    Run full weekly context analysis.

    Returns comprehensive dict with all analyses and regime classification.
    """
    print(f"\n{'='*72}")
    print(f"  WEEKLY MARKET CONTEXT ANALYSIS")
    print(f"  {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print(f"{'='*72}\n")

    # Run all analyses
    print("  📅 Checking for FOMC meetings...")
    fomc_data = detect_fomc_next_week()
    print(f"     {fomc_data['note']}")

    print(f"\n  📊 Analyzing SPY daily trend...")
    spy_analysis = analyze_daily_trend("SPY")
    if "error" not in spy_analysis:
        print(f"     Price: ${spy_analysis['price']} | Trend: {spy_analysis['trend']}")
        print(f"     MA-50: ${spy_analysis['ma_50']} ({spy_analysis['distance_from_50']:+.2f}%)")
        print(f"     MA-200: ${spy_analysis['ma_200']} ({spy_analysis['distance_from_200']:+.2f}%)")

    print(f"\n  📊 Analyzing QQQ daily trend...")
    qqq_analysis = analyze_daily_trend("QQQ")
    if "error" not in qqq_analysis:
        print(f"     Price: ${qqq_analysis['price']} | Trend: {qqq_analysis['trend']}")
        print(f"     MA-50: ${qqq_analysis['ma_50']} ({qqq_analysis['distance_from_50']:+.2f}%)")
        print(f"     MA-200: ${qqq_analysis['ma_200']} ({qqq_analysis['distance_from_200']:+.2f}%)")

    print(f"\n  😱 Checking VIX (fear gauge)...")
    vix_data = get_vix_level()
    if "error" not in vix_data:
        print(f"     VIX: {vix_data['vix']} | {vix_data['classification']}")
        print(f"     {vix_data['note']}")

    # Alternative data analysis
    print(f"\n")
    try:
        from alternative_data import analyze_alternative_data
        alternative_analysis = analyze_alternative_data()
        alternative_bias = alternative_analysis.get("directional_bias")
    except Exception as e:
        print(f"  ⚠ Alternative data analysis failed: {e}")
        alternative_analysis = None
        alternative_bias = None

    # Classify regime (with alternative data if available)
    print(f"\n  🎯 Classifying market regime...")
    regime = classify_market_regime(spy_analysis, qqq_analysis, vix_data, fomc_data, alternative_bias)
    print(f"     Regime: {regime['regime']}")
    print(f"     {regime['description']}")
    print(f"\n  📐 Scoring modifiers:")
    for key, value in regime['scoring_modifiers'].items():
        print(f"     {key}: {value}")

    # Compile full context
    context = {
        "generated_at": datetime.now(ET).isoformat(),
        "week_starting": (datetime.now(ET) + timedelta(days=(7 - datetime.now(ET).weekday()))).strftime("%Y-%m-%d"),
        "fomc": fomc_data,
        "spy": spy_analysis,
        "qqq": qqq_analysis,
        "vix": vix_data,
        "alternative_data": alternative_analysis if alternative_analysis else {"error": "unavailable"},
        "regime": regime,
    }

    return context


def save_weekly_context(context: dict):
    """Save weekly context to disk."""
    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONTEXT_FILE, "w") as f:
        json.dump(context, f, indent=2)
    print(f"\n  💾 Saved weekly context to {CONTEXT_FILE}")


def load_weekly_context() -> dict | None:
    """Load weekly context from disk."""
    if not CONTEXT_FILE.exists():
        return None

    try:
        with open(CONTEXT_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠ Could not load weekly context: {e}")
        return None


if __name__ == "__main__":
    """Run weekly context analysis standalone."""
    context = generate_weekly_context()
    save_weekly_context(context)

    print(f"\n{'='*72}")
    print(f"  ANALYSIS COMPLETE")
    print(f"{'='*72}\n")
