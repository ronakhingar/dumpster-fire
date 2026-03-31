#!/usr/bin/env python3
"""
Analyze swings channel Discord messages to categorize option trade types.

Categorizes into:
- LEAPS (Long-term Equity Anticipation Securities)
- Short-term calls/puts
- Spreads (vertical, calendar, diagonal)
- Covered calls / cash-secured puts
- Iron condors / butterflies
- Straddles / strangles
- Rolling positions
- Position closes / profit-taking
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime


# Option strategy patterns
PATTERNS = {
    "leaps": {
        "keywords": ["leap", "leaps", "long term", "2025", "2026", "2027", "jan 20", "year out"],
        "regex": [r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}", r"\d{1,2}/\d{1,2}/\d{4}"]
    },
    "spreads": {
        "keywords": ["spread", "vertical", "calendar", "diagonal", "debit spread", "credit spread",
                    "bull call", "bear put", "call spread", "put spread"],
        "regex": [r"\$\d+/\$\d+", r"\d+c/\d+c", r"\d+p/\d+p"]
    },
    "covered_call": {
        "keywords": ["covered call", "cc on", "writing calls", "sell call against"],
        "regex": []
    },
    "cash_secured_put": {
        "keywords": ["cash secured put", "csp", "sell put", "writing puts"],
        "regex": []
    },
    "iron_condor": {
        "keywords": ["iron condor", "ic", "condor"],
        "regex": []
    },
    "butterfly": {
        "keywords": ["butterfly", "fly"],
        "regex": []
    },
    "straddle": {
        "keywords": ["straddle", "long straddle", "short straddle"],
        "regex": []
    },
    "strangle": {
        "keywords": ["strangle", "long strangle", "short strangle"],
        "regex": []
    },
    "calls": {
        "keywords": ["call", "calls", "buying call", "long call"],
        "regex": [r"\d+c\b", r"\$\d+\s+call"]
    },
    "puts": {
        "keywords": ["put", "puts", "buying put", "long put"],
        "regex": [r"\d+p\b", r"\$\d+\s+put"]
    },
    "rolling": {
        "keywords": ["rolling", "roll to", "rolled", "roll up", "roll down", "roll out"],
        "regex": []
    },
    "close_profit": {
        "keywords": ["closed", "took profit", "sold for", "exit", "up $", "made $", "profit"],
        "regex": [r"up \d+%", r"made \$\d+", r"\+\$\d+"]
    },
    "dca_averaging": {
        "keywords": ["dca", "averaging", "adding", "scale in", "dollar cost"],
        "regex": []
    },
    "hedging": {
        "keywords": ["hedge", "hedging", "protection", "downside protection"],
        "regex": []
    },
}


def extract_ticker_and_strikes(text):
    """Extract ticker symbols and option strikes from message."""
    tickers = []
    strikes = []

    # Extract $TICKER mentions
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text)
    tickers.extend(dollar_tickers)

    # Extract strike prices
    strike_matches = re.findall(r'\$(\d+(?:\.\d+)?)\s*(?:c|p|call|put)', text.lower())
    strikes.extend(strike_matches)

    # Extract standalone strikes like "500c" or "100p"
    standalone_strikes = re.findall(r'(\d+)(?:c|p)\b', text.lower())
    strikes.extend(standalone_strikes)

    return list(set(tickers)), list(set(strikes))


def categorize_message(content):
    """Categorize a message into option strategy types."""
    content_lower = content.lower()
    categories = []

    for category, definition in PATTERNS.items():
        # Check keywords
        if any(kw in content_lower for kw in definition["keywords"]):
            categories.append(category)
            continue

        # Check regex patterns
        if any(re.search(pat, content_lower) for pat in definition["regex"]):
            categories.append(category)

    return categories if categories else ["general_discussion"]


def extract_expiration(content):
    """Extract option expiration dates from message."""
    # Look for date patterns
    date_patterns = [
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}',
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?',
        r'\d{1,2}/\d{1,2}/\d{2,4}',
        r'exp(?:iring)?\s+\w+\s+\d+',
    ]

    content_lower = content.lower()
    for pattern in date_patterns:
        match = re.search(pattern, content_lower)
        if match:
            return match.group(0)

    return None


def analyze_swings_channel():
    """Analyze all messages in the swings channel."""
    swings_file = Path("discord_history/swings/The Traveling Trader - ➤ 𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐀𝐋𝐄𝐑𝐓 ⚡ - 🚨┃stock-alerts [545047039084593163].json")

    if not swings_file.exists():
        print(f"❌ File not found: {swings_file}")
        return

    print(f"📊 Analyzing {swings_file.name}\n")

    # Try to load JSON, handle potential malformed end
    try:
        with open(swings_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Try to fix malformed JSON by ensuring proper closing
            if not content.rstrip().endswith('}'):
                # Find last complete message
                last_brace = content.rfind('    },')
                if last_brace > 0:
                    content = content[:last_brace + 6] + '\n  ]\n}'
            data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"⚠ JSON decode error, trying line-by-line parsing: {e}")
        # Fallback: extract messages array manually
        with open(swings_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find messages array start
        in_messages = False
        messages_json = []
        brace_count = 0
        current_msg = []

        for line in lines:
            if '"messages": [' in line:
                in_messages = True
                continue
            if in_messages:
                current_msg.append(line)
                brace_count += line.count('{') - line.count('}')

                # Complete message found
                if brace_count == 0 and current_msg and current_msg[0].strip().startswith('{'):
                    msg_text = ''.join(current_msg)
                    try:
                        messages_json.append(json.loads(msg_text.rstrip().rstrip(',')))
                    except:
                        pass
                    current_msg = []

        data = {"messages": messages_json}
        print(f"✓ Parsed {len(messages_json)} messages via fallback method\n")

    messages = data.get("messages", [])
    print(f"Total messages: {len(messages)}\n")

    # Storage
    categorized = defaultdict(list)
    ticker_counts = defaultdict(int)
    strategy_counts = defaultdict(int)
    expiration_distribution = defaultdict(int)

    # Analyze each message
    for msg in messages:
        content = msg.get("content", "")
        if not content or len(content) < 10:
            continue

        timestamp = msg.get("timestamp", "")
        author = msg.get("author", {}).get("name", "unknown")

        # Skip bot messages
        if msg.get("author", {}).get("isBot", False):
            continue

        # Categorize
        categories = categorize_message(content)
        tickers, strikes = extract_ticker_and_strikes(content)
        expiration = extract_expiration(content)

        # Store
        entry = {
            "timestamp": timestamp,
            "author": author,
            "content": content[:200],  # Truncate for summary
            "categories": categories,
            "tickers": tickers,
            "strikes": strikes,
            "expiration": expiration,
        }

        for cat in categories:
            categorized[cat].append(entry)
            strategy_counts[cat] += 1

        for ticker in tickers:
            ticker_counts[ticker] += 1

        if expiration:
            expiration_distribution[expiration] += 1

    # Generate report
    print("="*80)
    print("OPTION STRATEGY DISTRIBUTION")
    print("="*80)

    for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{strategy:<25} {count:>5} mentions")

    print(f"\n{'='*80}")
    print("TOP TICKERS MENTIONED")
    print("="*80)

    for ticker, count in sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"{ticker:<10} {count:>5} mentions")

    print(f"\n{'='*80}")
    print("EXPIRATION DISTRIBUTION (Top 20)")
    print("="*80)

    for exp, count in sorted(expiration_distribution.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"{exp:<30} {count:>5} mentions")

    # Save detailed categorization
    output_dir = Path("trade_categories/swings_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    for category, entries in categorized.items():
        if not entries:
            continue

        output_file = output_dir / f"{category}.jsonl"
        with open(output_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')

    print(f"\n✅ Detailed categorization saved to: {output_dir}/")

    # Generate summary report
    summary_file = Path("SWINGS_OPTIONS_ANALYSIS.md")
    with open(summary_file, 'w') as f:
        f.write("# Swings Channel Options Trading Analysis\n\n")
        f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Total Messages Analyzed:** {len(messages)}\n\n")

        f.write("## Strategy Distribution\n\n")
        for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(messages)) * 100
            f.write(f"- **{strategy}:** {count} mentions ({pct:.1f}%)\n")

        f.write("\n## Top Tickers\n\n")
        for ticker, count in sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)[:30]:
            f.write(f"- {ticker}: {count} mentions\n")

        f.write("\n## Strategy Characteristics\n\n")

        # LEAPS analysis
        if "leaps" in categorized:
            f.write("### LEAPS (Long-term)\n")
            f.write(f"- Count: {len(categorized['leaps'])}\n")
            leaps_tickers = [t for entry in categorized['leaps'] for t in entry['tickers']]
            leaps_top = defaultdict(int)
            for t in leaps_tickers:
                leaps_top[t] += 1
            f.write(f"- Top tickers: {', '.join([f'{t}({c})' for t, c in sorted(leaps_top.items(), key=lambda x: x[1], reverse=True)[:5]])}\n")
            f.write(f"- Typical duration: 6+ months to 2+ years\n\n")

        # Spreads analysis
        if "spreads" in categorized:
            f.write("### Spreads\n")
            f.write(f"- Count: {len(categorized['spreads'])}\n")
            f.write(f"- Types: Vertical, calendar, diagonal\n")
            f.write(f"- Purpose: Defined risk, lower cost basis\n\n")

        # Short-term calls/puts
        calls_count = strategy_counts.get("calls", 0)
        puts_count = strategy_counts.get("puts", 0)
        f.write("### Directional Options\n")
        f.write(f"- Calls: {calls_count} mentions\n")
        f.write(f"- Puts: {puts_count} mentions\n")
        ratio = f"{calls_count/puts_count:.2f}" if puts_count > 0 else "N/A"
        f.write(f"- Call/Put ratio: {ratio}\n\n")

        f.write("\n## Key Insights\n\n")

        # Determine primary strategy
        top_strategy = max(strategy_counts.items(), key=lambda x: x[1])[0]
        f.write(f"1. **Primary Strategy:** {top_strategy.replace('_', ' ').title()}\n")

        # Bullish vs bearish
        if calls_count > puts_count * 1.5 and puts_count > 0:
            ratio_str = f"{calls_count/puts_count:.1f}"
            f.write(f"2. **Directional Bias:** Bullish (calls outnumber puts {ratio_str}x)\n")
        elif puts_count > calls_count * 1.5 and calls_count > 0:
            ratio_str = f"{puts_count/calls_count:.1f}"
            f.write(f"2. **Directional Bias:** Bearish (puts outnumber calls {ratio_str}x)\n")
        else:
            f.write(f"2. **Directional Bias:** Neutral/Balanced\n")

        # Time horizon
        leaps_pct = (strategy_counts.get("leaps", 0) / len(messages)) * 100
        if leaps_pct > 10:
            f.write(f"3. **Time Horizon:** Mix of short-term and long-term (LEAPS: {leaps_pct:.1f}%)\n")
        else:
            f.write(f"3. **Time Horizon:** Primarily short to medium-term\n")

        # Risk profile
        spreads_pct = (strategy_counts.get("spreads", 0) / len(messages)) * 100
        if spreads_pct > 15:
            f.write(f"4. **Risk Management:** Active use of spreads for defined risk ({spreads_pct:.1f}%)\n")
        else:
            f.write(f"4. **Risk Management:** Mostly naked long options\n")

        f.write("\n## Example Trades by Category\n\n")

        for category in ["leaps", "spreads", "calls", "puts", "close_profit"]:
            if category in categorized and categorized[category]:
                f.write(f"### {category.replace('_', ' ').title()}\n\n")
                for entry in categorized[category][:3]:  # Show 3 examples
                    f.write(f"**{entry['timestamp'][:10]}** - {entry['author']}\n")
                    f.write(f"```\n{entry['content']}\n```\n")
                    if entry['tickers']:
                        f.write(f"Tickers: {', '.join(entry['tickers'])}\n")
                    if entry['strikes']:
                        f.write(f"Strikes: {', '.join(entry['strikes'])}\n")
                    if entry['expiration']:
                        f.write(f"Expiration: {entry['expiration']}\n")
                    f.write("\n")

    print(f"📄 Summary report saved to: {summary_file}")

    return categorized, strategy_counts, ticker_counts


if __name__ == "__main__":
    analyze_swings_channel()
