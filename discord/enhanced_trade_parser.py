#!/usr/bin/env python3
"""
Enhanced Discord Trade Parser

Capabilities:
1. Multi-message threading - Links related messages from same author
2. Chart OCR - Extracts levels from screenshots
3. Context understanding - Builds complete trades from partial info
4. State tracking - Tracks position lifecycle (entry → updates → exit)

Handles real-world Discord patterns:
- "Entered ES 6350" → "Stop 6345, target 6360" (separate messages)
- Chart images with visual levels
- Updates: "Moving stop to BE", "TP1 hit"
- Invalidations: "Setup broke", "Exiting"
"""

import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Import OCR if available
try:
    from discord.discord_chart_ocr import extract_chart_levels
    OCR_AVAILABLE = True
except:
    OCR_AVAILABLE = False


class TradeState:
    """Represents a trade in progress from a Discord user."""

    def __init__(self, author: str, symbol: str):
        self.author = author
        self.symbol = symbol
        self.entry = None
        self.stop = None
        self.target = None
        self.direction = None  # 'buy' or 'sell'
        self.messages = []  # List of message IDs that contributed
        self.first_seen = None
        self.last_updated = None
        self.status = 'building'  # 'building', 'complete', 'active', 'closed'
        self.exit_reason = None
        self.partial_exits = []

    def is_complete(self):
        """Check if we have all required info for a valid trade."""
        return all([self.entry, self.stop, self.target, self.direction])

    def to_signal(self):
        """Convert to trade signal format."""
        if not self.is_complete():
            return None

        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry': self.entry,
            'stop': self.stop,
            'target': self.target,
            'messages': self.messages,
            'first_seen': self.first_seen,
            'last_updated': self.last_updated,
            'status': self.status
        }


class EnhancedTradeParser:
    """Enhanced parser that understands multi-message trade sequences."""

    def __init__(self):
        self.active_trades = {}  # {(author, symbol): TradeState}
        self.last_symbol_by_author = {}  # {author: (symbol, timestamp)}
        self.message_window = timedelta(minutes=10)  # Group messages within 10 min

    def extract_symbol(self, content: str) -> Optional[str]:
        """Extract ticker symbol from message."""
        content_upper = content.upper()

        # Check for supported symbols
        symbols = re.findall(r'\b(SPY|QQQ|GLD|MES|MNQ|MGC|ES|NQ|GC|S&P|SPX|NASDAQ|NDX|GOLD)\b',
                            content_upper)

        if not symbols:
            return None

        symbol = symbols[0]

        # Normalize
        if symbol in ('MES', 'ES', 'S&P', 'SPX', 'SPY'):
            return 'SPY'
        elif symbol in ('MNQ', 'NQ', 'NASDAQ', 'NDX', 'QQQ'):
            return 'QQQ'
        elif symbol in ('MGC', 'GC', 'GOLD', 'GLD'):
            return 'GLD'

        return None

    def extract_direction(self, content: str) -> Optional[str]:
        """Extract trade direction from message."""
        content_lower = content.lower()

        # Explicit direction keywords
        if any(kw in content_lower for kw in ['buy', 'long', 'buying', 'going long', 'entered long']):
            return 'buy'
        elif any(kw in content_lower for kw in ['sell', 'short', 'selling', 'going short', 'entered short']):
            return 'sell'

        # Context clues
        if any(kw in content_lower for kw in ['looking for longs', 'bullish', 'upside']):
            return 'buy'
        elif any(kw in content_lower for kw in ['looking for shorts', 'bearish', 'downside']):
            return 'sell'

        return None

    def extract_price_levels(self, content: str) -> Dict[str, List[float]]:
        """Extract all price levels from message text."""
        levels = {
            'entries': [],
            'stops': [],
            'targets': []
        }

        content_lower = content.lower()

        # Find all numbers that look like prices
        prices = re.findall(r'\b(\d{2,5}(?:\.\d{1,2})?)\b', content)
        prices = [float(p) for p in prices if 100 < float(p) < 30000]  # Reasonable range

        # Pattern matching for labeled levels

        # Entry patterns (use flexible symbol matching)
        symbol_pattern = r'[a-z&]{2,6}'  # Matches ES, MES, S&P, etc.
        entry_patterns = [
            r'(?:entry|entered|got in|in at|@|at)\s*:?\s*[\$]?(\d{2,5}(?:\.\d{1,2})?)',
            rf'entered\s+{symbol_pattern}\s+(\d{{2,5}}(?:\.\d{{1,2}})?)',  # "entered ES 6350"
            rf'(?:buy|sell|long|short)\s+{symbol_pattern}\s+(\d{{2,5}}(?:\.\d{{1,2}})?)',  # "BUY MES 6350" or "SHORT S&P 6350"
            rf'{symbol_pattern}\s+(?:long|short)\s+(\d{{2,5}}(?:\.\d{{1,2}})?)',  # "ES long 6350"
            r'(\d{2,5}(?:\.\d{1,2})?)\s*(?:entry|long|short)',
        ]
        for pattern in entry_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                try:
                    price = float(match)
                    if 100 < price < 30000:
                        levels['entries'].append(price)
                except:
                    pass

        # Stop loss patterns
        stop_patterns = [
            r'(?:stop|sl|stop loss|stop @|stop:)\s*:?\s*[\$]?(\d{2,5}(?:\.\d{1,2})?)',
            r'(\d{2,5}(?:\.\d{1,2})?)\s*(?:stop|sl)',
            r'stop\s+(\d{2,5}(?:\.\d{1,2})?)',  # "Stop 6345"
        ]
        for pattern in stop_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                try:
                    price = float(match)
                    if 100 < price < 30000:
                        levels['stops'].append(price)
                except:
                    pass

        # Target patterns
        target_patterns = [
            r'(?:target|tp|take profit|tp @|tp:|targets?)\s*:?\s*[\$]?(\d{2,5}(?:\.\d{1,2})?)',
            r'(\d{2,5}(?:\.\d{1,2})?)\s*(?:target|tp)'
        ]
        for pattern in target_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                try:
                    price = float(match)
                    if 100 < price < 30000:
                        levels['targets'].append(price)
                except:
                    pass

        # If we have unlabeled prices, try to infer
        if prices and not (levels['entries'] or levels['stops'] or levels['targets']):
            # Use context and order
            if len(prices) >= 3:
                # Common pattern: entry, stop, target
                levels['entries'].append(prices[0])
                levels['stops'].append(prices[1])
                levels['targets'].append(prices[2])

        return levels

    def extract_from_chart(self, image_path: str, symbol: str) -> Dict:
        """Extract levels from chart image using OCR."""
        if not OCR_AVAILABLE:
            return {'entry': None, 'stop': None, 'targets': []}

        try:
            chart_data = extract_chart_levels(image_path)

            result = {
                'entry': chart_data.get('entry'),
                'stop': chart_data.get('stop_loss'),
                'targets': chart_data.get('take_profit', [])
            }

            return result
        except Exception as e:
            return {'entry': None, 'stop': None, 'targets': []}

    def detect_update_type(self, content: str) -> Optional[str]:
        """Detect if message is a trade update."""
        content_lower = content.lower()

        # Breakeven
        if any(kw in content_lower for kw in ['breakeven', 'break even', 'be', 'stop to be', 'moved stop']):
            return 'breakeven'

        # Partial exit
        if any(kw in content_lower for kw in ['tp1 hit', 'tp2 hit', 'partial', 'took some', 'half out']):
            return 'partial_exit'

        # Full exit - win
        if any(kw in content_lower for kw in ['tp hit', 'target hit', 'took profit', 'winner', 'closed for profit']):
            return 'exit_win'

        # Full exit - loss
        if any(kw in content_lower for kw in ['stopped out', 'sl hit', 'stop hit', 'took the loss', 'loser']):
            return 'exit_loss'

        # Invalidation
        if any(kw in content_lower for kw in ['invalid', 'scratch', 'setup broke', 'no longer valid', 'exiting']):
            return 'invalidation'

        return None

    def process_message(self, message: Dict, chart_images: List[str] = None) -> Optional[Dict]:
        """
        Process a single Discord message and update trade states.

        Args:
            message: Discord message dict with 'author', 'content', 'timestamp', etc.
            chart_images: List of image paths attached to this message

        Returns:
            Complete trade signal dict if a trade becomes complete, else None
        """
        author = message.get('author', {}).get('nickname') or message.get('author', {}).get('name', 'Unknown')
        content = message.get('content', '')
        timestamp = message.get('timestamp', '')
        message_id = message.get('id', '')

        # Parse timestamp
        try:
            msg_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(ET)
        except:
            msg_time = datetime.now(ET)

        # Extract symbol
        symbol = self.extract_symbol(content)

        # If no symbol found, try to use author's last symbol (within time window)
        if not symbol:
            if author in self.last_symbol_by_author:
                last_symbol, last_time = self.last_symbol_by_author[author]
                if msg_time - last_time < self.message_window:
                    symbol = last_symbol
                    print(f"  🔗 No symbol mentioned, using author's recent symbol: {symbol}")
                else:
                    print(f"  ⚠️  No symbol found and last mention too old")
                    return None
            else:
                print(f"  ⚠️  No symbol found in message")
                return None
        else:
            # Update last symbol for this author
            self.last_symbol_by_author[author] = (symbol, msg_time)

        # Get or create trade state
        key = (author, symbol)
        if key not in self.active_trades:
            self.active_trades[key] = TradeState(author, symbol)

        trade = self.active_trades[key]
        trade.messages.append(message_id)
        trade.last_updated = msg_time
        if not trade.first_seen:
            trade.first_seen = msg_time

        # Check for updates to existing trade
        update_type = self.detect_update_type(content)
        if update_type:
            if update_type == 'breakeven':
                trade.stop = trade.entry  # Move stop to breakeven
                print(f"  🔄 {author} moved {symbol} stop to breakeven")
            elif update_type == 'partial_exit':
                trade.partial_exits.append({'time': msg_time, 'reason': 'partial_tp'})
                print(f"  📊 {author} partial exit on {symbol}")
            elif update_type in ('exit_win', 'exit_loss'):
                trade.status = 'closed'
                trade.exit_reason = update_type
                print(f"  ✅ {author} closed {symbol}: {update_type}")
                # Keep for history but don't return as new signal
                return None
            elif update_type == 'invalidation':
                trade.status = 'invalidated'
                print(f"  ⚠️  {author} invalidated {symbol} setup")
                return None

        # Extract direction
        direction = self.extract_direction(content)
        if direction and not trade.direction:
            trade.direction = direction

        # Extract price levels from text
        levels = self.extract_price_levels(content)

        if levels['entries'] and not trade.entry:
            trade.entry = levels['entries'][0]
            print(f"  🎯 Extracted entry: {trade.entry}")
        if levels['stops'] and not trade.stop:
            trade.stop = levels['stops'][0]
            print(f"  🛑 Extracted stop: {trade.stop}")
        if levels['targets'] and not trade.target:
            trade.target = levels['targets'][0]
            print(f"  🎯 Extracted target: {trade.target}")

        # Extract from chart images if provided
        if chart_images and not trade.is_complete():
            for img_path in chart_images:
                chart_levels = self.extract_from_chart(img_path, symbol)

                if chart_levels['entry'] and not trade.entry:
                    trade.entry = chart_levels['entry']
                if chart_levels['stop'] and not trade.stop:
                    trade.stop = chart_levels['stop']
                if chart_levels['targets'] and not trade.target:
                    trade.target = chart_levels['targets'][0]

        # Check if trade is now complete
        if trade.is_complete() and trade.status == 'building':
            trade.status = 'complete'
            signal = trade.to_signal()

            # Validate direction vs levels
            if signal['direction'] == 'buy':
                if not (signal['stop'] < signal['entry'] < signal['target']):
                    print(f"  ⚠️  {author} {symbol} LONG levels invalid: stop {signal['stop']} | entry {signal['entry']} | target {signal['target']}")
                    return None
            else:
                if not (signal['target'] < signal['entry'] < signal['stop']):
                    print(f"  ⚠️  {author} {symbol} SHORT levels invalid: target {signal['target']} | entry {signal['entry']} | stop {signal['stop']}")
                    return None

            print(f"  ✅ {author} complete trade signal: {signal['direction'].upper()} {symbol} @ {signal['entry']}, SL {signal['stop']}, TP {signal['target']}")
            return signal

        return None

    def cleanup_stale_trades(self, max_age_hours: int = 24):
        """Remove trades that haven't been updated in max_age_hours."""
        now = datetime.now(ET)
        stale_keys = []

        for key, trade in self.active_trades.items():
            if trade.last_updated:
                age = now - trade.last_updated
                if age > timedelta(hours=max_age_hours):
                    stale_keys.append(key)

        for key in stale_keys:
            del self.active_trades[key]

        if stale_keys:
            print(f"  🧹 Cleaned up {len(stale_keys)} stale trades")

    def get_active_trade(self, author: str, symbol: str) -> Optional[TradeState]:
        """Get active trade for a specific author/symbol."""
        return self.active_trades.get((author, symbol))


# Singleton instance
_parser = None

def get_parser():
    """Get global parser instance."""
    global _parser
    if _parser is None:
        _parser = EnhancedTradeParser()
    return _parser


if __name__ == "__main__":
    # Test with sample messages
    parser = EnhancedTradeParser()

    # Simulate message sequence
    messages = [
        {
            'id': '1',
            'author': {'nickname': 'testuser'},
            'content': 'Looking at ES long setup',
            'timestamp': '2026-04-01T09:30:00-04:00'
        },
        {
            'id': '2',
            'author': {'nickname': 'testuser'},
            'content': 'Entered ES 6350',
            'timestamp': '2026-04-01T09:31:00-04:00'
        },
        {
            'id': '3',
            'author': {'nickname': 'testuser'},
            'content': 'Stop 6345, targets 6360 and 6370',
            'timestamp': '2026-04-01T09:32:00-04:00'
        }
    ]

    print("Processing message sequence:\n")
    for i, msg in enumerate(messages, 1):
        print(f"Message {i}: {msg['content']}")
        signal = parser.process_message(msg)

        # Debug: show current state
        author = msg['author']['nickname']
        symbol = parser.extract_symbol(msg['content'])
        if symbol:
            key = (author, symbol)
            if key in parser.active_trades:
                trade = parser.active_trades[key]
                print(f"  State: entry={trade.entry}, stop={trade.stop}, target={trade.target}, direction={trade.direction}, complete={trade.is_complete()}")

        if signal:
            print(f"\n✅ Complete trade signal generated:")
            print(json.dumps(signal, indent=2, default=str))
