# How to Execute Discord Opportunities with Agent

## Current Agent Schedule

### **Agent Does NOT Run Every 2 Minutes**

Your agent runs at **specific killzone times**:

```
Asia Killzone:    20:00 ET (5:00 PM PT)
London Killzone:  02:00 ET (11:00 PM PT prev day)
NY AM Killzone:   09:30 ET (6:30 AM PT)
NY Lunch:         12:00 ET (9:00 AM PT)
NY PM Killzone:   13:30 ET (10:30 AM PT)
```

**What runs every 2 minutes:**
- `discord_monitor.py` - Captures Discord notifications (continuous loop)
- `discord_signal_extractor.py` - Processes signals (LaunchAgent every 2 min)

**Agent execution:** Only during killzones for SPY/QQQ day trading

---

## Daily Opportunities Report ✅ INSTALLED

**Schedule:** Every weekday at 6 AM PT (9 AM ET)

**Output:** `~/Desktop/trading_opportunities.txt`

**What it contains:**
- Long-term value plays (AMZN, IGV, etc.)
- Conditional setups (QQQ at 200MA, etc.)
- Active positions to monitor

---

## How to Execute Opportunities

### **Method 1: Manual Execution** ⭐ RECOMMENDED

**Best for:** Swing trades, long-term positions, options

**Workflow:**
```bash
# 1. Read report each morning
cat ~/Desktop/trading_opportunities.txt

# 2. See opportunity you like
# Example: "AMZN at golden pocket, 21 forward PE"

# 3. Open your broker manually
# - Alpaca website
# - Or trading app

# 4. Execute the trade
# - Symbol: AMZN
# - Quantity: Based on position size
# - Order type: Limit or market

# 5. Log it (optional)
echo "$(date): Bought 50 AMZN @ \$198 - Golden pocket setup" >> journal/manual_trades.log
```

**Pros:**
- ✅ Full control over execution
- ✅ No code changes
- ✅ Zero risk to existing agent
- ✅ Can check current price before entering

**Cons:**
- ❌ Manual work required
- ❌ Might miss opportunities if not monitoring

---

### **Method 2: Add to Agent's Signal File**

**Best for:** Day trade signals you want agent to execute automatically

**Workflow:**
```bash
# 1. Find a good short-term setup in opportunities
# Example: "SPY at support $610"

# 2. Manually add to agent's signal file
cat >> journal/discord_signals.json << 'EOF'
{
  "timestamp": "2026-03-30T09:00:00-04:00",
  "symbols": ["SPY"],
  "sentiment": "bullish",
  "confidence": "high",
  "price_targets": {
    "SPY": {
      "support": [610.0],
      "resistance": [615.0]
    }
  },
  "expires_at": "2026-03-30T13:00:00-04:00"
}
EOF

# 3. Agent will pick it up on next killzone check
# 4. If score >= 80, agent executes automatically
```

**Pros:**
- ✅ Agent executes automatically
- ✅ Uses existing scoring system
- ✅ No code changes

**Cons:**
- ❌ Only works for day trades (4-hour expiry)
- ❌ Must manually format JSON
- ❌ Agent only checks during killzones

---

### **Method 3: Create Swing Trade Executor** 🚧 FUTURE

**Best for:** Automated swing/long-term execution

**Implementation:** (Not built yet, requires Phase 3)

```python
# NEW FILE: execute_swing_trade.py

import json
from alpaca_trader import place_market_order

def execute_opportunity(ticker, strategy, price, reason):
    """Execute a swing/long-term opportunity."""

    # Calculate position size (e.g., 2% of portfolio)
    position_size = calculate_swing_position_size(ticker)

    # Place order
    result = place_market_order(
        symbol=ticker,
        qty=position_size,
        side='buy',
        time_in_force='day'
    )

    # Log
    log_swing_trade(ticker, position_size, price, reason, result)

    return result

# Usage:
# python3 execute_swing_trade.py AMZN "Golden pocket, 21 PE"
```

**To build this:**
1. Create swing trade executor script
2. Add position tracking
3. Add to cron or manual trigger
4. Integrate with opportunities report

**Pros:**
- ✅ Automated execution
- ✅ Proper position sizing
- ✅ Trade logging

**Cons:**
- ❌ Requires building (Phase 3)
- ❌ Needs testing
- ❌ More complex

---

## Recommended Approach by Strategy

| Strategy | Method | Execution | Why |
|----------|--------|-----------|-----|
| **Day Trades** | Agent (existing) | Automatic | Already built, score >= 80 |
| **Swing Setups** | Manual (Method 1) | Manual broker | Conditional, need price check |
| **Long-Term Ideas** | Manual (Method 1) | Manual broker | Value plays, not time-sensitive |
| **Options** | Manual (Method 1) | Manual broker | Complex, need approval |

---

## Current Opportunities (Right Now)

### **Execute These Manually:**

**Long-Term (Hold months):**
```
AMZN @ $198
- Setup: Golden pocket, cheapest valuation ever (21 PE)
- Action: Buy 50-100 shares
- Target: $250+ (when PE normalizes to 28)
- Stop: -20% ($158)
```

**Conditional (Monitor daily):**
```
QQQ if reaches $538 (200MA)
- Setup: DCA at 200MA per Discord analyst
- Action: Buy 20-50 shares when within 2% of $538
- Target: $560+ (short-term bounce)
- Stop: Below 200MA
```

**Not Recommended Now:**
```
HOOD @ $66-68
- Analyst says: "NOT adding yet, want lower PE"
- Action: SKIP for now
```

---

## Integration with Agent (Future Phases)

### **Phase 2: Shared Signal Processing** (Week 2-3)

Modify `discord_signal_extractor.py`:

```python
def process_notification(notif):
    # Extract signal
    signal = extract_signal(notif)

    # Categorize
    categories = categorize_message(notif['raw_text'])

    # Route by category
    if 'day_trade' in categories:
        save_to_discord_signals_json(signal)  # Agent picks up

    if 'swing_setup' in categories:
        save_to_swing_opportunities(signal)   # Manual review

    if 'long_term' in categories:
        save_to_long_term_ideas(signal)       # Manual review
```

### **Phase 3: Multi-Strategy Agent** (Month 2)

Add to `agent.py`:

```python
def check_opportunities():
    """Check all trading opportunities."""

    # Priority 1: Day trades (existing)
    day_signal = check_discord_signals()
    if day_signal and day_signal['score'] >= 80:
        return execute_day_trade(day_signal)

    # Priority 2: Swing setups (NEW)
    swing_opps = load_swing_opportunities()
    for opp in swing_opps:
        if conditions_met(opp) and has_capital('swing'):
            return execute_swing_trade(opp)

    # Priority 3: Long-term (still manual)
    return None
```

---

## Quick Start Guide

### **This Week (Manual Execution):**

```bash
# 1. Every morning, read report
cat ~/Desktop/trading_opportunities.txt

# 2. If you see good opportunity:
#    - AMZN at golden pocket
#    - QQQ at 200MA
#    - IGV at support

# 3. Open Alpaca/broker
# 4. Execute manually
# 5. Track in spreadsheet

# 6. After 2 weeks: Review
#    - Did opportunities work?
#    - Worth continuing?
#    - Ready for automation?
```

### **Next Month (If Manual Works):**

```bash
# 1. Build swing trade executor
# 2. Test with small positions
# 3. Add to agent workflow
# 4. Gradually automate
```

---

## Summary

**✅ Installed:** Daily opportunities report (6 AM PT)

**Current setup:**
- Agent: Runs at killzones for SPY/QQQ day trades
- Report: Daily at 9 AM ET with swing/long-term ideas
- Execution: Manual via broker

**To execute opportunities:**
1. **Best way:** Read report, execute manually in broker
2. **Advanced:** Add to `discord_signals.json` for agent
3. **Future:** Build automated swing executor (Phase 3)

**Recommendation:** Start with manual execution for 2 weeks, then decide if you want to automate.

---

## Files to Check

```bash
# Daily opportunities report
~/Desktop/trading_opportunities.txt

# Agent's day trade signals (automatic)
journal/discord_signals.json

# Categorized opportunities (detailed)
trade_categories/long_term_ideas.jsonl
trade_categories/conditional_setups.jsonl
trade_categories/active_trades.jsonl

# Manual trade log (you create this)
journal/manual_trades.log
```

---

**Status:** ✅ Ready to use
**Next action:** Check `~/Desktop/trading_opportunities.txt` tomorrow morning at 9 AM ET
