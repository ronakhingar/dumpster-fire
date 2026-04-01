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
      - Gold (GLD ETF): Safe haven, inverse correlation when breaking out
      - Oil (USO ETF): Inflation indicator, affects consumer spending

    Uses Yahoo Finance for free real-time commodity prices.

    NOTE: Support/resistance levels should be reviewed monthly based on
    recent 30-day highs/lows. Check actual price action to recalibrate.

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
        commodities = {}

        # Gold (GLD ETF as proxy)
        try:
            # Fetch real GLD price with historical context
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=30)).timestamp())
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/GLD?interval=1d&period1={start}&period2={end}"
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

            if response.status_code == 200:
                data = response.json()
                result = data["chart"]["result"][0]
                closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]

                gold_price = closes[-1]
                week_ago_price = closes[-6] if len(closes) >= 6 else closes[0]
                month_ago_price = closes[0]

                # Calculate momentum
                weekly_change = ((gold_price - week_ago_price) / week_ago_price) * 100
                monthly_change = ((gold_price - month_ago_price) / month_ago_price) * 100
                month_low = min(closes)
                month_high = max(closes)
            else:
                raise Exception(f"HTTP {response.status_code}")

            # Dynamic resistance/support based on 30-day price action
            # Updated 2026-03-25: Recent range $399-$492
            resistance = 485.0  # 30-day high zone ($492 recent peak)
            support = 400.0     # 30-day low zone ($399 recent test)

            # Absolute level check
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

            # SHARP SPIKE DETECTION - gold surge = flight to safety
            # Gold spike >15% in 30 days = risk-off sentiment even if not at resistance
            if monthly_change > 15 and gold_signal == 0:
                gold_trend = "sharp_rally_flight_to_safety"
                gold_implication = "bearish_for_stocks"  # Risk-off
                gold_signal = -3

            # Gold drop >15% in 30 days = risk-on rotation
            elif monthly_change < -15 and gold_signal == 0:
                gold_trend = "sharp_drop_risk_on"
                gold_implication = "bullish_for_stocks"  # Money rotating out of safe havens
                gold_signal = +2

            commodities["gold"] = {
                "ticker": "GLD",
                "price": round(gold_price, 2),
                "weekly_change": round(weekly_change, 2),
                "monthly_change": round(monthly_change, 2),
                "month_low": round(month_low, 2),
                "month_high": round(month_high, 2),
                "resistance": resistance,
                "support": support,
                "trend": gold_trend,
                "implication": gold_implication,
                "signal": gold_signal,
                "note": f"Gold at ${gold_price:.2f} ({monthly_change:+.1f}% monthly), {gold_trend.replace('_', ' ')}"
            }
        except Exception as e:
            commodities["gold"] = {"error": f"Failed to fetch gold: {e}"}

        # Oil (USO ETF as proxy)
        try:
            # Fetch real USO price with historical context
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=30)).timestamp())
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/USO?interval=1d&period1={start}&period2={end}"
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

            if response.status_code == 200:
                data = response.json()
                result = data["chart"]["result"][0]
                closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]

                oil_price = closes[-1]
                week_ago_price = closes[-6] if len(closes) >= 6 else closes[0]
                month_ago_price = closes[0]

                # Calculate momentum
                weekly_change = ((oil_price - week_ago_price) / week_ago_price) * 100
                monthly_change = ((oil_price - month_ago_price) / month_ago_price) * 100
                month_low = min(closes)
                month_high = max(closes)
            else:
                raise Exception(f"HTTP {response.status_code}")

            # Oil thresholds based on 30-day action and inflation implications
            # Updated 2026-03-25: Recent range $78-$125, currently $113
            high_threshold = 120.0  # Above this = inflation concern (near recent high $125)
            low_threshold = 85.0    # Below this = demand concern or low inflation

            # Absolute level check
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

            # SHARP SPIKE DETECTION - override neutral if momentum extreme
            # Oil spike >30% in 30 days = inflation shock risk even if not at threshold
            if monthly_change > 30 and oil_signal == 0:
                oil_trend = "sharp_spike_inflation_risk"
                oil_implication = "bearish_for_stocks"
                oil_signal = -3  # Stronger bearish signal for spike

            # Oil crash >30% in 30 days = demand collapse or deflation
            elif monthly_change < -30 and oil_signal == 0:
                oil_trend = "sharp_drop_demand_concern"
                oil_implication = "bearish_for_stocks"  # Demand destruction also bearish
                oil_signal = -2

            commodities["oil"] = {
                "ticker": "USO",
                "price": round(oil_price, 2),
                "weekly_change": round(weekly_change, 2),
                "monthly_change": round(monthly_change, 2),
                "month_low": round(month_low, 2),
                "month_high": round(month_high, 2),
                "high_threshold": high_threshold,
                "low_threshold": low_threshold,
                "trend": oil_trend,
                "implication": oil_implication,
                "signal": oil_signal,
                "note": f"Oil at ${oil_price:.2f} ({monthly_change:+.1f}% monthly), {oil_trend.replace('_', ' ')}"
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
      - Yahoo Finance news RSS/API
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
        # Fetch real news headlines from Yahoo Finance
        events = []

        # Try to get market news from Yahoo Finance
        try:
            symbols = ["^GSPC", "^DJI", "^IXIC"]  # S&P 500, Dow, Nasdaq
            for symbol in symbols[:1]:  # Just use S&P for now to avoid rate limiting
                url = f"https://query1.finance.yahoo.com/v1/finance/search?q={symbol}&quotesCount=0&newsCount=10"
                response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

                if response.status_code == 200:
                    data = response.json()
                    news_items = data.get("news", [])

                    for item in news_items[:5]:  # Top 5 stories
                        title = item.get("title", "")
                        pub_time = item.get("providerPublishTime", 0)
                        pub_date = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d") if pub_time else "recent"

                        # Simple sentiment analysis based on keywords
                        title_lower = title.lower()
                        sentiment = "neutral"
                        score = 0
                        impact = "medium"

                        # Bearish keywords
                        if any(word in title_lower for word in ["fall", "drop", "plunge", "crash", "slide", "loss", "down", "concern", "worry", "fear", "risk", "war", "inflation", "rate hike"]):
                            sentiment = "bearish"
                            score = -2
                            if any(word in title_lower for word in ["crash", "plunge", "war", "crisis"]):
                                impact = "high"
                                score = -3

                        # Bullish keywords
                        elif any(word in title_lower for word in ["surge", "rally", "gain", "rise", "up", "beat", "record", "high", "strong", "growth"]):
                            sentiment = "bullish"
                            score = +2
                            if any(word in title_lower for word in ["surge", "record", "soar"]):
                                impact = "high"
                                score = +3

                        if score != 0:  # Only add if not neutral
                            events.append({
                                "date": pub_date,
                                "headline": title,
                                "sentiment": sentiment,
                                "impact": impact,
                                "score": score
                            })

                    break  # Got news, no need to try other symbols

        except Exception as e:
            print(f"  ⚠ Could not fetch Yahoo Finance news: {e}")

        # If no news fetched, use informative default
        if not events:
            events = [
                {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "headline": "Unable to fetch current news headlines",
                    "sentiment": "neutral",
                    "impact": "low",
                    "score": 0
                }
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
