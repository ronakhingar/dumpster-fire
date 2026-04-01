# 📱 Discord Trade Integration - Futures Agent

The futures agent now monitors Discord #day-trade-alerts channel for explicit trade signals and gives them **PRIORITY** over chart analysis.

---

## 🎯 Key Features

1. **Priority**: Discord trades > chart analysis
2. **Auto-sync**: Syncs Discord every 2 minutes (aligned with agent scan cycle)
3. **Signal parsing**: Extracts entry, stop, target, direction from messages
4. **Invalidation monitoring**: Exits positions if setup is cancelled
5. **Seamless integration**: Discord trades score and execute like chart setups

---

## 🔄 How It Works

### Step 1: Discord Monitoring

Every scan cycle (2 minutes), the futures agent:

```python
# At start of scan_and_act():
sync_discord_trades()  # Fetch last 50 messages from #day-trade-alerts
```

This:
- Fetches recent messages via Discord API
- Parses trade signals (BUY/SELL + entry/stop/target)
- Checks for invalidation keywords
- Updates cache at `journal/discord_trades.json`

### Step 2: Trade Signal Parsing

Recognizes patterns like:
```
"SELL SPY @ 650.50, SL 651.00, TP 648.00"
"BUY QQQ 580.25 stop 579.50 target 582.00"
"SHORT MES 6350, stop 6355, target 6340"
"SELL ES 6350, stop 6355, target 6340"
"BUY NQ 21000, stop 20950, target 21100"
```

Extracts:
- **Symbol**: SPY, QQQ, MES, ES, MNQ, NQ, S&P, SPX, NASDAQ, NDX
  - All variants normalized: ES/MES/S&P/SPX → SPY
  - All variants normalized: NQ/MNQ/NASDAQ/NDX → QQQ
- **Direction**: buy/long vs sell/short
- **Entry**: First price or explicit "entry @ X"
- **Stop**: Labeled "SL" or "stop", validated by direction
- **Target**: Labeled "TP" or "target", validated by direction

**Filters out (ignores):**
- **GC** (gold futures) - NOT SUPPORTED
- **CL** (crude oil) - NOT SUPPORTED
- Other commodities/metals - NOT SUPPORTED

**Only E-mini S&P and Nasdaq futures are traded!**

### Step 3: Priority Check

Before analyzing each symbol:

```python
# Check Discord first
discord_trade = get_active_discord_trade(sym)

if discord_trade:
    # Use Discord setup, skip chart analysis
    intraday = create_intraday_from_discord(discord_trade)
else:
    # Normal chart analysis
    intraday = get_intraday_analysis(sym, daily_bias)
```

**If Discord trade found:**
- ✅ Skips all chart analysis (daily bias, intraday scan)
- ✅ Creates synthetic "intraday" object with Discord levels
- ✅ Continues to A+ scoring and execution
- ✅ Logs as `detected_setup: "discord_signal"`

### Step 4: A+ Scoring

Discord trades score just like chart setups:
- Base score from standard criteria (still evaluated)
- HTF liquidity bonus (weekly/monthly)
- Regime adjustment
- Video validation
- **Discord bonus**: +10 if confidence high, +5 if medium (from original discord_integration.py)

### Step 5: Execution

If score ≥ A+ threshold:
- Translates to futures (SPY → MES, QQQ → MNQ)
- Places bracket order on IBKR
- Logs to `journal/futures_signals.jsonl` with `source: "discord"`

---

## 🚨 Invalidation Monitoring

### Detection

Every scan cycle checks for invalidation messages:

```python
# In _check_discord_invalidations():
for position in IBKR_positions:
    is_invalidated, reason = check_invalidation(symbol)
    if is_invalidated:
        # EMERGENCY EXIT
```

### Invalidation Keywords

Messages containing:
- "invalidated" / "invalid"
- "scratch that" / "cancel"
- "no longer valid"
- "abort" / "exit" / "get out"
- "setup broke" / "setup failed"

### Action Taken

If Discord trade is invalidated:

1. **Cancel all orders** for that contract
2. **Close position** with market order (immediate exit)
3. **Log invalidation** to `journal/discord_invalidations.jsonl`
4. **Log decision** with reason

```
🚨 DISCORD INVALIDATION DETECTED: SPY (MES202606)
   Reason: "SPY setup invalidated - broke below support"
   Position: 10 contracts @ $6357.00
   🛑 EMERGENCY EXIT: Closing position and cancelling all orders
   ✓ Position closed: filled
```

---

## 📊 Example Workflow

### Scenario: Discord Trade Execution

**9:28 AM** - Discord message:
```
"SELL SPY @ 635.50, SL 636.00, TP 633.00 - FVG entry at PWH rejection"
```

**9:30 AM** - Futures agent scan:
```
  📱 Syncing Discord #day-trade-alerts...
  ✓ Fetched 50 recent messages
  ⏭ Skipped GC (gold) trade - not supported
  🎯 NEW TRADE: SELL SPY @ 635.5, SL 636.0, TP 633.0 (R:R 5.0)
  ✓ Active trades: 1 valid, 0 invalidated
  ⏭ Skipped 1 non-E-mini trades (GC/gold, crude oil, etc.)

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ANALYZING SPY  (multi-timeframe)
  ────────────────────────────────────────────────────────────────

  📱 DISCORD TRADE FOUND: SELL @ 635.5
     Stop: 636.0, Target: 633.0, R:R: 5.0
     Age: 2m
     ✓ Using Discord setup instead of chart analysis

  ✓ Skipping chart analysis — using Discord setup

  A+ SCORE: 95  (base: 55 + HTF: +25 + regime: +5 + discord: +10)
  Threshold: 75  |  HTF cap: 40
    ✓ near_liquidity_level: 15pts
    ✓ with_structure: 10pts
    ... (other criteria) ...
    ✓ weekly_liquidity: +15pts — Within 0.3% of PWH $636.20
    ✓ monthly_liquidity: +10pts — Within 0.8% of PMH $638.50
    📱 Discord signal active: BEARISH (high conf.) - FVG entry at PWH rejection [2m ago]

  🔄 Translating to futures signal...

  📊 FUTURES SIGNAL:
     Contract: MES (Micro E-mini S&P 500)
     Direction: SELL
     Entry: 6355.0 (SPY 635.50 × 10)
     Stop: 6360.0 (SPY 636.00 × 10)
     Target: 6330.0 (SPY 633.00 × 10)
     Contracts: 33 (risk $82.50 per contract)

  ✅ PAPER BRACKET ORDER PLACED
     SELL 33 MES
     Entry: 6355.0
     Stop: 6360.0
     Target: 6330.0
     Order IDs: [12345, 12346, 12347]
```

**9:35 AM** - Entry filled, target hit

**9:40 AM** - Discord update:
```
"SPY setup invalidated - broke above stop, exit now"
```

**9:42 AM** - Next agent scan:
```
  📱 Syncing Discord #day-trade-alerts...
  ⚠️  INVALIDATION detected: 1 trades affected
      Message: "SPY setup invalidated - broke above stop, exit now"
      ✗ SPY SELL invalidated

  📊 IBKR mode: positions managed by broker-side stops

  🚨 DISCORD INVALIDATION DETECTED: SPY (MES202606)
     Reason: "SPY setup invalidated - broke above stop, exit now"
     Position: 33 contracts @ $6355.00
     🛑 EMERGENCY EXIT: Closing position and cancelling all orders
     ✓ Position closed: filled
```

---

## 📁 Files Modified

### Created:
- `discord/discord_trade_monitor.py` - Core Discord monitoring logic
- `docs/DISCORD_TRADE_INTEGRATION.md` - This file

### Modified:
- `futures/futures_agent.py`:
  - Added Discord sync at scan start
  - Added Discord priority check before chart analysis
  - Added `_check_discord_invalidations()` function
  - Calls invalidation check in IBKR position management

- `futures/ibkr_executor.py`:
  - Enhanced `get_positions()` to return dict with position data
  - Added `cancel_all_orders(contract_symbol)` method
  - Added `close_position(contract_symbol)` method

### Journal Files:
- `journal/discord_trades.json` - Active Discord trades cache
- `journal/discord_invalidations.jsonl` - Log of invalidated trades

---

## 🧪 Testing

### Manual Test:

```bash
# 1. Test Discord sync
cd /Users/rhingar/Projects/dumpster-fire
python3 discord/discord_trade_monitor.py --test

# Expected output:
#   📱 Syncing Discord #day-trade-alerts...
#   ✓ Fetched 50 recent messages
#   🎯 NEW TRADE: SELL SPY @ 635.5, SL 636.0, TP 633.0 (R:R 5.0)
#
#   ═══════════════════════════════════════════════════════════
#     ACTIVE DISCORD TRADES
#   ═══════════════════════════════════════════════════════════
#     SPY: SELL @ 635.5, SL 636.0, TP 633.0 (R:R 5.0, 5m ago)

# 2. Dry-run futures agent to see Discord integration
python3 futures/futures_agent.py --dry-run

# Should see:
#   📱 Syncing Discord #day-trade-alerts...
#   📱 DISCORD TRADE FOUND: SELL @ 635.5
#   ✓ Using Discord setup instead of chart analysis

# 3. Test invalidation detection
# Post invalidation message to #day-trade-alerts:
# "SPY setup invalidated"
# Then run:
python3 discord/discord_trade_monitor.py --sync

# Should see:
#   ⚠️  INVALIDATION detected: 1 trades affected
#   ✗ SPY SELL invalidated
```

### Live Test (Paper Trading):

```bash
# 1. Ensure TWS is running (paper mode)
ps aux | grep "Trader Workstation"

# 2. Post test trade to Discord:
# "SELL SPY @ 635.50, SL 636.00, TP 633.00"

# 3. Run futures agent (paper trading)
./scripts/run_futures_agent.sh

# 4. Watch logs:
tail -f journal/futures_agent_cron.log

# 5. Post invalidation:
# "SPY setup invalidated"

# 6. Wait for next scan (2 min)
# Should see emergency exit in logs
```

---

## 🔧 Configuration

### Discord Bot Token

Required in `.env`:
```bash
DISCORD_BOT_TOKEN=MTM0MTIyNTc3NzM3ODg4NTYzMg.GM8SG-...
```

### Channel ID

Hardcoded in `discord_trade_monitor.py`:
```python
CHANNEL_ID = "1336773655095111801"  # #day-trade-alerts
```

To monitor a different channel, update this value.

### Signal Expiry

Discord trades expire after 4 hours by default:

```python
SIGNAL_EXPIRY_HOURS = 4  # Intraday trades
```

Adjust in `discord_trade_monitor.py` if needed.

### Supported Futures

**ONLY E-mini S&P and Nasdaq futures are traded:**

Supported symbols (all map to SPY):
- ES (E-mini S&P 500)
- MES (Micro E-mini S&P 500)
- SPY
- S&P
- SPX

Supported symbols (all map to QQQ):
- NQ (E-mini Nasdaq 100)
- MNQ (Micro E-mini Nasdaq 100)
- QQQ
- NASDAQ
- NDX

**Filtered out (ignored):**
- GC (gold) - SKIPPED
- CL (crude oil) - SKIPPED
- Other metals/commodities - SKIPPED

The agent will log when it skips non-supported futures:
```
⏭ Skipped GC (gold) trade - not supported
⏭ Skipped 1 non-E-mini trades (GC/gold, crude oil, etc.)
```

---

## 🐛 Troubleshooting

### "Discord sync failed"

**Cause**: Discord API error (token invalid, rate limit, network issue)

**Fix**:
1. Check `DISCORD_BOT_TOKEN` in `.env`
2. Verify bot has access to #day-trade-alerts
3. Check Discord API status: https://status.discord.com

### "No Discord trade found but message was posted"

**Cause**: Message format not recognized OR unsupported symbol

**Fix**:
1. Check message contains keywords: buy/sell, entry, stop, target
2. Verify symbol is supported (ES/MES/NQ/MNQ, NOT GC/CL)
3. Check price format (e.g., 635.50 not 635)

Example valid formats:
```
✓ "SELL SPY @ 635.50, SL 636.00, TP 633.00"
✓ "BUY QQQ 580.25 stop 579.50 target 582.00"
✓ "SHORT MES 6350 stop 6355 target 6340"
✓ "SELL ES 6350, stop 6355, target 6340"
✓ "BUY NQ 21000, stop 20950, target 21100"
✗ "Think SPY might sell off here"  (no explicit levels)
✗ "SELL GC @ 2850, SL 2860, TP 2830"  (gold not supported)
```

**If you see "Skipped GC (gold) trade":**
- This is expected! Gold futures are intentionally filtered out
- Only E-mini S&P (ES/MES) and Nasdaq (NQ/MNQ) are traded

### "Invalidation not detected"

**Cause**: Message doesn't contain invalidation keywords

**Fix**: Use explicit keywords:
- "invalidated"
- "cancel SPY"
- "exit SPY"
- "setup broke"

Example:
```
✓ "SPY setup invalidated - broke above stop"
✓ "Cancel SPY trade"
✗ "SPY not looking good anymore"  (too vague)
```

---

## 📈 Impact on Trading

### Benefits

1. **React faster**: Execute professional setups within 2 minutes
2. **Skip bad setups**: If expert says invalidated, exit immediately
3. **Hybrid approach**: Chart analysis backup if no Discord signals
4. **Full automation**: No manual copy-paste, no missed invalidations

### Trade Priority

```
Priority 1: Active Discord trade for symbol → Execute
Priority 2: No Discord trade → Chart analysis
Priority 3: Discord invalidation → Emergency exit
```

### Risk Management

Discord trades still subject to:
- ✅ Pre-flight checks (killzone, daily limits, loss limits)
- ✅ A+ scoring threshold
- ✅ Position sizing (2% account risk)
- ✅ Broker-side bracket orders (TP/SL)
- ✅ HTF liquidity validation

Not bypassed:
- ✗ Can't override daily loss limit
- ✗ Can't trade outside killzones
- ✗ Can't exceed max trades/day
- ✗ Must still hit A+ threshold (75+)

---

## 🚀 Future Enhancements

### Potential improvements:

1. **Partial exits**: If message says "take 50% off", adjust position size
2. **Entry confirmation**: Wait for explicit "setup triggered" before executing
3. **Multi-symbol**: Support ES/NQ full-size contracts
4. **Confidence levels**: Parse "(high confidence)" → adjust scoring
5. **Trailing stops**: "move stop to breakeven" → modify existing order
6. **Position scaling**: "add to SPY" → increase position
7. **Alert on Discord trade**: Notify when Discord signal used

---

## ✅ Summary

**What was added:**
- ✅ Discord trade parsing from #day-trade-alerts
- ✅ Priority: Discord > chart analysis
- ✅ Invalidation monitoring → emergency exit
- ✅ Seamless integration with A+ scoring
- ✅ Bracket order execution
- ✅ Full journaling and logging

**What you need to do:**
- Post explicit trades to #day-trade-alerts in format: "[BUY/SELL] [SPY/QQQ] @ [entry], SL [stop], TP [target]"
- Post invalidation if setup fails: "[Symbol] invalidated" or "cancel [symbol]"
- Monitor `journal/futures_agent_cron.log` for Discord activity

**Commands to remember:**
```bash
# Test Discord sync:
python3 discord/discord_trade_monitor.py --test

# Dry-run with Discord:
python3 futures/futures_agent.py --dry-run

# View active Discord trades:
cat journal/discord_trades.json | jq '.active_trades'

# View invalidations:
tail journal/discord_invalidations.jsonl
```

🎯 **Discord trades now have priority — futures agent will execute them automatically!**
