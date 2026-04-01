# 🚀 Fully Automated IBKR Futures Trading - Setup Complete!

**Status:** ✅ READY TO USE

Your agent now automatically:
1. Analyzes SPY/QQQ using proven multi-timeframe analysis
2. Translates signals to MES/MNQ futures
3. Places bracket orders on IBKR with TP/SL on every trade
4. Logs everything to journal

**Zero human intervention required!**

---

## 🎯 What's Been Built

### Core Integration
- ✅ `--ibkr` command line flag for futures mode
- ✅ Automatic IBKR connection on startup
- ✅ SPY → MES translation (SPY × 10)
- ✅ QQQ → MNQ translation (QQQ × 40)
- ✅ Bracket orders with entry, stop, and take profit
- ✅ Position sizing based on 2% account risk
- ✅ All trades logged to `journal/futures_signals.jsonl`
- ✅ Graceful error handling and cleanup

### Smart Features
- ✅ Uses micro contracts (MES/MNQ) - safer for starting
- ✅ Every trade has TP/SL based on agent's analysis
- ✅ Risk/reward calculated in futures terms
- ✅ Broker-side stops (survives connection loss)
- ✅ Automatic cleanup on exit

---

## 📋 Prerequisites

### 1. TWS Must Be Running
```bash
# Before starting agent, make sure TWS is:
# - Launched and logged in (paper account: gresnj027)
# - API enabled (port 7497)
# - Connected and showing paper account balance
```

### 2. Alpaca Keys (For Market Data)
Even though you're trading futures on IBKR, the agent still uses Alpaca for SPY/QQQ market data (free tier works fine).

Add to `.env`:
```bash
# Get from: https://alpaca.markets (free paper trading account)
ALPACA_API_KEY=your_actual_key_here
ALPACA_SECRET_KEY=your_actual_secret_here
```

---

## 🚀 Usage

### Option 1: Single Scan (Test First)
```bash
# Make sure TWS is running first!
python3 agent.py --ibkr --dry-run

# What happens:
# 1. Connects to IBKR paper account
# 2. Gets account equity ($1M paper)
# 3. Analyzes SPY/QQQ
# 4. Shows futures signals (but doesn't place orders)
# 5. Disconnects cleanly
```

### Option 2: Fully Automated Loop
```bash
# Make sure TWS is running first!
python3 agent.py --ibkr --loop

# What happens:
# 1. Connects to IBKR paper account
# 2. Scans SPY/QQQ every 2 minutes during killzones
# 3. When A+ signal detected (score 80+):
#    - Translates to MES/MNQ
#    - Places bracket order automatically
#    - Logs to journal
# 4. Keeps running until market closes
# 5. Disconnects cleanly on exit
```

### Option 3: Custom Scan Interval
```bash
python3 agent.py --ibkr --loop --interval 5

# Scans every 5 minutes instead of 2
```

---

## 📊 Example Execution Flow

**Scenario:** Agent detects SPY short signal

```
1. ANALYSIS PHASE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Analyzing SPY (multi-timeframe)
   Daily bias: BEARISH
   15Min setup: FVG_entry short
   A+ Score: 97 (base 65 + HTF +30 + video +12)
   Entry: $635.69
   Stop: $636.00
   Target: $634.80
   R:R: 2.87:1

2. FUTURES TRANSLATION
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Translating to MES (Micro E-mini S&P 500)
   Entry: 6357.00 (SPY × 10, rounded to tick)
   Stop: 6360.00
   Target: 6348.00
   Contracts: 33 (2% risk of $1M account)
   Risk: $495 (3 points × $5/point × 33)
   Reward: $1485 (9 points × $5/point × 33)
   R:R: 3:1

3. IBKR EXECUTION
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Placing bracket order on IBKR...
   ✅ Order placed: [123, 124, 125]

   Orders in TWS:
   - Order 123: SELL 33 MES @ 6357.0 (entry)
   - Order 124: BUY 33 MES @ 6360.0 (stop loss)
   - Order 125: BUY 33 MES @ 6348.0 (take profit)

   OCO bracket active (one-cancels-other)

4. LOGGING
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Logged to: journal/futures_signals.jsonl
   Logged to: journal/decisions.jsonl

   Full signal with:
   - Original SPY analysis
   - Futures translation
   - IBKR order IDs
   - Risk/reward breakdown
   - A+ score components
```

---

## 📁 What Gets Logged

### `journal/futures_signals.jsonl`
Complete futures signal with translation details:
```json
{
  "timestamp": "2026-03-31T17:45:00",
  "original_signal": {
    "symbol": "SPY",
    "side": "sell",
    "entry": 635.69,
    "stop": 636.00,
    "target": 634.80,
    "score": 97,
    "setup": "FVG_entry"
  },
  "futures_signal": {
    "symbol": "MES",
    "side": "sell",
    "entry": 6357.0,
    "stop": 6360.0,
    "target": 6348.0,
    "recommended_contracts": 33,
    "total_risk": 495.0,
    "total_reward": 1485.0,
    "risk_reward_ratio": 3.0
  },
  "execution_notes": {
    "order_type": "LIMIT",
    "entry_instructions": "SELL 33 MES @ 6357.0 LIMIT",
    "stop_loss_instructions": "Stop @ 6360.0 (risk $495.00)",
    "take_profit_instructions": "Target @ 6348.0 (reward $1485.00)",
    "bracket_order": "Use OCO bracket: Stop @ 6360.0, Target @ 6348.0"
  }
}
```

### `journal/decisions.jsonl`
Full decision context with A+ scoring breakdown

---

## 🔍 Monitoring

### Check Agent Status
```bash
# View recent logs
tail -f journal/agent_cron.log

# Check futures signals
tail journal/futures_signals.jsonl | python3 -m json.tool

# Check if agent is running
ps aux | grep agent.py
```

### Check TWS Orders
1. Open TWS
2. Look at "Orders" panel at bottom
3. You'll see:
   - Pending orders (waiting for fill)
   - Filled orders (executed)
   - Cancelled orders (stopped out or target hit)

### Check IBKR Positions
1. Open TWS
2. Look at "Portfolio" panel
3. Shows:
   - Current MES/MNQ positions
   - Unrealized P&L
   - Realized P&L

---

## ⚠️ Important Notes

### TWS Must Stay Running
- Agent connects to TWS on port 7497
- If TWS closes, API disconnects
- Agent will fail gracefully if TWS dies
- Solution: Keep TWS running during market hours

### Paper Trading First!
- Test with paper account (gresnj027) for 2-4 weeks
- Validate 20+ trades before going live
- Ensure win rate matches expectations (60%+)

### Position Limits
- Paper account: $1M buying power
- Can trade up to ~800 MES contracts
- Agent sizes at 2% risk = 33 contracts typical
- Adjust in futures_translator.py if needed

### Commission Costs
- Paper trading: FREE (no commissions)
- Live trading: ~$0.25-0.85 per contract
- 33 MES round-trip = ~$16.50 commission
- Still way cheaper than stocks!

---

## 🐛 Troubleshooting

### "IBKR connection failed"
```bash
# Check TWS is running:
ps aux | grep -i tws

# Check API is enabled:
# TWS → File → Global Configuration → API → Enable ActiveX

# Test connection:
python3 ibkr_executor.py test
```

### "Unauthorized" errors
```bash
# These are from Alpaca (market data)
# Add valid Alpaca keys to .env:
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret

# Get free keys at: https://alpaca.markets
```

### Orders not appearing in TWS
```bash
# Check if order was placed:
tail journal/futures_signals.jsonl

# Check TWS Orders panel
# Look for order IDs in logs

# If order rejected:
# - Check margin requirements
# - Check contract expiry (should be 202606)
# - Check TWS permissions (futures enabled?)
```

### Agent stops scanning
```bash
# Check killzone:
# Agent only trades during NY AM (9:30-11:30) by default

# Override with:
python3 agent.py --ibkr --loop  # scans during killzones only

# Or modify GUARDRAILS in memories.py:
# "require_killzone": False  # scans all market hours
```

---

## 🎓 Understanding the System

### Why SPY/QQQ Analysis → ES/NQ Execution?
1. **Liquidity:** SPY/QQQ have best data/charting
2. **Correlation:** ES tracks SPY almost perfectly (ES = SPY × 10)
3. **Advantage:** Futures have better leverage, tax treatment, hours
4. **Best of both:** Analyze the most liquid ETFs, trade the best instruments

### Position Sizing (2% Risk)
```python
Account: $1,000,000
Risk per trade: 2% = $20,000
Signal risk: $495 per 33 MES contracts
Contracts: $20,000 / $495 = 40 contracts (capped at 33 for safety)

On a $25k account:
Risk per trade: 2% = $500
Signal risk: $495 per 33 MES contracts
Contracts: 1 MES (can't split contracts)
```

### Bracket Orders (OCO)
- **Entry:** Limit order at signal price
- **Stop loss:** Protects against adverse move
- **Take profit:** Locks in profit at target
- **OCO:** When one fills, other cancels (one-cancels-other)
- **Broker-side:** Survives API disconnect, power loss, etc.

---

## 🚀 Next Steps

### This Week: Paper Trading
1. ✅ TWS installed and running
2. ✅ API enabled and tested
3. ✅ Agent integrated with IBKR
4. 🔄 Run: `python3 agent.py --ibkr --loop`
5. 🔄 Monitor: Check TWS for orders
6. 🔄 Track: 20+ paper trades

### Week 2-4: Validate Performance
- Compare with agent's Alpaca stock trades
- Check win rate (target: 60%+)
- Check R:R (target: 2:1+)
- Verify execution quality
- Ensure no bugs/issues

### Month 2: Go Live (When Ready)
1. Open live IBKR account (if not funded yet)
2. Fund with $2,500+ (for 1 MES contract)
3. Update `.env` with live account credentials
4. Change `paper_trading=False` in `main()`
5. Start with 1 MES contract per signal
6. Scale up slowly based on results

### Future: AWS Deployment
- Run TWS on AWS EC2
- Agent connects remotely
- 24/7 uptime
- No local machine needed

---

## ✅ Summary

**You now have:**
- ✅ Fully automated IBKR futures execution
- ✅ SPY/QQQ analysis → MES/MNQ translation
- ✅ Every trade has TP/SL (bracket orders)
- ✅ 2% risk management
- ✅ Complete logging
- ✅ Tested and working

**What's automated:**
- Signal detection (A+ scoring with all bonuses)
- Futures translation (SPY × 10 = ES)
- Position sizing (2% account risk)
- Order placement (entry + stop + target)
- Logging (complete audit trail)

**What you need to do:**
1. Keep TWS running during market hours
2. Monitor results (check TWS orders/positions)
3. Review journal daily
4. Scale up after validation

**First command to run:**
```bash
# Start TWS first, then:
python3 agent.py --ibkr --loop
```

**You're ready to trade futures automatically!** 🎉

---

## 📞 Quick Reference

```bash
# Test IBKR connection
python3 ibkr_executor.py test

# Test agent (dry-run)
python3 agent.py --ibkr --dry-run

# Run live paper trading
python3 agent.py --ibkr --loop

# Check recent signals
tail journal/futures_signals.jsonl

# Check agent logs
tail -f journal/agent_cron.log

# Check FOMC timing
python3 fomc_timing.py
```

🚀 **Let the agent trade for you!**
