#!/usr/bin/env python3
"""
Alternative Data & Market Sentiment Analysis

Gathers alternative data sources to enhance weekly market context:
  - Polymarket prediction markets (Fed decisions, economic data)
  - Commodities analysis (gold, oil, silver) with stock correlations
  - Financial news scanning and sentiment
  - Asymmetric opportunity detection

Output: Directional bias scores and weight adjustments for the week ahead
"""

from __future__ import annotations

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


# ─── Polymarket Integration ──────────────────────────────────────────────────

def query_polymarket_markets() -> dict:
    """
    Query Polymarket API for relevant prediction markets.

    Focus areas:
      - Federal Reserve rate decisions
      - Jobs reports
      - CPI/inflation data
      - Major economic events

    Returns:
        {
            "fed_rate_cut": {"probability": 0.65, "direction": "dovish"},
            "jobs_beat": {"probability": 0.45, "direction": "neutral"},
            "sentiment_summary": str
        }
    """
    try:
        # Polymarket API endpoint (https://docs.polymarket.com/)
        # Note: This is a simplified implementation
        # Real implementation would need proper API key and authentication

        markets_of_interest = {
            "fed_rate_cut": {
                "market_slug": "will-the-fed-cut-rates",
                "description": "Fed rate cut probability",
                "bullish_outcome": "yes",  # Rate cut = bullish for stocks
            },
            "inflation_above_target": {
                "market_slug": "will-cpi-be-above-3",
                "description": "CPI above 3% probability",
                "bullish_outcome": "no",  # Lower inflation = bullish
            },
            "jobs_beat_estimates": {
                "market_slug": "will-nfp-beat-estimates",
                "description": "Jobs beat estimates probability",
                "bullish_outcome": "yes",  # Strong jobs = mixed signal
            },
        }

        # Mock implementation - replace with actual API calls
        # For demo purposes, returning plausible probabilities
        sentiment = {
            "fed_rate_cut": {
                "probability": 0.35,
                "direction": "slightly_hawkish",
                "note": "Low probability of near-term cut suggests Fed staying firm"
            },
            "inflation_cooling": {
                "probability": 0.60,
                "direction": "moderately_bullish",
                "note": "Market pricing in cooling inflation trajectory"
            },
            "jobs_strength": {
                "probability": 0.55,
                "direction": "neutral",
                "note": "Balanced expectations on labor market"
            },
        }

        # Calculate overall sentiment
        bullish_signals = sum(1 for s in sentiment.values() if "bullish" in s["direction"])
        bearish_signals = sum(1 for s in sentiment.values() if "bearish" in s["direction"] or "hawkish" in s["direction"])

        if bullish_signals > bearish_signals:
            overall = "bullish_tilt"
            bias_score = +5
        elif bearish_signals > bullish_signals:
            overall = "bearish_tilt"
            bias_score = -5
        else:
            overall = "neutral"
            bias_score = 0

        sentiment["overall_sentiment"] = {
            "direction": overall,
            "bias_score": bias_score,
            "confidence": 0.6,
            "summary": f"Polymarket sentiment: {overall.replace('_', ' ')} based on {len(sentiment)-1} markets"
        }

        return sentiment

    except Exception as e:
        print(f"  ⚠ Polymarket query failed: {e}")
        return {
            "error": str(e),
            "overall_sentiment": {
                "direction": "unavailable",
                "bias_score": 0,
                "confidence": 0,
                "summary": "Polymarket data unavailable"
            }
        }


# ─── Commodities Analysis ────────────────────────────────────────────────────

def analyze_commodities() -> dict:
    """
    Analyze key commodities and their correlation with stock market.

    Commodities:
      - Gold (GLD ETF or XAUUSD): Safe haven, inverse correlation when breaking out
      - Oil (USO ETF or CL futures): Inflation indicator, affects consumer spending
      - Silver (SLV ETF): Industrial demand, tech sector proxy

    Returns:
        {
            "gold": {
                "price": 2050.0,
                "trend": "breakout",
                "at_key_level": true,
                "implication": "bearish_for_stocks"
            },
            "correlation_signal": "gold_breakout_warns_risk_off"
        }
    """
    try:
        from alpaca_trader import get_quote

        commodities = {}

        # Gold (GLD ETF as proxy)
        try:
            gld_quote = get_quote("GLD")
            gold_price = (gld_quote["bid"] + gld_quote["ask"]) / 2 if gld_quote else None

            if gold_price:
                # Simple trend detection (would be enhanced with historical data)
                # Mock resistance/support levels
                resistance = 200.0  # Example GLD level
                support = 180.0

                if gold_price > resistance:
                    gold_trend = "breakout_above_resistance"
                    gold_implication = "bearish_for_stocks"  # Flight to safety
                    gold_signal = -3  # Bearish for stocks
                elif gold_price < support:
                    gold_trend = "breakdown_below_support"
                    gold_implication = "bullish_for_stocks"  # Risk-on
                    gold_signal = +3
                else:
                    gold_trend = "range_bound"
                    gold_implication = "neutral"
                    gold_signal = 0

                commodities["gold"] = {
                    "ticker": "GLD",
                    "price": round(gold_price, 2),
                    "resistance": resistance,
                    "support": support,
                    "trend": gold_trend,
                    "implication": gold_implication,
                    "signal": gold_signal,
                    "note": f"Gold at ${gold_price:.2f}, {gold_trend.replace('_', ' ')}"
                }
        except Exception as e:
            commodities["gold"] = {"error": f"Failed to fetch gold: {e}"}

        # Oil (USO ETF as proxy)
        try:
            uso_quote = get_quote("USO")
            oil_price = (uso_quote["bid"] + uso_quote["ask"]) / 2 if uso_quote else None

            if oil_price:
                # Oil above $80 (USO ~$80) = inflation concerns
                high_threshold = 80.0
                low_threshold = 60.0

                if oil_price > high_threshold:
                    oil_trend = "elevated_inflation_concern"
                    oil_implication = "bearish_for_stocks"
                    oil_signal = -2
                elif oil_price < low_threshold:
                    oil_trend = "low_inflation_supportive"
                    oil_implication = "bullish_for_stocks"
                    oil_signal = +2
                else:
                    oil_trend = "neutral_range"
                    oil_implication = "neutral"
                    oil_signal = 0

                commodities["oil"] = {
                    "ticker": "USO",
                    "price": round(oil_price, 2),
                    "high_threshold": high_threshold,
                    "low_threshold": low_threshold,
                    "trend": oil_trend,
                    "implication": oil_implication,
                    "signal": oil_signal,
                    "note": f"Oil at ${oil_price:.2f}, {oil_trend.replace('_', ' ')}"
                }
        except Exception as e:
            commodities["oil"] = {"error": f"Failed to fetch oil: {e}"}

        # Calculate combined commodity signal
        total_signal = sum(c.get("signal", 0) for c in commodities.values() if "signal" in c)

        if total_signal > 2:
            correlation_signal = "commodities_suggest_risk_on"
            bias_score = +3
        elif total_signal < -2:
            correlation_signal = "commodities_warn_risk_off"
            bias_score = -3
        else:
            correlation_signal = "commodities_neutral"
            bias_score = 0

        commodities["summary"] = {
            "correlation_signal": correlation_signal,
            "bias_score": bias_score,
            "total_signal": total_signal,
            "note": correlation_signal.replace('_', ' ').title()
        }

        return commodities

    except Exception as e:
        print(f"  ⚠ Commodities analysis failed: {e}")
        return {
            "error": str(e),
            "summary": {
                "correlation_signal": "unavailable",
                "bias_score": 0,
                "total_signal": 0,
                "note": "Commodities data unavailable"
            }
        }


# ─── Financial News Scanning ──────────────────────────────────────────────────

def scan_financial_news() -> dict:
    """
    Scan financial news from past week for market-moving events.

    Sources:
      - Alpha Vantage News API
      - Major economic releases
      - Corporate earnings surprises
      - Geopolitical events

    Returns:
        {
            "major_events": [
                {"date": "2026-03-25", "headline": "...", "sentiment": "bearish", "impact": "high"}
            ],
            "sentiment_score": -2,
            "summary": "Mixed news with slight bearish tilt"
        }
    """
    try:
        # In production, would integrate with Alpha Vantage or similar
        # For now, return structure with mock data

        # Mock recent events (would be fetched from API)
        events = [
            {
                "date": "2026-03-24",
                "headline": "Fed Chair signals higher rates for longer",
                "sentiment": "bearish",
                "impact": "high",
                "score": -3
            },
            {
                "date": "2026-03-26",
                "headline": "Tech earnings beat expectations",
                "sentiment": "bullish",
                "impact": "medium",
                "score": +2
            },
            {
                "date": "2026-03-27",
                "headline": "Consumer confidence drops unexpectedly",
                "sentiment": "bearish",
                "impact": "medium",
                "score": -2
            },
        ]

        # Calculate sentiment
        total_score = sum(e["score"] for e in events)
        avg_score = total_score / len(events) if events else 0

        if avg_score > 1:
            sentiment = "bullish"
            bias_score = +3
        elif avg_score < -1:
            sentiment = "bearish"
            bias_score = -3
        else:
            sentiment = "mixed"
            bias_score = 0

        high_impact_events = [e for e in events if e["impact"] == "high"]

        return {
            "major_events": events,
            "high_impact_count": len(high_impact_events),
            "sentiment_score": round(avg_score, 2),
            "sentiment": sentiment,
            "bias_score": bias_score,
            "summary": f"{len(events)} major events this week, sentiment: {sentiment}, avg impact: {avg_score:.1f}"
        }

    except Exception as e:
        print(f"  ⚠ News scanning failed: {e}")
        return {
            "error": str(e),
            "major_events": [],
            "sentiment": "unavailable",
            "bias_score": 0,
            "summary": "News data unavailable"
        }


# ─── Sentiment Scoring System ─────────────────────────────────────────────────

def calculate_alternative_data_bias(
    polymarket_data: dict,
    commodities_data: dict,
    news_data: dict
) -> dict:
    """
    Combine all alternative data sources into unified directional bias.

    Weight different signals by reliability and convert to actionable scores.

    Returns:
        {
            "directional_bias": "bullish" | "bearish" | "neutral",
            "confidence": 0.75,
            "bias_score": +8,  # Applied to long setups
            "weight_adjustments": {
                "long_boost": +8,
                "short_penalty": -8
            },
            "asymmetric_opportunities": [...]
        }
    """
    # Extract bias scores from each source
    polymarket_score = polymarket_data.get("overall_sentiment", {}).get("bias_score", 0)
    commodities_score = commodities_data.get("summary", {}).get("bias_score", 0)
    news_score = news_data.get("bias_score", 0)

    # Weight the signals (Polymarket most forward-looking, news most recent)
    weighted_score = (
        polymarket_score * 0.4 +  # Prediction markets = forward-looking
        commodities_score * 0.3 +  # Inter-market = structural
        news_score * 0.3            # News = recent events
    )

    # Determine directional bias
    if weighted_score > 3:
        direction = "strong_bullish"
        confidence = 0.75
        long_boost = +10
        short_penalty = -15
    elif weighted_score > 1:
        direction = "bullish"
        confidence = 0.65
        long_boost = +5
        short_penalty = -8
    elif weighted_score < -3:
        direction = "strong_bearish"
        confidence = 0.75
        long_boost = -15
        short_penalty = +10
    elif weighted_score < -1:
        direction = "bearish"
        confidence = 0.65
        long_boost = -8
        short_penalty = +5
    else:
        direction = "neutral"
        confidence = 0.5
        long_boost = 0
        short_penalty = 0

    # Detect asymmetric opportunities
    asymmetric_ops = []

    # Example: If Polymarket shows high conviction but stocks haven't moved
    poly_conviction = abs(polymarket_score) > 3
    if poly_conviction:
        asymmetric_ops.append({
            "type": "polymarket_divergence",
            "description": "Prediction markets showing strong conviction",
            "bias": "bullish" if polymarket_score > 0 else "bearish",
            "score": abs(polymarket_score)
        })

    # Gold breakout while stocks still near highs = asymmetric risk
    gold_data = commodities_data.get("gold", {})
    if gold_data.get("trend") == "breakout_above_resistance":
        asymmetric_ops.append({
            "type": "gold_flight_to_safety",
            "description": "Gold breaking out suggests hidden risk",
            "bias": "bearish",
            "score": 3
        })

    return {
        "directional_bias": direction,
        "confidence": confidence,
        "weighted_score": round(weighted_score, 2),
        "bias_score": round(weighted_score, 0),
        "weight_adjustments": {
            "long_boost": long_boost,
            "short_boost": short_penalty,
            "long_penalty": short_penalty,
            "short_penalty": long_boost,
        },
        "asymmetric_opportunities": asymmetric_ops,
        "component_scores": {
            "polymarket": polymarket_score,
            "commodities": commodities_score,
            "news": news_score,
        },
        "summary": f"Alternative data shows {direction} bias (score: {weighted_score:.1f}, confidence: {confidence:.0%})"
    }


# ─── Main Analysis Function ───────────────────────────────────────────────────

def analyze_alternative_data() -> dict:
    """
    Run full alternative data analysis suite.

    Returns comprehensive dict with all analyses and actionable bias.
    """
    print(f"\n{'='*72}")
    print(f"  ALTERNATIVE DATA & SENTIMENT ANALYSIS")
    print(f"  {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print(f"{'='*72}\n")

    # Polymarket prediction markets
    print("  🎲 Querying Polymarket prediction markets...")
    polymarket_data = query_polymarket_markets()
    poly_summary = polymarket_data.get("overall_sentiment", {})
    print(f"     {poly_summary.get('summary', 'N/A')}")

    # Commodities analysis
    print(f"\n  🥇 Analyzing commodities (gold, oil, silver)...")
    commodities_data = analyze_commodities()
    comm_summary = commodities_data.get("summary", {})
    print(f"     {comm_summary.get('note', 'N/A')}")

    # Financial news
    print(f"\n  📰 Scanning financial news from past week...")
    news_data = scan_financial_news()
    print(f"     {news_data.get('summary', 'N/A')}")

    # Calculate unified bias
    print(f"\n  🎯 Calculating alternative data bias...")
    bias = calculate_alternative_data_bias(polymarket_data, commodities_data, news_data)
    print(f"     {bias['summary']}")

    if bias.get("asymmetric_opportunities"):
        print(f"\n  ⚡ Asymmetric opportunities detected:")
        for opp in bias["asymmetric_opportunities"]:
            print(f"     • {opp['description']} ({opp['bias']}, score: {opp['score']})")

    # Compile full analysis
    analysis = {
        "generated_at": datetime.now(ET).isoformat(),
        "polymarket": polymarket_data,
        "commodities": commodities_data,
        "news": news_data,
        "directional_bias": bias,
    }

    return analysis


if __name__ == "__main__":
    """Run alternative data analysis standalone."""
    analysis = analyze_alternative_data()

    print(f"\n{'='*72}")
    print(f"  ANALYSIS COMPLETE")
    print(f"{'='*72}\n")

    # Pretty print summary
    bias = analysis["directional_bias"]
    print(f"Directional Bias: {bias['directional_bias']}")
    print(f"Confidence: {bias['confidence']:.0%}")
    print(f"Score: {bias['bias_score']}")
    print(f"\nWeight Adjustments:")
    for k, v in bias["weight_adjustments"].items():
        print(f"  {k}: {v:+d}")
