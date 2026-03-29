# Discord Signal Decision Flow - Step by Step

## Example Message (from day-trade-alerts channel)

```
QQQ is officially in a correction down 10% from highs almost at the 300MA (SPY is down 7.5%).
I make a habit of adding indices to my portfolio if we drop 10%. Next level is $538.

Now, I don't think this is the absolute bottom, but with all of the tension building up
recently and everyone expecting a full ground invasion, I think the market rallies a bit
in the short term whether we get one or not, after next week. The character will look a
bit different though. If Trump fully tacos, we get a violent snapback rally immediately
that could take us to at least halfway up of this drop. If there is a ground invasion,
we might see a big gap down first that will quickly get bought up.

Whether the rally is sustained will depend on a lot of factors. But oil is going to be a
big factor this year IMO whether we get worse than a correction. If oil prices stay above
$100 for a sustained period (months) we could fall into a global recession by end of year.
Whatever happens with the war has to include a mechanism to stop oil from spiking.

Yes, the issues with the stock market started before the war. We mainly needed a valuation
reset and a break from the AI circle jerk. Every single Mag7 is now in a correction and
all besides AAPL are in a bear market. Historically if you bought the Mag7 here you'd more
than likely be profitable the next year. I don't mind nibbling here on the ones with
compressed PE's (MSFT, META, GOOGL, NVDA) although I think most will go lower plausibly.

Remember that the market was barely down 2% and tech stocks were getting hammered as
valuations in tech were being reset. So this breakdown is not as easy to read as previous
eras where every stock tanked at the same time. Nasdaq valuations have finally subsided
to a 25 P/E, which is in the 25th-75th percentile range historically. S&P 500 fell below
the 5y avg for forward P/E, heading towards the 10y avg. Tech is well below the 10y avg.
You can see the other sectors holding up really well (energy, industrials, staples).

As the market trickles down investors tend to get lulled into a deep sleep, assuming it's
going to keep tanking. Fun fact, since WWII there have been 105 pullbacks of -5% or more
in the S&P 500. ONLY 26 turned into a -10%+ correction and only 13 into a full -20%+ bear
market.

I still think we get at least a correction as the weekly moving averages officially cross
down, which has almost always led to one. I would love to visit the Liberation Day gap below.
But realistic targets for SPY are $613 and $590. QQQ are $540 and $520. @everyone
```

---

## Step-by-Step Processing & Decision Flow

### STEP 1: Message Capture & Storage

**Database: `discord_messages` table**

```sql
INSERT INTO discord_messages (
    id,              -- 1234567890123456789 (Discord message ID)
    author_id,       -- 987654321 (Discord user ID)
    author_name,     -- "TradingGuru"
    content,         -- Full message text
    timestamp,       -- 2026-03-26 14:30:00
    attachments,     -- NULL (no images/charts)
    reactions        -- {thumbs_up: 15, fire: 8}
)
```

**Database: `discord_channels` table (pre-configured)**

```sql
-- Already exists:
discord_channels:
  id: 981926799212679248
  name: 'day-trade-alerts'
  priority: 'high'
  enabled: true
```

---

### STEP 2: Signal Extraction (LLM or Pattern Matching)

**Extraction Process:**

#### 2.1 Symbol Detection
- **Found:** QQQ, SPY, MSFT, META, GOOGL, NVDA, AAPL
- **Agent-Relevant:** QQQ, SPY (others filtered out - not in ALLOWED_SYMBOLS)

#### 2.2 Sentiment Analysis
- **Overall:** Mixed/Neutral trending bearish
  - **Short-term (next week):** Bullish bounce expected
  - **Medium-term:** Bearish continuation likely
  - **Confidence:** Medium (hedged language: "I think", "plausibly")

#### 2.3 Price Level Extraction
```json
{
  "SPY": {
    "current_context": "down 7.5%",
    "support_levels": [613, 590],
    "technical_note": "Below 5y avg forward P/E"
  },
  "QQQ": {
    "current_context": "down 10%, at 300MA",
    "support_levels": [540, 520],
    "key_level": 538,
    "technical_note": "Nasdaq PE at 25 (historical range)"
  }
}
```

#### 2.4 Key Insights Extraction
```python
key_insights = [
    "QQQ officially in correction (-10%), testing 300MA support",
    "Short-term bounce expected before more downside",
    "Historical stat: Only 26 of 105 pullbacks became 10%+ corrections",
    "Weekly MA cross down - typically leads to correction",
    "Mag7 all in correction except AAPL",
    "Valuations compressed to historical norms (Nasdaq PE: 25)",
    "Energy, industrials, staples holding up well"
]
```

#### 2.5 Risk Factors Extraction
```python
risk_factors = [
    "Oil above $100 could trigger recession (sustained period)",
    "Ground invasion scenario - gap down then bounce",
    "Geopolitical uncertainty - war impact on markets",
    "Weekly moving averages crossed down bearishly"
]
```

#### 2.6 Catalysts Identified
```python
catalysts = [
    "Ground invasion (expected after next week)",
    "Oil price movement (watching $100 level)",
    "Liberation Day gap visit (downside target)",
    "Valuation reset completion"
]
```

**Database: `discord_signals` table**

```sql
INSERT INTO discord_signals (
    message_id: 1234567890123456789,
    channel_id: 981926799212679248,

    signal_type: 'market_analysis',
    confidence: 'medium',
    time_horizon: 'mixed',  -- short_term bullish, medium_term bearish

    symbols: ['QQQ', 'SPY'],
    sentiment: 'mixed_bearish',

    support_levels: {
        "SPY": [613, 590],
        "QQQ": [540, 520, 538]
    },

    resistance_levels: null,  -- Not mentioned

    key_insights: [
        "QQQ -10% correction at 300MA",
        "Short-term bounce expected",
        "Historical: 26/105 pullbacks → 10%+ correction",
        "Weekly MA death cross",
        ...
    ],

    risk_factors: [
        "Oil >$100 recession risk",
        "Ground invasion risk",
        ...
    ],

    catalysts: [
        "Ground invasion timing",
        "Oil price trajectory",
        ...
    ],

    regime_context: 'correction',

    technical_levels: {
        "QQQ_300MA": 538,
        "SPY_5y_avg_PE": "below",
        "Nasdaq_PE": 25
    },

    valuation_notes: "Nasdaq PE 25 (25th-75th percentile), S&P below 5y avg, tech below 10y avg",

    sector_context: "Energy, industrials, staples outperforming",

    expires_at: '2026-03-26 18:30:00',  -- 4 hours from extraction

    raw_text_snippet: "QQQ is officially in a correction down 10%..."
)
```

---

### STEP 3: Agent Trading Cycle (10:32 AM ET - 2 minutes later)

#### 3.1 Agent Scans Market
```
Current State:
  - SPY: $647.20 (above support levels 613, 590)
  - QQQ: $543.80 (near key level $538/$540)
  - Killzone: NY AM (active)
  - Macro window: No (10:32 AM - not in window)
```

#### 3.2 Agent Runs Analysis
**Detected Setup: QQQ oversold_reversal (potential long)**

```
Market State:
  - Price: $543.80
  - EMA-9: $541.50
  - EMA-21: $546.30
  - RSI: 31.2 (oversold territory)
  - MACD: Negative but histogram flattening
  - Daily bias: Bearish (downtrend)
```

**Intraday Signal:**
- 15-min timeframe showing bullish divergence
- Price above EMA-9 (reclaim)
- Volume spike on last candle
- **Recommendation:** BUY (counter-trend bounce)

---

### STEP 4: Discord Signal Integration

#### 4.1 Load Active Signals
```sql
SELECT * FROM active_discord_signals
WHERE 'QQQ' = ANY(symbols)
  AND expires_at > NOW()
ORDER BY extracted_at DESC
LIMIT 1;
```

**Returns:** Our signal (extracted 28 minutes ago)

#### 4.2 Calculate Signal Bonus

**Function:** `calculate_signal_bonus(symbol='QQQ', side='buy', price=543.80)`

**Analysis:**

```python
# Sentiment Check
signal_sentiment = 'mixed_bearish'
agent_side = 'buy'
time_horizon = 'mixed'  # Short-term bullish mentioned

# Short-term = bullish bounce expected
if 'short_term bounce expected' in key_insights:
    sentiment_match = True  # Partial alignment
    confidence_level = 'medium'
    bonus += 5  # Medium confidence alignment

# Price Level Check
support_levels_QQQ = [540, 520, 538]
current_price = 543.80

for support in support_levels_QQQ:
    distance = abs(current_price - support) / current_price
    if distance < 0.01:  # Within 1%
        bonus += 8
        reason = f"At support level ${support}"
        # 543.80 vs 540 = 0.7% away
        # MATCH! +8 points

# Risk Factor Warning
if 'Oil >$100 recession risk' in risk_factors:
    # Add context to trade notes
    warnings.append("⚠ Discord: Macro risk - oil/recession")

# Technical Confirmation
if 'QQQ -10% correction at 300MA' in key_insights:
    # Supports oversold bounce thesis
    bonus += 2
    reason += " | Oversold at 300MA"

TOTAL_BONUS = 5 + 8 + 2 = 15 points
```

#### 4.3 Apply to A+ Scoring

**Base A+ Score (before Discord):**
```
Criteria Scoring:
  liquidity_sweep: ✓ (15 pts) - swept lows
  market_structure_shift: ✗ (0 pts) - no MSS yet
  fvg_present: ✗ (0 pts)
  displacement: ✗ (0 pts)
  killzone_timing: ✓ (10 pts) - NY AM
  premium_discount: ✓ (10 pts) - discount zone
  ema_confirmation: ✓ (5 pts) - above EMA-9
  vwap_confluence: ✓ (5 pts)
  rsi_not_extreme: ✓ (5 pts) - RSI 31

Base Score: 50
Weekly HTF Bonus: +20 (near weekly support)
Total: 70 points
```

**A+ Threshold:** 80 points
**Result:** ❌ Below threshold (70 < 80)

**With Discord Signal:**
```
Base + HTF: 70
Discord Bonus: +15
FINAL SCORE: 85 ✅
```

---

### STEP 5: Trade Decision

**✅ QUALIFIED - Trade Approved**

**Agent Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ANALYZING QQQ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Market State: $543.80 near support zone
  Setup: oversold_reversal
  Bias: Bearish (counter-trend opportunity)

  A+ SCORE: 85  (base: 50 + weekly: +20 + discord: +15)
  Threshold: 80  |  HTF cap: 45

  📱 Discord signal active: MIXED_BEARISH (medium conf.) -
     Short-term bounce expected, QQQ -10% at 300MA [28m ago]

  Criteria:
    ✓ liquidity_sweep: 15pts
    ✗ market_structure_shift: 0pts
    ✗ fvg_present: 0pts
    ✗ displacement: 0pts
    ✓ killzone_timing: 10pts
    ✓ premium_discount: 10pts
    ✓ ema_confirmation: 5pts
    ✓ vwap_confluence: 5pts
    ✓ rsi_not_extreme: 5pts
    ✓ weekly_liquidity: +20pts — Near PWL $540
    ✓ discord_signal: +15pts — At support level $540.00 |
                      Oversold at 300MA | Short-term bounce expected

  ⚠ Risk Warning: Discord mentions oil >$100 recession risk

  ✅ TRADE SIGNAL

  🎯 BUY QQQ @ $543.80
     Stop: $539.50 (below support cluster)
     Target: $552.80 (2:1 R:R)
     Size: 18 shares (5% of equity)

  📊 Risk: $77.40 | Reward: $162.00 | R:R: 2.09:1
```

---

### STEP 6: Trade Execution & Tracking

#### 6.1 Place Order
```python
buy(symbol="QQQ",
    qty=18,
    order_type="limit",
    limit_price=543.80,
    stop_loss=539.50,
    take_profit=552.80)
```

#### 6.2 Log Signal Usage

**Database: `signal_performance` table**

```sql
INSERT INTO signal_performance (
    signal_id: 42,  -- Our extracted signal
    trade_id: '2026-03-26_103200_QQQ_buy',
    symbol: 'QQQ',

    signal_sentiment: 'mixed_bearish',
    signal_confidence: 'medium',
    score_bonus: 15,

    trade_direction: 'buy',
    entry_price: 543.80,

    signal_age_minutes: 28,
    trade_opened_at: '2026-03-26 10:32:00'
)
```

**Update signal record:**
```sql
UPDATE discord_signals
SET applied_to_trades = array_append(applied_to_trades, '2026-03-26_103200_QQQ_buy'),
    score_impact = jsonb_set(score_impact, '{2026-03-26_103200_QQQ_buy}', '15')
WHERE id = 42;
```

---

### STEP 7: Trade Outcome & Performance Tracking

**Scenario A: Trade Wins (Target Hit at $552.80)**

```sql
UPDATE signal_performance
SET
    exit_price = 552.80,
    pnl = 162.00,
    result = 'win',
    signal_accuracy = 'correct',  -- Signal predicted bounce
    distance_to_target = 0,  -- Hit exact target
    trade_closed_at = '2026-03-26 11:45:00'
WHERE trade_id = '2026-03-26_103200_QQQ_buy';

-- Update author credibility
UPDATE signal_author_stats
SET
    signals_used = signals_used + 1,
    correct_calls = correct_calls + 1,
    accuracy_rate = correct_calls::float / NULLIF(correct_calls + incorrect_calls, 0),
    total_pnl_impact = total_pnl_impact + 162.00,
    avg_score_bonus = (avg_score_bonus * (signals_used - 1) + 15) / signals_used
WHERE author_name = 'TradingGuru';
```

**Scenario B: Trade Loses (Stop Hit at $539.50)**

```sql
UPDATE signal_performance
SET
    exit_price = 539.50,
    pnl = -77.40,
    result = 'loss',
    signal_accuracy = 'incorrect',  -- Bounce didn't materialize
    distance_to_target = 9.30,  -- $9.30 away from target
    trade_closed_at = '2026-03-26 10:58:00'
WHERE trade_id = '2026-03-26_103200_QQQ_buy';

-- Update author credibility
UPDATE signal_author_stats
SET
    signals_used = signals_used + 1,
    incorrect_calls = incorrect_calls + 1,
    accuracy_rate = correct_calls::float / NULLIF(correct_calls + incorrect_calls, 0),
    total_pnl_impact = total_pnl_impact - 77.40
WHERE author_name = 'TradingGuru';
```

---

### STEP 8: Learning & Adaptation

**Query Performance Data:**

```sql
-- Check signal effectiveness
SELECT * FROM signal_effectiveness
WHERE channel_name = 'day-trade-alerts'
  AND sentiment = 'mixed_bearish'
  AND confidence = 'medium';

-- Result:
-- win_rate: 62% (15 wins, 9 losses)
-- avg_bonus: 12.5 points
-- avg_pnl: +$84.50

DECISION: Keep using these signals with 15-point bonus cap
```

**Adjust Future Scoring:**

```python
# In discord_integration.py, adjust weights based on performance

if author_stats.accuracy_rate > 0.70:
    confidence_multiplier = 1.2  # High accuracy = more bonus
elif author_stats.accuracy_rate < 0.45:
    confidence_multiplier = 0.5  # Low accuracy = less weight

bonus *= confidence_multiplier
```

---

## Summary: Why This Trade Happened

**Without Discord Signal:** ❌ Score 70 → Below threshold (80)
**With Discord Signal:** ✅ Score 85 → A+ Qualified

**Discord Added Value:**
1. **+5 pts** - Confirmed short-term bullish bias (bounce expected)
2. **+8 pts** - Price at key support level ($540)
3. **+2 pts** - Technical confirmation (oversold at 300MA)
4. **Risk context** - Flagged macro oil/recession risk for position sizing

**Outcome Scenarios:**
- If **win** → Signal author credibility ↑, future signals weighted higher
- If **loss** → Signal author credibility ↓, future signals weighted lower
- After 20+ signals → Statistical confidence in author's accuracy

---

## Database Query Examples

**Get active signals for current trading:**
```sql
SELECT * FROM active_discord_signals
WHERE 'QQQ' = ANY(symbols) OR 'SPY' = ANY(symbols);
```

**Check author track record before using signal:**
```sql
SELECT author_name, accuracy_rate, total_signals, avg_score_bonus
FROM signal_author_stats
WHERE author_name = 'TradingGuru';
```

**Analyze which channels provide best signals:**
```sql
SELECT
    channel_name,
    COUNT(*) as signals,
    AVG(win_rate) as avg_win_rate,
    SUM(avg_pnl) as total_pnl_impact
FROM signal_effectiveness
GROUP BY channel_name
ORDER BY avg_win_rate DESC;
```

**Find historically accurate signals for current setup:**
```sql
SELECT
    s.sentiment,
    s.confidence,
    AVG(CASE WHEN sp.result = 'win' THEN 1.0 ELSE 0.0 END) as win_rate
FROM discord_signals s
JOIN signal_performance sp ON s.id = sp.signal_id
WHERE s.symbols && ARRAY['QQQ']
  AND s.signal_type = 'market_analysis'
GROUP BY s.sentiment, s.confidence
HAVING COUNT(*) >= 10;
```

This creates a **data-driven, feedback loop system** where Discord signals improve over time based on actual trading outcomes.
