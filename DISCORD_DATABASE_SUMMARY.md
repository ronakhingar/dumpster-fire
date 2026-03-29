# Discord Database Integration - Complete Summary

## What Was Built

A **robust, production-ready Discord signal system** with full database tracking, multi-message trade lifecycle support, and chart OCR.

---

## Architecture

```
Discord Message → Database Storage → Intent Detection → Trade Lifecycle
                                                              ↓
                                              Chart OCR (TP/SL extraction)
                                                              ↓
                                              Agent Integration
                                                              ↓
                                              Performance Tracking
```

---

## Database Schema

### Core Tables

#### 1. **discord_channels**
```sql
- id: Discord channel ID
- name: stock-alerts, day-trade-alerts, swings
- priority: high/medium/low
- enabled: active monitoring flag
```

#### 2. **discord_messages**
```sql
- id: Discord message ID
- author_id, author_name
- content: message text
- timestamp
- attachments: chart images (JSON)
- reactions: emoji reactions (JSON)
```

#### 3. **discord_signals** (Market Analysis)
```sql
- message_id → links to discord_messages
- channel_id → links to discord_channels
- symbols: ['SPY', 'QQQ']
- sentiment: bullish/bearish/neutral
- confidence: high/medium/low
- support_levels, resistance_levels (JSON)
- key_insights, risk_factors (arrays)
- expires_at: 4 hours default
```

#### 4. **discord_trade_lifecycle** (Multi-Message Trades)
```sql
- symbol, direction: SPY short
- author_id, author_name
- status: open → partial_close → closed
- entry_message_id, entry_timestamp
- stop_loss, take_profit_1, take_profit_2
- exit_message_ids[] (array - multiple exits)
- pnl_updates (JSON): {message_id: pnl_amount}
- final_pnl
- updates (JSON): complete timeline
```

#### 5. **message_intents** (Intent Classification)
```sql
- message_id
- intent_type: entry, update, partial_exit, full_exit, stopped
- confidence: 0.0 - 1.0
- trade_lifecycle_id: links to trade
- symbols, direction, pnl_amount
- keywords: matched patterns
```

#### 6. **signal_performance** (Trade Outcomes)
```sql
- signal_id → links to discord_signals
- trade_id: agent's trade ID
- entry_price, exit_price, pnl
- result: win/loss
- signal_accuracy: correct/incorrect
```

#### 7. **signal_author_stats** (Credibility Tracking)
```sql
- author_id, author_name
- total_signals, signals_used
- correct_calls, incorrect_calls
- accuracy_rate
- avg_score_bonus, total_pnl_impact
- best_symbols, best_sentiment
```

---

## Features

### 1. Multi-Message Trade Tracking

**Example:**
```
Message 1 (10:05 AM): "ES short here @everyone"
  → Creates trade lifecycle record (status: open)

Message 2 (10:22 AM): "Up $600 per con here"
  → Updates trade with PnL (status: partial_close)

Message 3 (10:45 AM): "$950 per con. Taking it off"
  → Closes trade, final PnL recorded (status: closed)
```

**Database Links Messages:**
- All 3 messages linked to same `trade_lifecycle_id`
- Complete audit trail preserved
- P&L progression tracked

### 2. Intent Detection (Pattern-Based)

**Built-in Patterns:**
- `short_entry`: "ES short here @everyone"
- `long_entry`: "SPY long here"
- `profit_update`: "Up $600 per con"
- `partial_exit`: "Take it if you wish"
- `full_exit`: "Taking it off here"
- `target_hit`: "Target hit at 6500"
- `stopped_out`: "Stopped out"

**Extensible:** Add custom patterns via database

### 3. Chart OCR (TP/SL Extraction)

**Methods:**
- **Color Detection:** Green zones = TP, Red zones = SL
- **OCR Text Extraction:** "TP: 6500", "SL: 6550"
- **Hybrid:** Combines both methods

**Detects:**
- Entry levels
- Stop Loss (red zones)
- Take Profit levels (green zones)
- Support/Resistance zones

**Example:**
```python
chart_levels = extract_chart_levels('/path/to/chart.png')
# Returns:
{
    "entry": 6525,
    "stop_loss": 6550,
    "take_profit": [6500, 6475],
    "confidence": 0.85
}
```

### 4. Author Credibility Scoring

**Tracks:**
- Win rate per author
- Total P&L impact
- Average score bonus provided
- Best symbols (specialization)

**Agent Uses:**
```python
if author_accuracy > 0.80:
    bonus_multiplier = 1.5  # High credibility
elif author_accuracy > 0.70:
    bonus_multiplier = 1.2  # Good credibility
else:
    bonus_multiplier = 0.0  # Below threshold
```

### 5. Performance Analytics

**Queries:**
- Which channels provide best signals?
- Which authors are most accurate?
- Which setups work best?
- What's the average trade duration?

**Views:**
- `active_discord_signals` - Ready for agent
- `open_trades` - Waiting for updates
- `trade_performance_summary` - By author
- `signal_effectiveness` - By channel/sentiment

---

## How Agent Uses It

### Step 1: Check Active Signals
```sql
SELECT * FROM active_discord_signals
WHERE 'SPY' = ANY(symbols)
  AND author_name IN (
      SELECT author_name FROM signal_author_stats
      WHERE accuracy_rate > 0.70
  );
```

### Step 2: Calculate Bonus
```python
# High-credibility author with matching sentiment
if signal.sentiment == agent_bias and author_accuracy > 0.75:
    bonus = +10 points
    reason = f"{author_name} signal (78% accuracy)"

# At predicted support level
if abs(current_price - signal.support_level) / current_price < 0.01:
    bonus += 8 points
    reason += f" | At support ${signal.support_level}"
```

### Step 3: Apply to A+ Score
```
Base Score: 70
Discord Bonus: +18
FINAL: 88 ✅ (Qualifies for trade)
```

### Step 4: Track Outcome
```sql
-- When trade closes:
UPDATE signal_performance
SET exit_price = 552.80,
    pnl = 162.00,
    result = 'win',
    signal_accuracy = 'correct'
WHERE trade_id = '2026-03-27_103200_SPY';

-- Update author stats:
UPDATE signal_author_stats
SET correct_calls = correct_calls + 1,
    accuracy_rate = correct_calls / (correct_calls + incorrect_calls)
WHERE author_name = 'TraderBob';
```

---

## Files Created

### Database Migrations
- `db/discord_signals_migration.sql` - Signal tables
- `db/discord_trades_enhancement.sql` - Trade lifecycle tables

### Python Modules
- `discord_db.py` - Database operations
- `discord_intent_detector.py` - Pattern matching & intent detection
- `discord_chart_ocr.py` - Chart image analysis
- `discord_monitor.py` - Notification capture (existing)
- `discord_signal_extractor.py` - Signal extraction (existing)

### Documentation
- `DISCORD_DECISION_FLOW.md` - Step-by-step example
- `DISCORD_TRADE_LIFECYCLE.md` - Multi-message tracking
- `DISCORD_DATABASE_SUMMARY.md` - This file

---

## Setup Instructions

### 1. Install Dependencies
```bash
# Chart OCR dependencies
pip install opencv-python pillow pytesseract
brew install tesseract  # macOS
```

### 2. Run Database Migrations
```bash
# Apply migrations (adjust for your DB connection)
psql $DATABASE_URL < db/discord_signals_migration.sql
psql $DATABASE_URL < db/discord_trades_enhancement.sql
```

### 3. Initialize Channels
```bash
python3 discord_db.py --init
```

### 4. Test System
```bash
# Test intent detection
python3 discord_intent_detector.py --test

# Test chart OCR (requires sample chart)
python3 discord_chart_ocr.py --test

# Test database queries
python3 discord_db.py --test
```

### 5. Process Messages
```python
from discord_intent_detector import process_discord_message

# When Discord message arrives:
process_discord_message(
    message_id=msg.id,
    author_id=msg.author.id,
    author_name=msg.author.name,
    content=msg.content,
    timestamp=msg.timestamp,
    channel_id=msg.channel.id,
    has_chart=len(msg.attachments) > 0
)
```

---

## Query Examples

**Get active signals with credibility:**
```sql
SELECT
    s.symbols,
    s.sentiment,
    s.support_levels,
    sa.accuracy_rate,
    sa.author_name
FROM active_discord_signals s
JOIN signal_author_stats sa ON s.author_name = sa.author_name
WHERE s.symbols && ARRAY['SPY', 'QQQ']
  AND sa.accuracy_rate > 0.70
ORDER BY sa.accuracy_rate DESC;
```

**Find open trades from high-performing authors:**
```sql
SELECT
    tl.*,
    sa.accuracy_rate,
    EXTRACT(EPOCH FROM (NOW() - tl.entry_timestamp))/60 as age_minutes
FROM open_trades tl
JOIN signal_author_stats sa ON tl.author_id = sa.author_id
WHERE sa.accuracy_rate > 0.75
  AND tl.symbol IN ('SPY', 'QQQ')
ORDER BY tl.entry_timestamp DESC;
```

**Channel performance report:**
```sql
SELECT
    c.name,
    COUNT(DISTINCT tl.author_id) as traders,
    COUNT(*) as trades,
    AVG(CASE WHEN tl.final_pnl > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
    AVG(tl.final_pnl) as avg_pnl
FROM discord_trade_lifecycle tl
JOIN discord_channels c ON tl.channel_id = c.id
WHERE tl.status = 'closed'
  AND tl.closed_at > NOW() - INTERVAL '30 days'
GROUP BY c.name;
```

**Author specialization analysis:**
```sql
SELECT
    author_name,
    symbol,
    direction,
    COUNT(*) as trades,
    AVG(final_pnl) as avg_pnl,
    AVG(CASE WHEN final_pnl > 0 THEN 1.0 ELSE 0.0 END) as win_rate
FROM discord_trade_lifecycle
WHERE status = 'closed'
  AND final_pnl IS NOT NULL
GROUP BY author_name, symbol, direction
HAVING COUNT(*) >= 5
ORDER BY win_rate DESC, avg_pnl DESC;
```

---

## Next Steps

### Agent Integration
1. Import `discord_db.get_active_signals()` in agent.py
2. Add Discord bonus calculation in A+ scoring
3. Call `discord_db.log_signal_usage()` when trade placed
4. Call `discord_db.update_trade_outcome()` when trade closes

### Chart Notifications
1. Set up macOS notification capture for chart attachments
2. Call `discord_chart_ocr.process_chart_from_notification()`
3. Store extracted levels in `discord_trade_lifecycle.chart_levels`

### Continuous Learning
1. Weekly cron: Analyze signal effectiveness
2. Adjust author credibility scores
3. Identify best-performing patterns
4. Update agent weighting based on results

---

## Key Benefits

✅ **Complete Audit Trail** - Every message, every trade, full history
✅ **Multi-Message Tracking** - Links entry → updates → exit automatically
✅ **Author Credibility** - Learns which traders to trust over time
✅ **Chart Analysis** - Extracts TP/SL from screenshots automatically
✅ **Performance Analytics** - Data-driven signal weighting
✅ **Extensible Patterns** - Add new intent patterns without code changes
✅ **Channel Comparison** - Know which Discord channels provide best signals

This creates a **self-improving system** where Discord signals get smarter over time based on actual trading outcomes.
