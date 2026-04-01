# 📱 Discord Trade Integration - Quick Start

## 🎯 What It Does

Futures agent now monitors Discord #day-trade-alerts and:
- **Executes Discord trades** instead of chart analysis
- **Exits immediately** if setup is invalidated
- Runs **fully automated** every 2 minutes

---

## 📝 How to Post Trades

### Format:

```
[BUY/SELL] [SPY/QQQ] @ [entry], SL [stop], TP [target]
```

### Examples:

```
✅ "SELL SPY @ 635.50, SL 636.00, TP 633.00"
✅ "BUY QQQ 580.25 stop 579.50 target 582.00"
✅ "SHORT MES 6350, stop 6355, target 6340"
✅ "SELL ES 6350, stop 6355, target 6340"
✅ "BUY NQ 21000, stop 20950, target 21100"
✅ "LONG SPY $640 sl $638 tp $645"
✅ "SELL GC @ 2850, SL 2860, TP 2830"   (gold supported!)
✅ "BUY GOLD 2850 stop 2840 target 2870"
```

### Recognized Symbols:
- **SPY** or **MES** or **ES** or **S&P** or **SPX** → Micro E-mini S&P 500
- **QQQ** or **MNQ** or **NQ** or **NASDAQ** or **NDX** → Micro E-mini Nasdaq 100
- **GLD** or **MGC** or **GC** or **GOLD** → Micro Gold ✨

### ⚠️ Ignored Symbols (filtered out):
- **CL** (crude oil futures) - SKIPPED
- Other commodities - SKIPPED

**Supported: E-mini S&P, Nasdaq, and Gold futures!**

### Recognized Keywords:
- **Direction**: buy, long, sell, short, dca, add
- **Entry**: @, at, entry, price
- **Stop**: SL, stop, stop loss
- **Target**: TP, target, take profit

---

## 🚨 How to Invalidate

### Format:

```
[Symbol] invalidated
[Symbol] cancel
exit [symbol]
```

### Examples:

```
✅ "SPY setup invalidated"
✅ "Cancel SPY trade"
✅ "Exit SPY - setup broke"
✅ "QQQ no longer valid"
```

**Result**: Agent will immediately:
1. Cancel all open orders for that contract
2. Close position with market order
3. Log invalidation

---

## 🔄 Workflow

### 1. Post Trade to Discord

**9:28 AM** - You post:
```
SELL SPY @ 635.50, SL 636.00, TP 633.00 - FVG at PWH
```

### 2. Futures Agent Scans (9:30 AM)

```
📱 Syncing Discord #day-trade-alerts...
🎯 NEW TRADE: SELL SPY @ 635.5, SL 636.0, TP 633.0 (R:R 5.0)

📱 DISCORD TRADE FOUND: SELL @ 635.5
   ✓ Using Discord setup instead of chart analysis

A+ SCORE: 95 → PASS (threshold 75)

📊 FUTURES SIGNAL: SELL 33 MES
   Entry: 6355.0, Stop: 6360.0, Target: 6330.0

✅ PAPER BRACKET ORDER PLACED
   Order IDs: [12345, 12346, 12347]
```

### 3. Setup Invalidates (9:40 AM)

**You post:**
```
SPY setup invalidated - broke above stop
```

### 4. Next Agent Scan (9:42 AM)

```
⚠️  INVALIDATION detected: 1 trades affected
🚨 DISCORD INVALIDATION DETECTED: SPY (MES202606)
   🛑 EMERGENCY EXIT: Closing position
   ✓ Position closed: filled
```

---

## 🧪 Test It

### Step 1: Test Discord Sync

```bash
cd /Users/rhingar/Projects/dumpster-fire
python3 discord/discord_trade_monitor.py --test
```

**Expected**:
```
  📱 Syncing Discord #day-trade-alerts...
  ✓ Fetched 50 recent messages
  🎯 NEW TRADE: SELL SPY @ 635.5, SL 636.0, TP 633.0

  ═══════════════════════════════════════════════════════
    ACTIVE DISCORD TRADES
  ═══════════════════════════════════════════════════════
    SPY: SELL @ 635.5, SL 636.0, TP 633.0 (R:R 5.0, 5m ago)
```

### Step 2: Dry Run Futures Agent

```bash
python3 futures/futures_agent.py --dry-run
```

**Look for**:
```
  📱 DISCORD TRADE FOUND: SELL @ 635.5
  ✓ Using Discord setup instead of chart analysis
  ✓ Skipping chart analysis — using Discord setup
```

### Step 3: Live Test (Paper Trading)

```bash
# Ensure TWS is running
ps aux | grep "Trader Workstation"

# Run futures agent (paper mode)
./scripts/run_futures_agent.sh

# Watch logs
tail -f journal/futures_agent_cron.log
```

---

## 📊 Priority Logic

```
Priority 1: Valid Discord trade exists
   → Use Discord setup
   → Skip chart analysis
   → Execute if A+ score met

Priority 2: No Discord trade
   → Normal chart analysis
   → Execute if setup found and A+ score met

Priority 3: Invalidation message posted
   → Emergency exit existing position
   → Cancel all orders
   → Log reason
```

---

## ✅ Checklist

**Before posting trades:**
- [ ] Discord bot token in `.env`
- [ ] TWS running (paper mode)
- [ ] Futures agent running (cron or manual)

**When posting:**
- [ ] Use format: `[BUY/SELL] [SPY/QQQ] @ [entry], SL [stop], TP [target]`
- [ ] Entry < Target for LONG, Entry > Target for SHORT
- [ ] Stop < Entry for LONG, Stop > Entry for SHORT

**After posting:**
- [ ] Check `journal/discord_trades.json` for active trade
- [ ] Monitor `journal/futures_agent_cron.log` for execution
- [ ] Post invalidation if setup fails

---

## 🔍 View Active Trades

```bash
# View JSON cache:
cat journal/discord_trades.json

# Pretty print:
cat journal/discord_trades.json | jq '.active_trades[] | {symbol, direction, entry, stop, target}'

# View invalidation log:
tail journal/discord_invalidations.jsonl
```

---

## 🐛 Common Issues

### "Discord sync failed"

**Check**:
```bash
# Verify bot token:
echo $DISCORD_BOT_TOKEN

# Test Discord API:
python3 discord/discord_trade_monitor.py --sync
```

### "No trade parsed from message"

**Fix**: Use exact format:
```
❌ "SPY might drop to 633"           (no levels)
❌ "Short SPY here"                  (no levels)
✅ "SELL SPY @ 635.50, SL 636.00, TP 633.00"
```

### "Trade posted but not executed"

**Check**:
1. Did A+ score meet threshold? (need 75+)
2. Did pre-flight checks pass? (killzone, daily limits)
3. Is TWS running?

**Debug**:
```bash
# View last scan:
tail -100 journal/futures_agent_cron.log

# Look for:
# "A+ SCORE: XX (threshold 75)"
# "PRE-FLIGHT CHECKS:" results
```

---

## 📈 What Gets Logged

### `journal/discord_trades.json`
```json
{
  "last_updated": "2026-04-01T09:30:00-04:00",
  "active_trades": [
    {
      "message_id": "1234567890",
      "timestamp": "2026-04-01T09:28:00-04:00",
      "symbol": "SPY",
      "direction": "sell",
      "entry": 635.5,
      "stop": 636.0,
      "target": 633.0,
      "risk_reward": 5.0,
      "expires_at": "2026-04-01T13:28:00-04:00",
      "invalidated": false
    }
  ]
}
```

### `journal/discord_invalidations.jsonl`
```json
{"timestamp": "2026-04-01T09:42:00-04:00", "message_id": "1234567890", "symbol": "SPY", "direction": "sell", "entry": 635.5, "invalidation_reason": "SPY setup invalidated - broke above stop"}
```

### `journal/futures_signals.jsonl`
```json
{"timestamp": "2026-04-01T09:30:15-04:00", "symbol": "SPY", "side": "sell", "entry": 635.5, "stop": 636.0, "target": 633.0, "futures_symbol": "MES", "futures_entry": 6355.0, "contracts": 33, "source": "discord", "discord_message_id": "1234567890"}
```

---

## 🚀 Tips

1. **Be explicit**: Always include entry, stop, target
2. **Post early**: Agent syncs every 2 min, so post 1-2 min before desired entry
3. **Invalidate quickly**: If setup breaks, post invalidation immediately
4. **Check logs**: Verify execution in `journal/futures_agent_cron.log`
5. **Monitor TWS**: See orders in TWS to confirm fills

---

## 📞 Quick Commands

```bash
# Test Discord sync
python3 discord/discord_trade_monitor.py --test

# Dry run futures agent
python3 futures/futures_agent.py --dry-run

# View active trades
cat journal/discord_trades.json | jq

# Watch live logs
tail -f journal/futures_agent_cron.log

# Check if TWS running
ps aux | grep "Trader Workstation"

# Check if futures agent running
ps aux | grep "futures_agent.py --loop"
```

---

🎯 **Post trades to #day-trade-alerts → Futures agent executes automatically!**
