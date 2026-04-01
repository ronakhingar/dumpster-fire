#!/usr/bin/env python3
"""
Trade Opportunity Monitor

Monitors market conditions and checks if trade setups from Discord are actionable.

Categories monitored:
1. Conditional setups (if-then rules)
2. Long-term ideas (valuation-based)
3. Technical level setups (support/resistance)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
import yfinance as yf
from notify_macos import notify_opportunities

ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).parent
CATEGORIES_DIR = BASE_DIR / "trade_categories"
OUTPUT_FILE = BASE_DIR / "trade_opportunities" / "actionable_now.json"
OUTPUT_FILE.parent.mkdir(exist_ok=True)


def get_current_price(ticker: str) -> Optional[float]:
    """Get current market price for ticker."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period='1d')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except Exception as e:
        pass
    return None


def get_technical_indicators(ticker: str) -> Dict:
    """Get current technical indicators."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period='60d')

        if len(data) < 50:
            return {}

        # Calculate indicators
        current_price = float(data['Close'].iloc[-1])
        ma_50 = data['Close'].rolling(50).mean().iloc[-1]
        ma_200 = data['Close'].rolling(200).mean().iloc[-1] if len(data) >= 200 else None

        # Distance from MAs
        distance_50ma = ((current_price - ma_50) / ma_50) * 100 if ma_50 else None
        distance_200ma = ((current_price - ma_200) / ma_200) * 100 if ma_200 else None

        # Recent high/low
        high_52w = data['High'].tail(252).max() if len(data) >= 252 else data['High'].max()
        low_52w = data['Low'].tail(252).min() if len(data) >= 252 else data['Low'].min()

        # Draw down from highs
        drawdown = ((current_price - high_52w) / high_52w) * 100

        return {
            'price': current_price,
            'ma_50': float(ma_50) if ma_50 else None,
            'ma_200': float(ma_200) if ma_200 else None,
            'distance_50ma': float(distance_50ma) if distance_50ma else None,
            'distance_200ma': float(distance_200ma) if distance_200ma else None,
            'high_52w': float(high_52w),
            'low_52w': float(low_52w),
            'drawdown_pct': float(drawdown)
        }
    except Exception as e:
        return {}


def get_valuation_metrics(ticker: str) -> Dict:
    """Get valuation metrics (PE, etc.)."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            'forward_pe': info.get('forwardPE'),
            'trailing_pe': info.get('trailingPE'),
            'peg_ratio': info.get('pegRatio'),
            'price_to_book': info.get('priceToBook'),
            'market_cap': info.get('marketCap')
        }
    except Exception as e:
        return {}


def check_conditional_setups() -> List[Dict]:
    """Check if conditional trade setups are triggered."""
    opportunities = []

    setup_file = CATEGORIES_DIR / "conditional_setups.jsonl"
    if not setup_file.exists():
        return opportunities

    with open(setup_file) as f:
        for line in f:
            entry = json.loads(line)
            text = entry['raw_text'].lower()
            tickers = entry.get('tickers', [])

            # Check common conditional patterns
            conditions_met = []

            # Pattern: "DCA at 200MA"
            if "200ma" in text or "200 ma" in text:
                for ticker in tickers:
                    indicators = get_technical_indicators(ticker)
                    if indicators.get('distance_200ma') is not None:
                        dist = indicators['distance_200ma']
                        # Within 2% of 200MA
                        if abs(dist) <= 2.0:
                            conditions_met.append({
                                'condition': 'At 200MA',
                                'ticker': ticker,
                                'price': indicators['price'],
                                'distance': f"{dist:+.2f}%"
                            })

            # Pattern: "down X% from highs"
            if "down" in text and "from high" in text:
                for ticker in tickers:
                    indicators = get_technical_indicators(ticker)
                    if indicators.get('drawdown_pct'):
                        drawdown = indicators['drawdown_pct']
                        # Significant drawdown (>10%)
                        if drawdown < -10:
                            conditions_met.append({
                                'condition': 'Down from highs',
                                'ticker': ticker,
                                'price': indicators['price'],
                                'drawdown': f"{drawdown:.1f}%"
                            })

            if conditions_met:
                opportunities.append({
                    'type': 'conditional_setup',
                    'timestamp': entry['timestamp'],
                    'original_message': entry['raw_text'][:200],
                    'conditions_met': conditions_met
                })

    return opportunities


def check_long_term_ideas() -> List[Dict]:
    """Check if long-term investment ideas are still valid."""
    opportunities = []

    ideas_file = CATEGORIES_DIR / "long_term_ideas.jsonl"
    if not ideas_file.exists():
        return opportunities

    with open(ideas_file) as f:
        for line in f:
            entry = json.loads(line)
            text = entry['raw_text'].lower()
            tickers = entry.get('tickers', [])

            # Check each ticker
            for ticker in tickers:
                current_price = get_current_price(ticker)
                if not current_price:
                    continue

                valuation = get_valuation_metrics(ticker)
                indicators = get_technical_indicators(ticker)

                # Criteria for "still valid"
                valid_reasons = []

                # Check PE ratio
                if valuation.get('forward_pe') and valuation['forward_pe'] < 25:
                    valid_reasons.append(f"Forward PE: {valuation['forward_pe']:.1f} (attractive)")

                # Check drawdown
                if indicators.get('drawdown_pct') and indicators['drawdown_pct'] < -20:
                    valid_reasons.append(f"Down {abs(indicators['drawdown_pct']):.0f}% from highs")

                # Check if at 200MA
                if indicators.get('distance_200ma') and abs(indicators['distance_200ma']) < 5:
                    valid_reasons.append(f"Near 200MA ({indicators['distance_200ma']:+.1f}%)")

                if valid_reasons:
                    opportunities.append({
                        'type': 'long_term_idea',
                        'ticker': ticker,
                        'current_price': current_price,
                        'timestamp': entry['timestamp'],
                        'original_message': entry['raw_text'][:200],
                        'valid_reasons': valid_reasons,
                        'valuation': valuation,
                        'technicals': indicators
                    })

    return opportunities


def check_technical_levels() -> List[Dict]:
    """Check if price is at mentioned support/resistance levels."""
    opportunities = []

    levels_file = CATEGORIES_DIR / "technical_levels.jsonl"
    if not levels_file.exists():
        return opportunities

    with open(levels_file) as f:
        for line in f:
            entry = json.loads(line)
            tickers = entry.get('tickers', [])
            price_levels = entry.get('price_levels', {})

            for ticker in tickers:
                current_price = get_current_price(ticker)
                if not current_price:
                    continue

                # Check if near support levels (within 1%)
                for support in price_levels.get('support', []):
                    distance = abs(current_price - support) / support * 100
                    if distance < 1.0:
                        opportunities.append({
                            'type': 'at_support',
                            'ticker': ticker,
                            'current_price': current_price,
                            'support_level': support,
                            'distance': f"{distance:.2f}%",
                            'message': entry['raw_text'][:150]
                        })

                # Check if near resistance (within 1%)
                for resistance in price_levels.get('resistance', []):
                    distance = abs(current_price - resistance) / resistance * 100
                    if distance < 1.0:
                        opportunities.append({
                            'type': 'at_resistance',
                            'ticker': ticker,
                            'current_price': current_price,
                            'resistance_level': resistance,
                            'distance': f"{distance:.2f}%",
                            'message': entry['raw_text'][:150]
                        })

    return opportunities


def generate_report():
    """Generate actionable opportunities report."""
    print("🔍 Scanning for actionable trade opportunities...\n")

    # Check all categories
    conditional = check_conditional_setups()
    long_term = check_long_term_ideas()
    technical = check_technical_levels()

    all_opportunities = {
        'generated_at': datetime.now(ET).isoformat(),
        'conditional_setups': conditional,
        'long_term_ideas': long_term,
        'technical_levels': technical,
        'total_opportunities': len(conditional) + len(long_term) + len(technical)
    }

    # Save report
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_opportunities, f, indent=2)

    # Display summary
    print("="*70)
    print("ACTIONABLE OPPORTUNITIES")
    print("="*70)

    if conditional:
        print(f"\n📊 Conditional Setups Triggered: {len(conditional)}")
        for opp in conditional[:3]:
            for cond in opp['conditions_met']:
                print(f"  • {cond['ticker']}: {cond['condition']} @ ${cond['price']:.2f}")

    if long_term:
        print(f"\n💼 Long-Term Ideas Still Valid: {len(long_term)}")
        for opp in long_term[:3]:
            print(f"  • {opp['ticker']}: ${opp['current_price']:.2f}")
            for reason in opp['valid_reasons'][:2]:
                print(f"    - {reason}")

    if technical:
        print(f"\n📈 At Technical Levels: {len(technical)}")
        for opp in technical[:3]:
            level_type = opp['type'].replace('_', ' ').title()
            level = opp.get('support_level') or opp.get('resistance_level')
            print(f"  • {opp['ticker']}: {level_type} ${level:.2f} (current: ${opp['current_price']:.2f})")

    print(f"\n✅ Report saved to: {OUTPUT_FILE}")
    print("="*70)

    # Send macOS notification if opportunities found
    total = all_opportunities['total_opportunities']
    if total > 0:
        # Build summary for notification
        details_parts = []
        if conditional:
            details_parts.append(f"{len(conditional)} conditional")
        if long_term:
            details_parts.append(f"{len(long_term)} long-term")
        if technical:
            details_parts.append(f"{len(technical)} technical")

        details = " | ".join(details_parts)
        notify_opportunities(total, details)


if __name__ == "__main__":
    generate_report()
