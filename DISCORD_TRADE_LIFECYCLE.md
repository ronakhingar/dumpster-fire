# Discord Multi-Message Trade Lifecycle Tracking

## How It Works: Real Example

### Example Trade Sequence (from day-trade-alerts)

**Message 1** (10:05 AM):
```
ES short here @everyone
DOL is fake news pump from Monday premarket
```
*[Screenshot attached: Chart showing ES at 6550 with TP at 6500 and SL at 6570]*

**Message 2** (10:22 AM):
```
Up $600 per con here at low hanging fruit (1:1). Take it if you wish @everyone
I want to see SPX hit 6500
```

**Message 3** (10:45 AM):
```
$950 per con here. SPX is almost at 6500. Taking it off here. Great trade @everyone
```

---

## Step-by-Step Processing

### MESSAGE 1: Entry Detection

#### 1.1 Intent Detection
```python
detect_intent("ES short here @everyone DOL is fake news pump...")

# Pattern Matching:
✓ Matches "short_entry" pattern
  - keyword: "short"
  - keyword: "here"
  - context: "@everyone"
  - confidence: 0.95

# Entity Extraction:
  - Symbol: "ES" → normalized to "SPY"
  - Direction: "short"
  - Context: "DOL fake news pump"
```

#### 1.2 Database: Create Trade
```sql
INSERT INTO discord_trade_lifecycle (
    symbol: 'SPY',
    author_id: 123456789,
    author_name: 'TraderBob',
    channel_id: 981926799212679248,  -- day-trade-alerts
    status: 'open',
    direction: 'short',
    entry_message_id: 111111111111,
    entry_timestamp: '2026-03-27 10:05:00',
    entry_reasoning: 'DOL fake news pump',
    chart_entry_path: '/charts/111111111111.png'
)
RETURNING id = 42;
```

#### 1.3 Database: Save Intent
```sql
INSERT INTO message_intents (
    message_id: 111111111111,
    intent_type: 'entry',
    confidence: 0.95,
    trade_lifecycle_id: 42,
    symbols: ['SPY'],
    direction: 'short',
    keywords: ['short', 'here'],
    mentions_everyone: true,
    has_chart: true
)
```

#### 1.4 Chart Analysis (if screenshot attached)
```python
# OCR extracts from chart image:
{
    "entry": 6550,
    "stop_loss": 6570,
    "take_profit": 6500
}

# Update trade with levels:
UPDATE discord_trade_lifecycle
SET
    stop_loss = 6570,
    take_profit_1 = 6500,
    chart_entry_path = '/charts/111111111111.png'
WHERE id = 42;
```

#### Output:
```
✓ Created trade #42: SPY short by TraderBob
  Entry: ES short @ 10:05 AM
  Levels: SL $6570 | TP $6500 (from chart)
```

---

### MESSAGE 2: Update Detection

#### 2.1 Intent Detection
```python
detect_intent("Up $600 per con here at low hanging fruit...")

# Pattern Matching:
✓ Matches "profit_update" pattern
  - keyword: "$600"
  - keyword: "per con"
  - keyword: "up"
  - context: "@everyone"
  - confidence: 0.85

# Entity Extraction:
  - PnL: $600 per contract
  - Price mentioned: 6500 (target reference)
  - Action: "Take it if you wish" (partial exit offered)
```

#### 2.2 Find Linked Trade
```python
find_open_trade(author_id=123456789, symbol='SPY')
# Returns: trade_id = 42
```

#### 2.3 Database: Update Trade
```sql
UPDATE discord_trade_lifecycle
SET
    updates = updates || '{
        "timestamp": "2026-03-27 10:22:00",
        "message_id": 222222222222,
        "intent": "update",
        "pnl": 600,
        "price_levels": {"mentioned": [6500]}
    }',
    pnl_updates = pnl_updates || '{"222222222222": 600}',
    status = 'partial_close'  -- Offered partial exit
WHERE id = 42;
```

#### 2.4 Database: Save Intent
```sql
INSERT INTO message_intents (
    message_id: 222222222222,
    intent_type: 'update',
    confidence: 0.85,
    trade_lifecycle_id: 42,
    pnl_per_contract: 600,
    keywords: ['$600', 'per con', 'take it']
)
```

#### Output:
```
✓ Updated trade #42: update (PnL: $600)
  17 minutes in trade
  Partial profit available at 1:1 R:R
```

---

### MESSAGE 3: Exit Detection

#### 3.1 Intent Detection
```python
detect_intent("$950 per con here. SPX is almost at 6500. Taking it off...")

# Pattern Matching:
✓ Matches "full_exit" pattern
  - keyword: "taking it off"
  - keyword: "here"
  - context: "great trade"
  - context: "@everyone"
  - confidence: 0.95

# Entity Extraction:
  - PnL: $950 per contract
  - Price mentioned: 6500 (near target)
```

#### 3.2 Find Linked Trade
```python
find_open_trade(author_id=123456789, symbol='SPY')
# Returns: trade_id = 42
```

#### 3.3 Database: Close Trade
```sql
UPDATE discord_trade_lifecycle
SET
    status = 'closed',
    exit_message_ids = array_append(exit_message_ids, 333333333333),
    exit_timestamps = array_append(exit_timestamps, '2026-03-27 10:45:00'),
    exit_reasons = array_append(exit_reasons, 'target_hit'),
    final_pnl = 950,
    updates = updates || '{
        "timestamp": "2026-03-27 10:45:00",
        "message_id": 333333333333,
        "intent": "full_exit",
        "pnl": 950,
        "price_levels": {"mentioned": [6500]}
    }',
    closed_at = '2026-03-27 10:45:00'
WHERE id = 42;
```

#### 3.4 Database: Save Intent
```sql
INSERT INTO message_intents (
    message_id: 333333333333,
    intent_type: 'full_exit',
    confidence: 0.95,
    trade_lifecycle_id: 42,
    pnl_per_contract: 950,
    keywords: ['taking it off', '$950']
)
```

#### 3.5 Update Author Stats
```sql
UPDATE signal_author_stats
SET
    total_signals = total_signals + 1,
    signals_used = signals_used + 1,
    correct_calls = correct_calls + 1,  -- Winning trade
    total_pnl_impact = total_pnl_impact + 950,
    last_signal_at = NOW()
WHERE author_id = 123456789;
```

#### Output:
```
✓ Updated trade #42: full_exit (PnL: $950)
  Trade closed after 40 minutes
  WINNER: +$950 per contract
  TraderBob stats updated: 85% win rate (17 wins, 3 losses)
```

---

## Complete Trade Record

```sql
SELECT * FROM discord_trade_lifecycle WHERE id = 42;
```

**Result:**
```json
{
  "id": 42,
  "symbol": "SPY",
  "author_id": 123456789,
  "author_name": "TraderBob",
  "channel_id": 981926799212679248,

  "status": "closed",
  "direction": "short",

  "entry_message_id": 111111111111,
  "entry_price": null,
  "entry_timestamp": "2026-03-27 10:05:00",
  "entry_reasoning": "DOL fake news pump",

  "stop_loss": 6570,
  "take_profit_1": 6500,

  "exit_message_ids": [333333333333],
  "exit_timestamps": ["2026-03-27 10:45:00"],
  "exit_reasons": ["target_hit"],

  "pnl_updates": {
    "222222222222": 600,
    "333333333333": 950
  },
  "final_pnl": 950,

  "updates": [
    {
      "timestamp": "2026-03-27 10:22:00",
      "message_id": 222222222222,
      "intent": "update",
      "pnl": 600
    },
    {
      "timestamp": "2026-03-27 10:45:00",
      "message_id": 333333333333,
      "intent": "full_exit",
      "pnl": 950
    }
  ],

  "created_at": "2026-03-27 10:05:00",
  "updated_at": "2026-03-27 10:45:00",
  "closed_at": "2026-03-27 10:45:00"
}
```

---

## Intent Detection Patterns (Extensible)

### Built-in Patterns:

| Pattern Name | Intent Type | Keywords | Example |
|-------------|-------------|----------|---------|
| `short_entry` | entry | short, here | "ES short here @everyone" |
| `long_entry` | entry | long, here | "SPY long here" |
| `profit_update` | update | $XXX, per con | "Up $600 per con" |
| `partial_exit` | partial_exit | take it, if you wish | "Take it if you wish" |
| `full_exit` | full_exit | taking it off, closed | "Taking it off here" |
| `target_hit` | full_exit | target hit, reached | "Target hit at 6500" |
| `stopped_out` | stopped | stopped, hit stop | "Stopped out" |

### Custom Patterns:
Add new patterns via database:

```sql
INSERT INTO intent_patterns (
    pattern_name,
    intent_type,
    keyword_regex,
    confidence_score,
    priority
)
VALUES (
    'scale_in',
    'update',
    ARRAY['\\badding\\b', '\\bmore\\b', '\\bscale'],
    0.80,
    75
);
```

---

## How Agent Uses This Data

### 1. Real-Time Signal Extraction

When TraderBob enters a trade:

```python
# Agent checks recent trades from high-credibility authors
recent_trades = get_recent_open_trades(
    min_author_accuracy=0.70,
    lookback_minutes=60
)

for trade in recent_trades:
    if trade.symbol in ['SPY', 'QQQ']:
        if trade.direction == 'short':
            # Bearish signal from credible source
            discord_bonus += 8
            reason = f"TraderBob short (85% accuracy)"
```

### 2. Author Credibility Weighting

```sql
SELECT
    author_name,
    accuracy_rate,
    total_pnl_impact,
    avg_trade_duration_minutes
FROM trade_performance_summary
WHERE accuracy_rate > 0.70
  AND total_trades >= 10;
```

**Example Result:**
```
TraderBob:     85% win rate, $12,450 total PnL, avg 38 min trades
TraderAlice:   78% win rate, $8,200 total PnL, avg 52 min trades
TraderCharlie: 62% win rate, -$1,500 total PnL, avg 72 min trades
```

**Agent Action:**
- TraderBob signal → +10 points (high credibility)
- TraderAlice signal → +7 points (good credibility)
- TraderCharlie signal → +0 points (below threshold)

### 3. Pattern Learning

```sql
-- Which setups work best?
SELECT
    direction,
    AVG(final_pnl) as avg_pnl,
    COUNT(*) as trades,
    AVG(EXTRACT(EPOCH FROM (closed_at - entry_timestamp))/60) as avg_duration
FROM discord_trade_lifecycle
WHERE status = 'closed'
  AND final_pnl > 0
GROUP BY direction;
```

**Result:**
```
short: $725 avg, 45 trades, 42 min avg duration
long:  $612 avg, 38 trades, 56 min avg duration
```

**Agent Learning:** Short signals from this channel are more profitable → weight shorts higher.

---

## API for Agent Integration

```python
from discord_intent_detector import process_discord_message, find_open_trade
from discord_db import get_author_credibility

# When new Discord message arrives:
process_discord_message(
    message_id=msg.id,
    author_id=msg.author.id,
    author_name=msg.author.name,
    content=msg.content,
    timestamp=msg.timestamp,
    channel_id=msg.channel.id,
    has_chart=len(msg.attachments) > 0
)

# Agent checks for active signals:
open_trades = """
    SELECT * FROM open_trades
    WHERE symbols @> ARRAY['SPY']
      AND author_name IN (
          SELECT author_name FROM signal_author_stats
          WHERE accuracy_rate > 0.70
      )
    ORDER BY entry_timestamp DESC
    LIMIT 5
"""

# Weight decision based on author credibility:
author_stats = get_author_credibility('TraderBob')
if author_stats['accuracy_rate'] > 0.80:
    bonus_multiplier = 1.5
elif author_stats['accuracy_rate'] > 0.70:
    bonus_multiplier = 1.2
else:
    bonus_multiplier = 1.0
```

---

## Handling Edge Cases

### Multiple Trades from Same Author

```sql
-- Find most recent open trade by symbol
SELECT * FROM discord_trade_lifecycle
WHERE author_id = 123456789
  AND symbol = 'SPY'
  AND status IN ('open', 'partial_close')
ORDER BY entry_timestamp DESC
LIMIT 1;
```

### Unclear Intent Messages

```python
# If confidence < 0.70, flag for review
if intent_data['confidence'] < 0.70:
    # Store as 'unknown' intent
    # Human review later or ask author for clarification
    save_message_intent(message_id, {
        "intent_type": "unknown",
        "confidence": intent_data['confidence'],
        "requires_review": True
    })
```

### Missing Entry Message

```python
# If exit detected but no open trade:
if intent_type == 'full_exit' and not find_open_trade(author_id):
    # Create retroactive trade entry
    # Mark as "reconstructed" for lower confidence
    create_trade_retroactive(
        author_id=author_id,
        symbol=extracted_symbol,
        direction='inferred',
        status='closed',
        final_pnl=extracted_pnl,
        confidence='reconstructed'
    )
```

### Chart OCR Failures

```python
# If chart attached but OCR fails:
# - Store chart path
# - Mark for manual review
# - Use text-based levels as fallback
UPDATE discord_trade_lifecycle
SET
    chart_screenshots = array_append(chart_screenshots, chart_path),
    chart_levels = '{"ocr_failed": true, "manual_review": true}'
WHERE id = trade_id;
```

---

## Query Examples

**Get active signals for agent:**
```sql
SELECT
    tl.symbol,
    tl.direction,
    tl.entry_timestamp,
    tl.stop_loss,
    tl.take_profit_1,
    sa.accuracy_rate,
    sa.author_name,
    EXTRACT(EPOCH FROM (NOW() - tl.entry_timestamp))/60 as age_minutes
FROM open_trades tl
JOIN signal_author_stats sa ON tl.author_id = sa.author_id
WHERE tl.symbol IN ('SPY', 'QQQ')
  AND sa.accuracy_rate > 0.70
  AND EXTRACT(EPOCH FROM (NOW() - tl.entry_timestamp))/60 < 120
ORDER BY sa.accuracy_rate DESC, tl.entry_timestamp DESC;
```

**Check if signal aligns with agent's bias:**
```sql
-- Agent has bearish bias on SPY
-- Check if any high-credibility traders are short
SELECT COUNT(*) FROM open_trades
WHERE symbol = 'SPY'
  AND direction = 'short'
  AND author_name IN (
      SELECT author_name FROM signal_author_stats
      WHERE accuracy_rate > 0.75
  );
```

**Performance report:**
```sql
SELECT
    channel.name,
    COUNT(DISTINCT tl.author_id) as active_traders,
    COUNT(*) as total_trades,
    SUM(CASE WHEN tl.final_pnl > 0 THEN 1 ELSE 0 END) as wins,
    AVG(tl.final_pnl) as avg_pnl,
    AVG(EXTRACT(EPOCH FROM (tl.closed_at - tl.entry_timestamp))/60) as avg_duration_min
FROM discord_trade_lifecycle tl
JOIN discord_channels channel ON tl.channel_id = channel.id
WHERE tl.status = 'closed'
  AND tl.closed_at > NOW() - INTERVAL '7 days'
GROUP BY channel.name;
```

This system creates a **complete audit trail** of every trade called in Discord, with full lifecycle tracking and performance metrics to inform agent decisions.
