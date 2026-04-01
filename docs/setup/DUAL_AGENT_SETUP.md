# 🤖 Dual Agent Setup - Stocks + Futures

You now have **two independent trading agents** with the same strategy but different execution:

## 📊 Agent Overview

| Agent | Broker | Instruments | Purpose |
|-------|--------|-------------|---------|
| **agent.py** | Alpaca | SPY/QQQ stocks | Proven, stable stock trading |
| **futures_agent.py** | IBKR | MES/MNQ futures | Leverage, better taxes, 23h trading |

**Both agents have identical analysis:**
- ✅ Multi-timeframe analysis (Monthly → Weekly → Daily → 15Min → 5Min → 1Min)
- ✅ A+ scoring system (80+ threshold)
- ✅ Video insights validation (+0-15 pts)
- ✅ FOMC timing awareness
- ✅ Discord signal confirmation
- ✅ HTF liquidity bonuses
- ✅ Smart regime scoring
- ✅ Same setup detection & validation

**Only difference:** Where trades execute (Alpaca vs IBKR)

---

## 🚀 Usage

### Stock Agent (Alpaca)

```bash
# Single scan (dry-run)
python3 agent.py --dry-run

# Live trading (loop mode)
python3 agent.py --loop

# Custom interval
python3 agent.py --loop --interval 5
```

**Requirements:**
- Alpaca API keys in `.env`
- No other software needed

**Trades:**
- SPY/QQQ stocks
- Bracket orders on Alpaca
- Logged to `journal/trades.jsonl`

---

### Futures Agent (IBKR)

```bash
# Single scan (dry-run)
python3 futures_agent.py --dry-run

# Live trading (loop mode)
python3 futures_agent.py --loop

# Custom interval
python3 futures_agent.py --loop --interval 5
```

**Requirements:**
- Alpaca API keys (for SPY/QQQ market data)
- TWS running and connected (port 7497 for paper)
- IBKR paper/live account

**Trades:**
- MES/MNQ futures
- Bracket orders on IBKR
- Logged to `journal/futures_signals.jsonl`

---

## 🔄 Running Both Simultaneously

You can run both agents at the same time for diversification:

### Terminal 1 (Stock Agent):
```bash
python3 agent.py --loop
```

### Terminal 2 (Futures Agent):
```bash
# Make sure TWS is running first!
python3 futures_agent.py --loop
```

**Benefits:**
- ✅ Diversified execution (stocks + futures)
- ✅ Different risk profiles
- ✅ Test futures while stocks keep trading
- ✅ Both learn from same signals

**Considerations:**
- Both agents scan same symbols (SPY/QQQ)
- Both detect same setups
- You'll get 2x signals (one stock, one futures)
- Manage total exposure across both

---

## 📁 File Structure

```
agent.py                    # Stock trading agent (Alpaca)
futures_agent.py            # Futures trading agent (IBKR)
alpaca_trader.py            # Alpaca API functions
ibkr_executor.py            # IBKR API functions
futures_translator.py       # SPY → MES, QQQ → MNQ translation
analyze.py                  # Multi-timeframe analysis (shared)
indicator_engine.py         # HTF liquidity detection (shared)
memories.py                 # Scoring criteria (shared)
video_insights_loader.py    # Video validation (shared)
fomc_timing.py              # FOMC detection (shared)
weekly_context.py           # Regime analysis (shared)

journal/
├── trades.jsonl            # Stock trades (agent.py)
├── futures_signals.jsonl   # Futures trades (futures_agent.py)
├── decisions.jsonl         # All decisions (both agents)
└── cycle_stats.jsonl       # Performance (both agents)
```

---

## 🎯 Recommended Approach

### Phase 1: Paper Trading (Week 1-4)
```bash
# Run both in parallel
Terminal 1: python3 agent.py --loop --dry-run
Terminal 2: python3 futures_agent.py --loop --dry-run

# Compare results:
# - Same signals detected?
# - Same scoring?
# - Both execute correctly?
```

### Phase 2: Live Stocks, Paper Futures (Week 5-8)
```bash
# Stocks go live, futures stay paper
Terminal 1: python3 agent.py --loop              # LIVE on Alpaca
Terminal 2: python3 futures_agent.py --loop      # PAPER on IBKR

# Validate futures performance before going live
```

### Phase 3: Both Live (Week 9+)
```bash
# Both agents live when ready
Terminal 1: python3 agent.py --loop              # LIVE on Alpaca
Terminal 2: python3 futures_agent.py --loop      # LIVE on IBKR (paper_trading=False)

# Full diversification!
```

---

## ⚙️ Configuration

### Stock Agent (`agent.py`)
- No configuration needed
- Uses Alpaca credentials from `.env`
- All settings in `memories.py`

### Futures Agent (`futures_agent.py`)
- Requires TWS running
- Uses IBKR credentials from `.env`
- To switch to live trading: Edit line 1501
  ```python
  IBKR_EXECUTOR = IBKRExecutor(paper_trading=False)  # Change True → False
  ```

---

## 📊 Monitoring

### Stock Agent
```bash
# Watch agent logs
tail -f journal/agent_cron.log

# Check trades
tail journal/trades.jsonl

# Alpaca dashboard
https://app.alpaca.markets/paper/dashboard
```

### Futures Agent
```bash
# Watch futures signals
tail -f journal/futures_signals.jsonl

# Check TWS
Open TWS → Orders panel (see active orders)
Open TWS → Portfolio panel (see positions/P&L)

# Test IBKR connection
python3 ibkr_executor.py test
```

---

## 🐛 Troubleshooting

### Stock Agent Not Trading
```bash
# Check Alpaca credentials
grep ALPACA_ .env

# Check account
python3 -c "from alpaca_trader import get_account; print(get_account())"
```

### Futures Agent Not Trading
```bash
# Check TWS is running
ps aux | grep -i tws

# Check IBKR connection
python3 ibkr_executor.py test

# Check API enabled
# TWS → File → Global Configuration → API → Enable ActiveX
```

### Both Agents Trading Same Signal
```bash
# This is normal! Same analysis = same signals
# You can:
# 1. Accept it (diversified execution)
# 2. Run only one agent
# 3. Modify one agent to skip certain setups
```

---

## ✅ Summary

**You have:**
- ✅ Two independent agents with identical strategy
- ✅ Stock agent: Proven, stable, working on Alpaca
- ✅ Futures agent: New, testing, on IBKR
- ✅ Can run both simultaneously
- ✅ Full analysis power in both
- ✅ Different execution layers

**Next steps:**
1. Test futures_agent.py in dry-run mode
2. Validate futures signals match stock signals
3. Run both in parallel for 2-4 weeks
4. Go live with futures when validated

**Commands to start:**
```bash
# Stocks (already working):
python3 agent.py --loop

# Futures (new):
python3 futures_agent.py --loop
```

🚀 **You're ready to trade both stocks and futures with the same proven strategy!**
