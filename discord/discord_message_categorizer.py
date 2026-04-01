#!/usr/bin/env python3
"""
Discord Message Categorizer

Categorizes Discord trading messages into actionable types:
- Active trades (entries/exits)
- Trade setups (conditional)
- Long-term ideas
- Economic analysis
- Options strategies
- Trade outcomes
"""

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import List, Dict

ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).parent

# Output files
CATEGORIES_DIR = BASE_DIR / "trade_categories"
CATEGORIES_DIR.mkdir(exist_ok=True)

# Category definitions
CATEGORY_PATTERNS = {
    "active_trade_entry": {
        "keywords": ["buying", "bought", "nibbling", "adding", "started a position", "going to buy"],
        "patterns": [r"up \d+%.*entry", r"cost basis.*\$\d+"],
        "output": "active_trades.jsonl"
    },

    "active_trade_exit": {
        "keywords": ["up \$", "profit", "sold", "closing", "took profit", "easy money"],
        "patterns": [r"up \d+% on", r"made \$\d+"],
        "output": "active_trades.jsonl"
    },

    "conditional_setup": {
        "keywords": ["if", "when", "criteria", "looking at", "will decide", "contemplating"],
        "patterns": [r"if .* then", r"when .* (>|<) \d+", r"will.*if"],
        "output": "conditional_setups.jsonl"
    },

    "long_term_idea": {
        "keywords": ["long term", "forward pe", "golden pocket", "cheap", "valuation",
                    "oversold", "dca", "averaging", "hold", "years"],
        "patterns": [r"pe ratio.*\d+", r"cheapest.*ever", r"down \d+%.*highs"],
        "output": "long_term_ideas.jsonl"
    },

    "options_strategy": {
        "keywords": ["leap", "calls", "puts", "spread", "strike", "premium",
                    "expiring", "delta", "itm", "otm"],
        "patterns": [r"\d+[cp]", r"exp\w* \w+ \d+", r"\$\d+\/\$\d+ spread"],
        "output": "options_strategies.jsonl"
    },

    "economic_analysis": {
        "keywords": ["fed", "fomc", "cpi", "pce", "nfp", "unemployment", "gdp",
                    "inflation", "rate cut", "jobs data", "macro"],
        "patterns": [r"(fed|fomc|cpi|pce|nfp).*\d+\.\d+%"],
        "output": "economic_analysis.jsonl"
    },

    "market_regime": {
        "keywords": ["correction", "bear market", "bull market", "rally", "recession",
                    "crash", "volatility", "vix", "trend", "pullback"],
        "patterns": [r"(down|up) \d+%.*from highs", r"vix.*\d+"],
        "output": "market_analysis.jsonl"
    },

    "risk_management": {
        "keywords": ["hedge", "hedging", "stop loss", "risk", "position size",
                    "portfolio", "diversif", "protection", "downside"],
        "patterns": [r"risk.*\d+%", r"hedge.*\d+%"],
        "output": "risk_management.jsonl"
    },

    "technical_level": {
        "keywords": ["support", "resistance", "200ma", "ema", "fib", "golden pocket",
                    "trend line", "breakout", "breakdown"],
        "patterns": [r"(support|resistance).*\$\d+", r"\d+ma", r"\d+ema"],
        "output": "technical_levels.jsonl"
    },

    "trade_outcome": {
        "keywords": ["closed", "result", "p&l", "win", "loss", "r-multiple", "hit target"],
        "patterns": [r"[+-]\$\d+", r"\d+\.\d+R", r"(won|lost).*trade"],
        "output": "trade_outcomes.jsonl"
    }
}


def categorize_message(text: str, timestamp: str) -> List[str]:
    """
    Categorize a message into one or more types.

    Returns list of matching categories.
    """
    text_lower = text.lower()
    categories = []

    for category, definition in CATEGORY_PATTERNS.items():
        # Check keywords
        keyword_match = any(kw in text_lower for kw in definition["keywords"])

        # Check regex patterns
        pattern_match = any(re.search(pat, text_lower) for pat in definition["patterns"])

        if keyword_match or pattern_match:
            categories.append(category)

    # Default category if nothing matched
    if not categories:
        categories.append("general_commentary")

    return categories


def extract_tickers(text: str) -> List[str]:
    """Extract stock tickers from text."""
    tickers = []

    # Explicit $ mentions (high confidence)
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text)
    tickers.extend(dollar_tickers)

    # All-caps words 1-5 chars (potential tickers)
    potential_tickers = re.findall(r'\b([A-Z]{1,5})\b', text)

    # Common English words to exclude
    common_words = {
        'I', 'A', 'AM', 'PM', 'ET', 'US', 'IT', 'IS', 'AS', 'AT', 'TO', 'OF', 'IF',
        'OR', 'AND', 'BUT', 'FOR', 'THE', 'NOT', 'ALL', 'ARE', 'WAS', 'HAS', 'HAD',
        'BE', 'WE', 'MY', 'NO', 'SO', 'UP', 'ON', 'IN', 'BY', 'AN', 'VIX', 'MA', 'EMA',
        'PE', 'ATH', 'IMO', 'FYI', 'CEO', 'CFO', 'AI', 'AR', 'VR', 'DCA', 'LEAPS',
        'ITM', 'OTM', 'ATM', 'IV', 'FVG', 'R', 'S', 'W', 'M', 'Y', 'H', 'D',
        'VS', 'AVG', 'MAX', 'MIN', 'USD', 'YOY', 'MOM', 'QOQ', 'YTD', 'MTD',
        'RED', 'GAP', 'PO', 'IPO', 'GDP', 'CPI', 'PPI', 'NFP', 'OPEX', 'FOMC',
        'FED', 'SEC', 'IRS', 'LLC', 'INC', 'CORP', 'CO', 'LTD', 'USA', 'UK', 'EU'
    }

    # Known tickers (whitelist common ones)
    known_tickers = {
        'SPY', 'QQQ', 'IWM', 'DIA', 'VIX', 'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'GOOG',
        'AMZN', 'META', 'TSLA', 'NFLX', 'AMD', 'INTC', 'AVGO', 'ORCL', 'ADBE', 'CRM',
        'PYPL', 'V', 'MA', 'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BRK',
        'UNH', 'JNJ', 'PFE', 'ABBV', 'LLY', 'MRK', 'TMO', 'DHR', 'ABT', 'BMY',
        'XOM', 'CVX', 'COP', 'SLB', 'MPC', 'PSX', 'VLO', 'EOG', 'PXD', 'OXY',
        'PLTR', 'HOOD', 'COIN', 'SQ', 'SOFI', 'AFRM', 'UPST', 'RBLX', 'DASH', 'UBER',
        'NVO', 'ASML', 'NKE', 'DIS', 'BA', 'CAT', 'DE', 'HON', 'UPS', 'FDX',
        'TLT', 'TMF', 'IGV', 'XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU',
        'GLD', 'SLV', 'USO', 'UNG', 'TAN', 'ICLN', 'ARKK', 'ARKG', 'ARKW', 'ARKF'
    }

    # Filter potential tickers
    for ticker in potential_tickers:
        # Must be in known list OR not in common words
        if ticker in known_tickers or (ticker not in common_words and len(ticker) >= 2):
            # Additional validation: if 2 chars, must be known ticker
            if len(ticker) == 2 and ticker not in known_tickers:
                continue
            tickers.append(ticker)

    # Company name mentions
    name_to_ticker = {
        'nvidia': 'NVDA', 'google': 'GOOG', 'alphabet': 'GOOG',
        'amazon': 'AMZN', 'microsoft': 'MSFT', 'apple': 'AAPL',
        'meta': 'META', 'facebook': 'META', 'tesla': 'TSLA',
        'palantir': 'PLTR', 'robinhood': 'HOOD', 'coinbase': 'COIN',
        'novo nordisk': 'NVO', 'nike': 'NKE', 'asml': 'ASML',
        'netflix': 'NFLX', 'disney': 'DIS', 'boeing': 'BA'
    }

    text_lower = text.lower()
    for name, ticker in name_to_ticker.items():
        if name in text_lower:
            tickers.append(ticker)

    # Deduplicate and sort
    return sorted(list(set(tickers)))


def extract_price_levels(text: str) -> Dict[str, List[float]]:
    """Extract support/resistance/target levels."""
    levels = {
        'support': [],
        'resistance': [],
        'targets': []
    }

    # Find price mentions
    prices = re.findall(r'\$(\d+(?:\.\d+)?)', text)

    # Categorize by context
    text_lower = text.lower()
    for price in prices:
        price_float = float(price)

        if 'support' in text_lower:
            levels['support'].append(price_float)
        if 'resistance' in text_lower:
            levels['resistance'].append(price_float)
        if 'target' in text_lower:
            levels['targets'].append(price_float)

    return {k: list(set(v)) for k, v in levels.items() if v}


def categorize_all_messages():
    """Categorize all historical messages."""
    # Load signals
    signals_file = BASE_DIR / "journal" / "discord_signals_history.jsonl"

    if not signals_file.exists():
        print(f"❌ No signals file found: {signals_file}")
        return

    # Category storage
    categorized = {cat: [] for cat in set(
        def_['output'] for def_ in CATEGORY_PATTERNS.values()
    )}
    categorized['general_commentary.jsonl'] = []

    print("📋 Categorizing Discord messages...\n")

    total = 0
    with open(signals_file) as f:
        for line in f:
            signal = json.loads(line)
            text = signal.get('raw_text', '')
            timestamp = signal.get('timestamp', '')

            if not text or len(text) < 20:
                continue

            total += 1

            # Categorize
            categories = categorize_message(text, timestamp)

            # Extract metadata
            tickers = extract_tickers(text)
            price_levels = extract_price_levels(text)

            # Create enriched entry
            entry = {
                'timestamp': timestamp,
                'raw_text': text,
                'categories': categories,
                'tickers': tickers,
                'price_levels': price_levels,
                'message_id': signal.get('notification_id', ''),
                'source_timestamp': signal.get('source_timestamp', '')
            }

            # Add to appropriate output files
            for category in categories:
                output_file = CATEGORY_PATTERNS.get(category, {}).get('output', 'general_commentary.jsonl')
                categorized[output_file].append(entry)

    # Save categorized messages
    print(f"✅ Categorized {total} messages\n")

    for filename, entries in categorized.items():
        if not entries:
            continue

        output_path = CATEGORIES_DIR / filename
        with open(output_path, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')

        print(f"  📁 {filename}: {len(entries)} messages")

    print(f"\n✅ Saved to: {CATEGORIES_DIR}/")

    # Summary stats
    print("\n" + "="*60)
    print("CATEGORY BREAKDOWN")
    print("="*60)

    category_counts = {}
    for filename, entries in categorized.items():
        if entries:
            cat_name = filename.replace('.jsonl', '').replace('_', ' ').title()
            category_counts[cat_name] = len(entries)

    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat:<30} {count:>4} messages")


if __name__ == "__main__":
    categorize_all_messages()
