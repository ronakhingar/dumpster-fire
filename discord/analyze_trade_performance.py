#!/usr/bin/env python3
"""
Analyze Discord #day-trade-alerts channel for:
1. Message categorization by type and ticker
2. Win rate calculation for specific members
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Path to Discord history (use fixed version)
HISTORY_FILE = Path(__file__).parent.parent / "discord_history" / "day-trade-alerts_fixed.json"


def parse_discord_export(file_path):
    """Parse Discord chat export JSON (handle incomplete JSON)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        messages = data.get('messages', [])
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        print(f"  Attempting to extract messages from partial JSON...")

        # Try to read what we can
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find messages array
        match = re.search(r'"messages":\s*\[(.*)', content, re.DOTALL)
        if match:
            messages_json = '[' + match.group(1)
            # Try to find last complete message
            # Count opening and closing braces to find complete objects
            try:
                # Remove trailing incomplete data
                last_complete = messages_json.rfind('},')
                if last_complete > 0:
                    messages_json = messages_json[:last_complete+1] + ']'
                    messages = json.loads(messages_json)
                    print(f"  ✓ Extracted {len(messages)} messages from partial JSON")
                else:
                    messages = []
            except:
                messages = []
        else:
            messages = []

    return messages


def extract_ticker(content):
    """Extract ticker symbols from message content."""
    content_upper = content.upper()

    # Common tickers
    tickers = []

    # Specific patterns
    ticker_patterns = [
        r'\b(SPY|QQQ|ES|MES|NQ|MNQ|GC|MGC|GLD)\b',
        r'\b(TSLA|AAPL|NVDA|MSFT|AMZN|META|GOOGL|NFLX)\b',
        r'\b(SPX|NDX|NASDAQ|S&P)\b'
    ]

    for pattern in ticker_patterns:
        matches = re.findall(pattern, content_upper)
        tickers.extend(matches)

    # Deduplicate
    return list(set(tickers))


def categorize_message(content):
    """Categorize message by type."""
    content_lower = content.lower()

    # Entry signals
    if any(kw in content_lower for kw in ['entry', 'buy', 'long', 'sell', 'short', 'adding', 'opened']):
        if any(kw in content_lower for kw in ['@', 'at', 'entry']) and \
           any(kw in content_lower for kw in ['stop', 'sl', 'target', 'tp']):
            return 'ENTRY_SIGNAL'

    # Exit signals
    if any(kw in content_lower for kw in ['exit', 'closed', 'took profit', 'stopped out', 'tp hit', 'sl hit']):
        return 'EXIT_SIGNAL'

    # Invalidation
    if any(kw in content_lower for kw in ['invalid', 'scratch', 'cancel', 'no longer valid', 'abort']):
        return 'INVALIDATION'

    # Update/commentary
    if any(kw in content_lower for kw in ['watching', 'looking at', 'monitoring', 'waiting for']):
        return 'WATCHING'

    # Analysis/context
    if any(kw in content_lower for kw in ['analysis', 'chart', 'level', 'support', 'resistance', 'fvg', 'ob']):
        return 'ANALYSIS'

    return 'OTHER'


def parse_trade_outcome(content):
    """Determine if message indicates win/loss."""
    content_lower = content.lower()

    # Win indicators
    win_keywords = ['tp hit', 'target hit', 'took profit', 'winner', 'profit', '+', 'green']
    if any(kw in content_lower for kw in win_keywords):
        # Check for dollar amounts or percentages
        if re.search(r'\+\$?\d+|\+\d+%|profit', content_lower):
            return 'WIN'

    # Loss indicators
    loss_keywords = ['stopped out', 'sl hit', 'stop hit', 'loss', 'loser', '-', 'red']
    if any(kw in content_lower for kw in loss_keywords):
        if re.search(r'-\$?\d+|-\d+%|loss', content_lower):
            return 'LOSS'

    # Breakeven
    if any(kw in content_lower for kw in ['breakeven', 'be', 'scratch']):
        return 'BREAKEVEN'

    return None


def analyze_member_trades(messages, username):
    """Analyze trades for a specific member (match by name or nickname)."""
    member_messages = [
        m for m in messages
        if m.get('author', {}).get('name') == username or
           m.get('author', {}).get('nickname') == username
    ]

    print(f"\n{'='*72}")
    print(f"  MEMBER ANALYSIS: {username}")
    print(f"{'='*72}")
    print(f"  Total messages: {len(member_messages)}")

    # Categorize messages
    categories = defaultdict(int)
    tickers = defaultdict(int)
    outcomes = defaultdict(int)

    trades = []

    for msg in member_messages:
        content = msg.get('content', '')

        # Category
        category = categorize_message(content)
        categories[category] += 1

        # Tickers
        msg_tickers = extract_ticker(content)
        for ticker in msg_tickers:
            tickers[ticker] += 1

        # Outcome
        outcome = parse_trade_outcome(content)
        if outcome:
            outcomes[outcome] += 1
            trades.append({
                'timestamp': msg.get('timestamp'),
                'content': content[:200],
                'outcome': outcome,
                'tickers': msg_tickers
            })

    # Print categories
    print(f"\n  📊 Message Categories:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"     {cat}: {count}")

    # Print tickers
    print(f"\n  🎯 Tickers Mentioned:")
    for ticker, count in sorted(tickers.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"     {ticker}: {count} times")

    # Calculate win rate
    total_outcomes = sum(outcomes.values())
    if total_outcomes > 0:
        wins = outcomes.get('WIN', 0)
        losses = outcomes.get('LOSS', 0)
        breakeven = outcomes.get('BREAKEVEN', 0)

        win_rate = (wins / total_outcomes * 100) if total_outcomes > 0 else 0

        print(f"\n  💰 Trade Outcomes:")
        print(f"     Wins: {wins}")
        print(f"     Losses: {losses}")
        print(f"     Breakeven: {breakeven}")
        print(f"     Total: {total_outcomes}")
        print(f"     Win Rate: {win_rate:.1f}%")

        if wins + losses > 0:
            win_rate_excluding_be = (wins / (wins + losses) * 100)
            print(f"     Win Rate (excl. BE): {win_rate_excluding_be:.1f}%")
    else:
        print(f"\n  ⚠️  No clear trade outcomes found in messages")

    # Show recent trades
    if trades:
        print(f"\n  📋 Recent Trade Outcomes (last 10):")
        for trade in trades[-10:]:
            try:
                # Handle various timestamp formats
                ts_str = trade['timestamp'].replace('Z', '+00:00')
                # Handle fractional seconds with varying precision
                if '.' in ts_str and '+' in ts_str:
                    parts = ts_str.split('+')
                    dt_part = parts[0]
                    tz_part = '+' + parts[1]
                    # Ensure fractional seconds have 6 digits
                    if '.' in dt_part:
                        main, frac = dt_part.split('.')
                        frac = frac.ljust(6, '0')[:6]  # Pad or truncate to 6 digits
                        ts_str = f"{main}.{frac}{tz_part}"

                timestamp = datetime.fromisoformat(ts_str)
                outcome_emoji = "✅" if trade['outcome'] == 'WIN' else "❌" if trade['outcome'] == 'LOSS' else "➖"
                tickers_str = ", ".join(trade['tickers']) if trade['tickers'] else "N/A"
                print(f"     {outcome_emoji} {timestamp.strftime('%Y-%m-%d %H:%M')} | {tickers_str}")
                print(f"        {trade['content'][:100]}...")
            except Exception as e:
                # Skip trades with bad timestamps
                continue

    return {
        'username': username,
        'total_messages': len(member_messages),
        'categories': dict(categories),
        'tickers': dict(tickers),
        'outcomes': dict(outcomes),
        'trades': trades
    }


def analyze_overall_channel(messages):
    """Analyze overall channel statistics."""
    print(f"\n{'='*72}")
    print(f"  CHANNEL OVERVIEW: #day-trade-alerts")
    print(f"{'='*72}")
    print(f"  Total messages: {len(messages)}")

    # Get unique authors
    authors = defaultdict(int)
    for msg in messages:
        author = msg.get('author', {}).get('name', 'Unknown')
        authors[author] += 1

    print(f"  Total unique members: {len(authors)}")
    print(f"\n  📊 Top 10 Most Active Members:")
    for author, count in sorted(authors.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"     {author}: {count} messages")

    # Overall categories
    categories = defaultdict(int)
    tickers = defaultdict(int)

    for msg in messages:
        content = msg.get('content', '')
        cat = categorize_message(content)
        categories[cat] += 1

        for ticker in extract_ticker(content):
            tickers[ticker] += 1

    print(f"\n  📊 Message Types:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(messages) * 100) if len(messages) > 0 else 0
        print(f"     {cat}: {count} ({pct:.1f}%)")

    print(f"\n  🎯 Top 15 Tickers:")
    for ticker, count in sorted(tickers.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"     {ticker}: {count} mentions")


def main():
    """Main analysis."""
    print("\n" + "="*72)
    print("  DISCORD #day-trade-alerts ANALYSIS")
    print("="*72)

    if not HISTORY_FILE.exists():
        print(f"  ❌ History file not found: {HISTORY_FILE}")
        return

    print(f"  📂 Loading: {HISTORY_FILE.name}")
    messages = parse_discord_export(HISTORY_FILE)

    # Overall channel analysis
    analyze_overall_channel(messages)

    # Analyze specific members
    target_members = ['kirstencumbiaparty', 'j u s t i i n']

    results = {}
    for member in target_members:
        results[member] = analyze_member_trades(messages, member)

    # Summary comparison
    print(f"\n{'='*72}")
    print(f"  MEMBER COMPARISON")
    print(f"{'='*72}")

    for member in target_members:
        if member in results:
            data = results[member]
            outcomes = data['outcomes']
            total = sum(outcomes.values())
            wins = outcomes.get('WIN', 0)
            losses = outcomes.get('LOSS', 0)

            win_rate = (wins / total * 100) if total > 0 else 0
            win_rate_excl = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

            print(f"\n  {member}:")
            print(f"     Messages: {data['total_messages']}")
            print(f"     Trades: {total}")
            print(f"     Win Rate: {win_rate:.1f}%")
            print(f"     Win Rate (excl. BE): {win_rate_excl:.1f}%")
            print(f"     Record: {wins}W - {losses}L - {outcomes.get('BREAKEVEN', 0)}BE")


if __name__ == "__main__":
    main()
