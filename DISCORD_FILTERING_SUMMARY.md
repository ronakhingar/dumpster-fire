# ✅ Discord Trade Filtering

## 🎯 What Gets Traded

**E-mini S&P, Nasdaq, and Gold futures:**

### Supported Symbols → SPY (E-mini S&P 500)
- **SPY** - Direct reference
- **MES** - Micro E-mini S&P 500
- **ES** - E-mini S&P 500
- **S&P** - Common name
- **SPX** - Index symbol

### Supported Symbols → QQQ (E-mini Nasdaq 100)
- **QQQ** - Direct reference
- **MNQ** - Micro E-mini Nasdaq 100
- **NQ** - E-mini Nasdaq 100
- **NASDAQ** - Common name
- **NDX** - Index symbol

### Supported Symbols → GLD (Micro Gold) ✨
- **GLD** - Direct reference
- **MGC** - Micro Gold futures
- **GC** - Gold futures
- **GOLD** - Common name

---

## 🚫 What Gets Filtered Out

### Ignored Futures (will NOT trade):
- **CL** - Crude oil futures ❌
- **CRUDE** - Crude oil ❌
- **OIL** - Oil ❌
- Other commodities/metals ❌

### Agent Behavior:
When a non-supported trade is posted, you'll see:
```
⏭ Skipped crude oil trade - not supported
⏭ Skipped 1 unsupported trades (crude oil, etc.)
```

---

## 📝 Examples

### ✅ ACCEPTED (will trade):

```
✅ "SELL SPY @ 635.50, SL 636.00, TP 633.00"
✅ "BUY QQQ 580.25 stop 579.50 target 582.00"
✅ "SHORT MES 6350, stop 6355, target 6340"
✅ "SELL ES 6350, stop 6355, target 6340"
✅ "BUY NQ 21000, stop 20950, target 21100"
✅ "LONG MNQ 21000 sl 20950 tp 21100"
✅ "SELL S&P @ 6350, SL 6355, TP 6340"
✅ "BUY NASDAQ 21000, stop 20950, target 21100"
✅ "SELL GC @ 2850, SL 2860, TP 2830"      (gold ✨)
✅ "BUY GOLD 2850 stop 2840 target 2870"   (gold ✨)
✅ "SHORT MGC 2850, stop 2860, target 2830" (gold ✨)
```

### ❌ REJECTED (will skip):

```
❌ "SELL CL @ 85.50, SL 86.00, TP 84.00"   (crude)
❌ "BUY CRUDE 85.50 stop 85.00 target 87.00" (crude)
```

---

## 🧪 Verification Test

Run the test suite to verify filtering:

```bash
cd /Users/rhingar/Projects/dumpster-fire
python3 discord/test_trade_parsing.py
```

**Expected output:**
```
========================================================================
DISCORD TRADE PARSING TESTS
========================================================================
✅ PASS: "SELL SPY @ 635.50, SL 636.00, TP 633.00..."
   → Parsed: SELL SPY @ 635.5, SL 636.0, TP 633.0

✅ PASS: "BUY QQQ 580.25 stop 579.50 target 582.00..."
   → Parsed: BUY QQQ @ 580.25, SL 579.5, TP 582.0

✅ PASS: "SHORT MES 6350, stop 6355, target 6340..."
   → Parsed: SELL SPY @ 6350.0, SL 6355.0, TP 6340.0

✅ PASS: "SELL ES 6350, stop 6355, target 6340..."
   → Parsed: SELL SPY @ 6350.0, SL 6355.0, TP 6340.0

✅ PASS: "SELL GC @ 2850, SL 2860, TP 2830..."
   → Parsed: SELL GLD @ 2850.0, SL 2860.0, TP 2830.0

✅ PASS: "BUY GOLD 2850 stop 2840 target 2870..."
   → Parsed: BUY GLD @ 2850.0, SL 2840.0, TP 2870.0

✅ PASS: "SHORT MGC 2850, stop 2860, target 2830..."
   → Parsed: SELL GLD @ 2850.0, SL 2860.0, TP 2830.0

========================================================================
RESULTS: 15 passed, 0 failed
========================================================================
```

---

## 🔍 Monitoring Filters

### Watch for filtered trades:

```bash
# Monitor live agent log
tail -f journal/futures_agent_cron.log | grep -i "skipped\|gold\|crude"
```

### Check active Discord trades:

```bash
# View what's being tracked
cat journal/discord_trades.json | jq '.active_trades[] | {symbol, direction, entry}'

# Should see SPY, QQQ, or GLD (never CL crude oil)
```

---

## 📊 Why Filter Crude?

**Reasons for filtering crude oil (but not gold):**

1. **Strategy mismatch**: Agent's A+ scoring is calibrated for financial instruments (equities, gold)
2. **Different dynamics**: Crude oil has unique market drivers (OPEC, supply disruptions, geopolitical)
3. **Risk parameters**: Position sizing assumes equity/gold volatility patterns
4. **Focused approach**: S&P/Nasdaq/Gold provide sufficient diversification
5. **Cleaner logs**: Avoids confusion from unsupported instruments

**Gold is supported** because:
- Financial instrument (safe haven asset)
- Correlates with inflation/USD like equities
- Discord signals provide setup validation
- MGC offers similar position sizing as MES/MNQ

---

## 🚀 Usage

**Just post to Discord:**
```
SELL ES 6350, stop 6355, target 6340
```

**Agent will:**
1. ✅ Recognize ES → maps to SPY
2. ✅ Parse entry/stop/target
3. ✅ Score setup
4. ✅ Execute on IBKR (if A+ score met)

**If someone posts gold:**
```
SELL GC @ 2850, SL 2860, TP 2830
```

**Agent will:**
1. ✅ Detect GC → maps to GLD
2. ✅ Parse entry/stop/target
3. ✅ Score setup
4. ✅ Execute MGC on IBKR (if A+ score met)

**If someone posts crude oil:**
```
SELL CL @ 85.50, SL 86.00, TP 84.00
```

**Agent will:**
1. ⏭ Detect CL (crude oil)
2. ⏭ Skip parsing
3. ⏭ Log "Skipped crude oil trade - not supported"
4. ⏭ Continue to next message

---

## ✅ Summary

- **Trades**: ES/MES (S&P), NQ/MNQ (Nasdaq), GC/MGC (Gold) ✨
- **Filters**: CL (crude oil), other commodities
- **Logging**: Shows when unsupported trades are skipped
- **Testing**: `python3 discord/test_trade_parsing.py`
- **Verified**: All 15 test cases pass ✅

🎯 **Post ES/NQ/GC trades → Agent executes. Post CL/crude → Agent skips!**
