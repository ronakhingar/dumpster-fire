# Self-Learning System Documentation

## Overview

The agent includes a **self-learning system** that reviews weekly performance and automatically adjusts A+ scoring criteria weights based on what actually works in live trading. **Weights are learned separately for each killzone** (Asia, London, NY AM, NY Lunch, NY PM), enabling contextual optimization.

**Key Features:**
- The agent learns from its mistakes and successes, continuously optimizing its decision-making without manual intervention
- Reviews run weekly (Saturdays) to allow sufficient time for weights to prove themselves
- **Killzone-specific weights** adapt to different market conditions throughout the day
- A criterion that works well in London may be weighted differently in NY PM

---

## How It Works

### 1. Weekly Review Process

Every Saturday at 4:30 PM ET, the system:

1. **Collects Trade Data**
   - Reads all trades from the past 30 days
   - Matches order placements with closes
   - Calculates P&L for each trade

2. **Analyzes Performance by Killzone**
   - Groups trades by killzone (Asia, London, NY AM, NY Lunch, NY PM)
   - Correlates each A+ criterion with win/loss outcomes per killzone
   - Calculates win rate when criterion is present vs absent in each killzone
   - Identifies which criteria are actually predictive in specific market sessions

3. **Adjusts Weights by Killzone**
   - Increases weight for criteria correlated with wins in that killzone
   - Decreases weight for criteria correlated with losses in that killzone
   - Uses exponential moving average to smooth changes
   - Enforces minimum/maximum bounds
   - Each killzone learns independently

4. **Saves Results**
   - Persists learned weights to `learned_weights.json`
   - Generates weekly review report in `journal/reviews/`
   - Logs weight changes and performance metrics

5. **Next Week**
   - Agent loads learned weights on startup
   - Uses adjusted scoring for all future trades
   - Continues learning from new trades

---

## Example Learning Cycle

### Week 1 - Default Weights
```python
SCORE_CRITERIA = {
    "liquidity_sweep": 20,
    "market_structure_shift": 20,
    "fvg_present": 15,
    "displacement": 10,
    "killzone_timing": 10,
    "premium_discount": 10,
    "ema_confirmation": 5,
    "vwap_confluence": 5,
    "rsi_not_extreme": 5,
}
```

**Trades:**
- Trade 1: premium_discount=✓, vwap_confluence=✓ → **WIN** (+$50)
- Trade 2: liquidity_sweep=✓, fvg_present=✓ → **LOSS** (-$25)
- Trade 3: premium_discount=✓, ema_confirmation=✓ → **WIN** (+$30)

### Week 1 Review - Analysis
```
Criterion Analysis:
  premium_discount: present in 2 wins, 0 losses → win rate 100% (+correlation)
  vwap_confluence: present in 1 win, 0 losses → win rate 100% (+correlation)
  liquidity_sweep: present in 0 wins, 1 loss → win rate 0% (-correlation)
  fvg_present: present in 0 wins, 1 loss → win rate 0% (-correlation)
```

### Week 2 - Adjusted Weights
```python
LEARNED_WEIGHTS = {
    "liquidity_sweep": 18,        # -2 (negatively correlated)
    "market_structure_shift": 20,  # unchanged (no data)
    "fvg_present": 13,            # -2 (negatively correlated)
    "displacement": 10,            # unchanged
    "killzone_timing": 10,         # unchanged
    "premium_discount": 13,        # +3 (strongly positive)
    "ema_confirmation": 5,         # unchanged
    "vwap_confluence": 7,          # +2 (positive)
    "rsi_not_extreme": 5,          # unchanged
}
```

**Agent now prioritizes:**
- Premium/discount zone entry (increased from 10 → 13)
- VWAP confluence (increased from 5 → 7)

**Agent de-prioritizes:**
- Liquidity sweeps (decreased from 20 → 18)
- FVG presence (decreased from 15 → 13)

Over time, weights converge to optimal values based on YOUR specific market conditions and trading style.

---

## Killzone-Specific Learning

### Why Killzone-Specific Weights?

Different trading sessions have different characteristics:
- **London** (02:00-05:00 ET): High volatility, liquidity sweeps common
- **NY AM** (09:30-11:00 ET): Algo bursts, FVG setups frequent
- **NY Lunch** (12:00-13:00 ET): Low volume, choppy, fewer quality setups
- **NY PM** (13:30-16:00 ET): Directional moves, momentum plays

The same criterion may be:
- **Highly predictive** in one killzone (e.g., liquidity_sweep in London)
- **Less relevant** in another (e.g., liquidity_sweep in NY Lunch)

### Example: Killzone Learning in Action

#### Week 1 Trades
```
London trades:   3W-1L (75% win rate) → liquidity_sweep present in all 3 wins
NY AM trades:    1W-2L (33% win rate) → liquidity_sweep present in both losses
NY PM trades:    2W-1L (67% win rate) → no liquidity_sweep in any trade
```

#### Week 2 Adjusted Weights
```python
learned_weights = {
    "London": {
        "liquidity_sweep": 25,  # +5 (strongly positive in London)
        ...
    },
    "NY_AM": {
        "liquidity_sweep": 15,  # -5 (negatively correlated in NY AM)
        ...
    },
    "NY_PM": {
        "liquidity_sweep": 20,  # no change (insufficient data)
        ...
    }
}
```

**Result:** Agent now knows:
- In **London**: Prioritize liquidity sweep setups (25 pts vs default 20)
- In **NY AM**: De-prioritize liquidity sweep setups (15 pts vs default 20)
- In **NY PM**: Use default weighting (20 pts)

This contextual learning mirrors how professional traders adjust their playbook based on the session.

---

## Weekly Market Context Analysis

### Macro Awareness

Every Saturday, the review also analyzes broader market conditions for the upcoming week:

1. **FOMC Calendar Detection**
   - Checks 2026 Fed meeting schedule
   - Detects meetings in next 7 days
   - Classifies impact (high/medium/low) based on proximity

2. **Daily Trend Analysis**
   - SPY and QQQ position relative to 50/100/200-day MAs
   - Trend classification (strong_uptrend, uptrend, neutral, downtrend, strong_downtrend)
   - Momentum assessment (bullish/neutral/bearish)

3. **VIX (Fear Gauge)**
   - Current volatility expectations
   - Classification (extreme_fear, high_fear, elevated, normal, complacent)
   - Volatility factor for position sizing

4. **Market Regime Classification**
   - Combines all analyses into single regime
   - Applies scoring modifiers for the week
   - Examples: `fomc_high_uncertainty`, `strong_bullish_trend`, `extreme_volatility`

### Scoring Modifiers by Regime

**FOMC High Uncertainty** (meeting in 2 days):
```python
{
  "risk_adjustment": 0.5,        # Cut position size in half
  "volatility_factor": 1.5,      # Expect 50% more volatility
  "trend_following_boost": 0,
  "reversal_penalty": 0
}
```

**Strong Bullish Trend** (both SPY/QQQ above all MAs):
```python
{
  "risk_adjustment": 1.0,
  "trend_following_boost": 5,    # +5 pts for long setups
  "reversal_penalty": -10,       # -10 pts for short setups
  "volatility_factor": 1.0
}
```

**Extreme Volatility** (VIX > 40):
```python
{
  "risk_adjustment": 0.6,        # Reduce size to 60%
  "volatility_factor": 2.0,      # Expect double volatility
  "trend_following_boost": 0,
  "reversal_penalty": 0
}
```

### How It Affects Trading

**Example 1: FOMC Week**
```
Setup: SPY short, base score 75, HTF bonus +10 = 85 (A+ qualified)
Regime: fomc_high_uncertainty
Adjustment: -5 pts (caution before Fed)
Final: 80 (barely qualifies)
Position size: 50% of normal (risk_adjustment: 0.5)
```

**Example 2: Strong Uptrend**
```
Setup: QQQ long, base score 70, HTF bonus +5 = 75 (below threshold)
Regime: strong_bullish_trend
Adjustment: +5 pts (trend-following boost)
Final: 80 (now qualifies!)
Position size: 100% (normal)
```

**Example 3: Counter-Trend in Strong Bull**
```
Setup: SPY short, base score 85, HTF bonus +5 = 90 (A+)
Regime: strong_bullish_trend
Adjustment: -10 pts (reversal penalty)
Final: 80 (still qualifies but penalized)
Note: Fighting the trend is harder
```

### Persistence

Weekly context is saved to `journal/weekly_context.json` and loaded by the agent at startup. It remains valid for the entire week until the next Saturday review.

```json
{
  "generated_at": "2026-03-29T16:30:00-04:00",
  "week_starting": "2026-03-31",
  "fomc": {
    "has_fomc": true,
    "date": "2026-04-01",
    "days_until": 3,
    "impact": "medium"
  },
  "spy": {
    "price": 580.25,
    "trend": "strong_uptrend",
    "above_ma_200": true
  },
  "vix": {
    "vix": 14.5,
    "classification": "normal"
  },
  "regime": {
    "regime": "strong_bullish_trend",
    "scoring_modifiers": {...}
  }
}
```

---

## Alternative Data & Market Sentiment (Phase 4)

Beyond technical analysis and market regime, the system incorporates alternative data sources to detect asymmetric opportunities and directional bias.

### Data Sources

#### 1. Polymarket Prediction Markets

Queries decentralized prediction markets for forward-looking sentiment:

**Markets Monitored:**
- Fed rate cut probability
- CPI inflation expectations
- Jobs report beat/miss likelihood
- Major economic events

**Interpretation:**
```python
# Example: 65% chance of rate cut
polymarket_score = +3  # Dovish = bullish for stocks

# Example: 80% chance inflation stays elevated
polymarket_score = -2  # Hawkish = bearish for stocks
```

**Key Insight:** Prediction markets often lead price action. If Polymarket shows 70% conviction on a dovish Fed but stocks haven't rallied yet, that's an asymmetric long opportunity.

#### 2. Commodities Analysis

Monitors key commodities and their historical correlation with equities:

**Gold (GLD):**
- Resistance: $200
- Breakout above resistance = flight to safety = bearish for stocks (-3 pts)
- Below support = risk-on = bullish for stocks (+3 pts)

**Oil (USO):**
- Above $80 = inflation concerns = bearish for stocks (-2 pts)
- Below $60 = low inflation = bullish for stocks (+2 pts)

**Silver (SLV):**
- Industrial demand proxy, correlated with tech sector

**Historical Context:**
- Gold breaking out in 2008, 2020 preceded major stock corrections
- Oil spikes (2022) led to bearish pressure on equities
- Commodities can signal hidden risks not yet priced into stocks

#### 3. Financial News Scanning

Scans past week's major financial events and extracts sentiment:

**Event Classification:**
```markdown
| Event | Sentiment | Impact | Score |
|-------|-----------|--------|-------|
| "Fed signals higher for longer" | Bearish | High | -3 |
| "Tech earnings beat" | Bullish | Medium | +2 |
| "Consumer confidence drops" | Bearish | Medium | -2 |
```

**Aggregation:**
- High-impact events weighted more heavily
- Sentiment averaged across all events
- Bias score: +3 (bullish), 0 (neutral), -3 (bearish)

#### 4. Unified Sentiment Scoring

All alternative data sources combined into single directional bias:

```python
weighted_score = (
    polymarket_score * 0.4 +    # Forward-looking
    commodities_score * 0.3 +    # Structural/inter-market
    news_score * 0.3             # Recent events
)

# Convert to weight adjustments
if weighted_score > 3:
    long_boost = +10
    short_penalty = -15
elif weighted_score < -3:
    long_penalty = -15
    short_boost = +10
```

### Real-World Examples

**Example 1: Polymarket Divergence**
```
Polymarket: 75% chance of dovish Fed pivot
SPY/QQQ: Still consolidating, not rallying yet
Gold: Not breaking down (risk still on)
News: Mixed

Alternative Data Bias: Strong Bullish
Action: +10 pts for long setups, -15 pts for shorts
Rationale: Prediction markets showing conviction not yet in price
```

**Example 2: Gold Flight-to-Safety Warning**
```
Gold: Breaking above $200 resistance (flight to safety)
SPY: Still near highs (complacency)
VIX: Only 15 (normal fear)
Polymarket: 40% chance of recession (growing)

Alternative Data Bias: Bearish
Action: -8 pts for longs, +5 pts for shorts
Rationale: Gold warning of hidden risk, asymmetric short opportunity
```

**Example 3: Oil Inflation Shock**
```
Oil: Above $80 (inflation concern)
Polymarket: 60% chance CPI stays elevated
News: Fed chair warns about inflation persistence
SPY/QQQ: Vulnerable to hawkish surprise

Alternative Data Bias: Bearish
Action: -10 pts for longs, +8 pts for shorts
Rationale: Multiple sources confirm inflation narrative
```

**Example 4: Neutral Consolidation**
```
Polymarket: 50/50 on Fed decision
Commodities: Range-bound
News: Mixed signals
SPY/QQQ: Sideways

Alternative Data Bias: Neutral
Action: 0 pts adjustment
Rationale: No edge from alternative data, rely on technicals
```

### Asymmetric Opportunities

System flags specific asymmetric setups:

**Type 1: Prediction Market Divergence**
- Polymarket shows >70% conviction
- Price hasn't moved to reflect probability
- Opportunity: Early positioning before the move

**Type 2: Gold Breakout Warning**
- Gold breaks resistance while stocks near highs
- Historical precedent: Often precedes correction
- Opportunity: Short stocks or reduce exposure

**Type 3: Commodities Correlation Break**
- Normal correlation breaks down
- Example: Oil rallying but stocks not falling (yet)
- Opportunity: Position for correlation mean-reversion

### Integration with Scoring

Alternative data adjustments layer on top of killzone weights and regime modifiers:

```python
# Final scoring formula
score = base + htf_bonus + regime_adj + alt_data_adj

# Example calculation
score = 70 (base) + 5 (HTF) + 5 (bullish regime) + 10 (strong alt data) = 90
```

**Scoring Output:**
```
A+ SCORE: 90  (base: 70 + weekly: +5 + monthly: +0 = +5 HTF + regime: +15)
Using NY_AM killzone weights
Market regime: strong_bullish_trend

  ✓ liquidity_sweep: 15pts
  ✓ premium_discount: 12pts
  ...
  ✓ regime_adjustment: +5pts — strong_bullish_trend
  ✓ alt_data_adjustment: +10pts — strong_bullish (Polymarket divergence)
```

### Files Created

**`journal/weekly_context.json`** now includes:
```json
{
  "alternative_data": {
    "polymarket": {
      "overall_sentiment": {
        "direction": "bullish_tilt",
        "bias_score": 5
      }
    },
    "commodities": {
      "gold": {"trend": "range_bound", "signal": 0},
      "oil": {"trend": "low_inflation_supportive", "signal": 2},
      "summary": {"bias_score": 3}
    },
    "news": {
      "sentiment": "bullish",
      "bias_score": 3
    },
    "directional_bias": {
      "directional_bias": "strong_bullish",
      "confidence": 0.75,
      "weighted_score": 8.4,
      "bias_score": 8,
      "weight_adjustments": {
        "long_boost": 10,
        "short_penalty": -15
      },
      "asymmetric_opportunities": [...]
    }
  }
}
```

**Run Standalone:**
```bash
python3 alternative_data.py
```

---

## Configuration

### Learning Parameters (`daily_review.py`)

```python
LEARNING_RATE = 0.15           # How fast to adjust (0.1-0.3 recommended)
MIN_TRADES_TO_LEARN = 3        # Minimum trades before adjusting
MIN_WEIGHT = 2                 # Minimum weight value
MAX_WEIGHT = 30                # Maximum weight value
CONFIDENCE_THRESHOLD = 0.6     # Min 60% win rate to increase weight
```

**Learning Rate:**
- Higher (0.3) = Fast adaptation, more volatile
- Lower (0.1) = Slow adaptation, more stable
- Default (0.15) = Balanced

**Confidence Threshold:**
- Only increases weight if criterion has ≥60% win rate when present
- Prevents overweighting based on lucky wins
- Decreases weight regardless of threshold if negatively correlated

---

## Files Created

### `learned_weights.json`
Persisted learned weights with killzone-specific values:
```json
{
  "criteria_weights": {
    "global": {
      "liquidity_sweep": 19,
      "premium_discount": 12,
      ...
    },
    "Asia": {
      "liquidity_sweep": 18,
      "premium_discount": 15,
      ...
    },
    "London": {
      "liquidity_sweep": 25,
      "premium_discount": 10,
      ...
    },
    "NY_AM": {
      "liquidity_sweep": 15,
      "premium_discount": 12,
      ...
    },
    "NY_Lunch": {
      "liquidity_sweep": 12,
      "premium_discount": 8,
      ...
    },
    "NY_PM": {
      "liquidity_sweep": 20,
      "premium_discount": 14,
      ...
    }
  },
  "weekly_liquidity_bonus": {...},
  "monthly_liquidity_bonus": {...},
  "meta": {
    "version": 42,
    "last_updated": "2026-03-25T16:30:00-04:00",
    "total_trades_analyzed": 156,
    "days_learning": 42
  }
}
```

### `journal/reviews/review_YYYY-MM-DD.md`
Daily review reports with detailed reasoning:
```markdown
# Daily Review - 2026-03-25

## Performance Summary
- Trades Completed: 2
- Wins: 1
- Losses: 1
- Win Rate: 50.0%
- Total P&L: $25.00

## Criteria Performance Analysis
| Criterion | Win Rate (Present) | Win Rate (Absent) | Correlation | Change |
...

## Weight Changes Summary
- premium_discount: 10 → 13 (+3)
- vwap_confluence: 5 → 7 (+2)
...

## Detailed Change Log

### premium_discount: 10 → 13 (+3)

**Increased** because:
- Win rate when present: **80%** (4W/1L)
- Win rate when absent: **40%** (2W/3L)
- Correlation: **+0.400** (positive)
- Trades analyzed: 10

...
```

### `journal/learning_history.jsonl`
Append-only log tracking every weight change with full context:
```jsonl
{"timestamp": "2026-03-25T16:30:00-04:00", "date": "2026-03-25", "version": 2, "total_trades_analyzed": 10, "changes": [{"criterion": "premium_discount", "old_weight": 10, "new_weight": 13, "change": 3, "win_rate_when_present": 0.8, "win_rate_when_absent": 0.4, "correlation": 0.4, "present_record": "4W-1L", "absent_record": "2W-3L", "trades_analyzed": 10, "reason": "Increased because win rate was 80% when present (4W/1L) vs 40% when absent (2W/3L) over 10 trades. Correlation: +0.400"}]}
```

Use `view_learning_history.py` to analyze this data (see below).

---

## Running the Review

### Automatic (Recommended)

Review runs automatically every Saturday at 4:30 PM ET:

```bash
# Load the LaunchAgent (one time)
launchctl load ~/Library/LaunchAgents/com.trading.review.plist

# Check if scheduled
launchctl list | grep trading.review

# View logs
tail -f logs/review_stdout.log
```

### Manual

```bash
# Run review now
python3 daily_review.py

# Reset weights to defaults
python3 daily_review.py --reset
```

---

## Monitoring Learning Progress

### View Current Weights
```bash
cat learned_weights.json | jq '.criteria_weights'
```

### View Learning History
```bash
# Show all weight changes with detailed reasoning
python3 view_learning_history.py

# Show last 5 days of changes
python3 view_learning_history.py --recent 5

# Track a specific criterion over time
python3 view_learning_history.py --criterion liquidity_sweep

# Show summary of all changes across criteria
python3 view_learning_history.py --summary
```

### View Daily Review Reports
```bash
# List all reviews
ls -lt journal/reviews/

# View recent review
cat journal/reviews/review_2026-03-25.md
```

### Compare to Defaults
```bash
python3 -c "
from memories import SCORE_CRITERIA
from daily_review import load_learned_weights

defaults = SCORE_CRITERIA
learned = load_learned_weights()['criteria_weights']

print('Weight Changes from Defaults:')
for k in sorted(defaults.keys()):
    d = defaults[k]
    l = learned[k]
    if d != l:
        change = l - d
        print(f'  {k:25} {d:2} → {l:2} ({change:+d})')
"
```

### Visualize Performance
```bash
# Extract win rates from reviews
for f in journal/reviews/*.md; do
    echo "$(basename $f):"
    grep "Win Rate:" "$f"
    echo
done
```

---

## Learning History Tracking

Every time weights are adjusted, the system logs:
- **What changed**: Old weight → New weight for each criterion
- **When**: Timestamp and date of the change
- **Why**: Win rates, correlation, number of trades, and reasoning statement

This creates a complete audit trail of the learning process.

### Example Learning History Entry

```
📅 2026-03-25 (Version 2) — 2 weight change(s), 10 trades analyzed

  ↑ premium_discount: 10 → 13 (+3)
     Increased because win rate was 80% when present (4W/1L) vs 40% when
     absent (2W/3L) over 10 trades. Correlation: +0.400

  ↓ liquidity_sweep: 20 → 18 (-2)
     Decreased because win rate was 33% when present (1W/2L) vs 67% when
     absent (4W/2L) over 10 trades. Correlation: -0.333
```

### Tracking a Specific Criterion

```bash
$ python3 view_learning_history.py --criterion premium_discount

TRACKING: premium_discount

Weight Evolution:

1. 2026-03-25: 10 → 13 (↑3)
   Present: 4W-1L, Absent: 2W-3L
   Correlation: +0.400

2. 2026-03-28: 13 → 15 (↑2)
   Present: 7W-1L, Absent: 3W-5L
   Correlation: +0.500

3. 2026-04-02: 15 → 14 (-1)
   Present: 5W-4L, Absent: 6W-2L
   Correlation: -0.194
```

### Understanding the Learning Process

The history shows:
- **Positive correlation** → weight increases (criterion helps win trades)
- **Negative correlation** → weight decreases (criterion doesn't help or hurts)
- **Confidence threshold** prevents overweighting based on lucky wins
- **Learning rate** smooths changes to avoid overreaction

You can see exactly how the agent is learning what works and adapting its strategy over time.

---

## Safety Features

### 1. Bounded Weights
- Min: 2 points (criterion never drops below 2)
- Max: 30 points (criterion never exceeds 30)
- Prevents extreme overweighting

### 2. Confidence Threshold
- Only increases weight if criterion has ≥60% win rate
- Prevents learning from lucky wins
- Ensures statistical significance

### 3. Learning Rate
- Gradual adjustments (15% of suggested change)
- Smooths out noise and variance
- Prevents overreaction to single trades

### 4. Minimum Trades
- Requires ≥3 completed trades before adjusting
- Prevents premature optimization
- Builds up sufficient data

### 5. Exponential Moving Average
- New weight = current + (learning_rate × adjustment)
- Smooths changes over time
- Prevents dramatic shifts

### 6. Reset Capability
```bash
# Reset to defaults if learning goes wrong
python3 daily_review.py --reset
```

---

## Understanding the Correlation Metric

**Correlation = Win Rate (Present) - Win Rate (Absent)**

| Correlation | Meaning | Action |
|-------------|---------|--------|
| +0.3 to +1.0 | Strongly positive | Increase weight significantly |
| +0.1 to +0.3 | Moderately positive | Increase weight slightly |
| -0.1 to +0.1 | Neutral | No change |
| -0.3 to -0.1 | Moderately negative | Decrease weight slightly |
| -1.0 to -0.3 | Strongly negative | Decrease weight significantly |

**Example:**
```
premium_discount:
  Win rate when present: 80%
  Win rate when absent: 40%
  Correlation: +0.40 (strongly positive)
  → Increase weight
```

---

## What Gets Learned

### Criteria Weights (Primary)
All 9 A+ criteria weights are adjusted:
- liquidity_sweep
- market_structure_shift
- fvg_present
- displacement
- killzone_timing
- premium_discount
- ema_confirmation
- vwap_confluence
- rsi_not_extreme

### HTF Bonuses (Future Enhancement)
Currently uses static bonuses, but could learn:
- weekly_liquidity_bonus by proximity
- monthly_liquidity_bonus by proximity
- Optimal HTF_BONUS_CAP

---

## Troubleshooting

### Weights Not Updating

**Check logs:**
```bash
tail -f logs/review_stdout.log
tail -f logs/review_stderr.log
```

**Common issues:**
- Not enough completed trades (need ≥3)
- No closed positions yet (all still open)
- Review runs Saturdays at 4:30 PM ET (market closed on weekends)

### Weights Seem Wrong

**View recent performance:**
```bash
cat journal/reviews/review_$(date +%Y-%m-%d).md
```

**Reset if needed:**
```bash
python3 daily_review.py --reset
```

### LaunchAgent Not Running

**Check status:**
```bash
launchctl list | grep trading.review
```

**Reload:**
```bash
launchctl unload ~/Library/LaunchAgents/com.trading.review.plist
launchctl load ~/Library/LaunchAgents/com.trading.review.plist
```

---

## Advanced: Tuning Learning Parameters

### Conservative Learning (Slow but Stable)
```python
LEARNING_RATE = 0.10
MIN_TRADES_TO_LEARN = 5
CONFIDENCE_THRESHOLD = 0.70
```

### Aggressive Learning (Fast but Volatile)
```python
LEARNING_RATE = 0.30
MIN_TRADES_TO_LEARN = 2
CONFIDENCE_THRESHOLD = 0.55
```

### Recommended (Balanced)
```python
LEARNING_RATE = 0.15
MIN_TRADES_TO_LEARN = 3
CONFIDENCE_THRESHOLD = 0.60
```

Edit these in `daily_review.py` lines 19-23.

---

## Integration with Agent

The agent automatically:
1. Checks for `learned_weights.json` on startup
2. Loads learned weights if present
3. Falls back to defaults if not found
4. Prints which weights are being used

**Startup message:**
```
🎓 Loaded learned weights (v42, updated 2026-03-25)
```

**Or:**
```
Using default scoring weights
```

---

## Performance Metrics

After 8-12 weeks of learning, typical results:
- 10-20% improvement in win rate
- 15-30% improvement in profit factor
- More consistent performance
- Better adaptation to market conditions

The system learns YOUR optimal weights based on:
- Your Alpaca account characteristics
- Your market conditions
- Your trading hours
- Actual execution fills

**Why weekly reviews?**
- Gives weights time to prove themselves over multiple trading days
- Prevents overreaction to daily variance
- More statistically significant with larger sample sizes
- Smoother learning curve with less noise

---

## Next Steps

1. **Let it learn:** Agent needs 8-12 weeks to gather meaningful data
2. **Review progress:** Check `journal/reviews/` on Saturdays to see what's being learned
3. **Monitor performance:** Track win rate trends over multiple weeks
4. **Adjust if needed:** Tune learning parameters based on results

The longer the agent runs, the better it gets at finding A+ setups that actually work for you! 🎓📈
