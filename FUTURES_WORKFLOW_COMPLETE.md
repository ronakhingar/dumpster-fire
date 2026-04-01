# 🔄 Complete Futures Trading Workflow - Start to End

A detailed walkthrough of exactly what happens when the futures agent trades.

---

## 📅 Example: Tuesday 9:30 AM ET - NY AM Killzone Opens

---

## ⏰ STEP 1: Cron Trigger (9:30:00 AM)

**Cron job fires:**
```bash
# From crontab:
30 9 * * 1-5 cd /Users/rhingar/Projects/dumpster-fire && ./run_futures_agent.sh
```

**What happens:**
```
1. Cron daemon (system service) reads schedule
2. Sees: "9:30 AM on weekday - time to run futures agent"
3. Executes: ./run_futures_agent.sh
```

---

## 🚀 STEP 2: Shell Script Checks (9:30:01 AM)

**File: `run_futures_agent.sh`**

### Check 1: Is futures agent already running?
```bash
# Check PID file:
if [ -f "journal/futures_agent.pid" ]; then
    OLD_PID=$(cat journal/futures_agent.pid)
    if kill -0 "$OLD_PID"; then
        # Already running!
        echo "Futures agent already running (PID $OLD_PID) — skipping"
        exit 0
    fi
fi
```

**Result:** No agent running → Continue

### Check 2: Is TWS running?
```bash
# Check if TWS process exists:
if ! pgrep -f "Trader Workstation" > /dev/null; then
    echo "⚠️  TWS not running — futures agent cannot start"
    exit 1
fi
```

**Result:** TWS running ✓ → Continue

### Launch Agent:
```bash
echo $$ > journal/futures_agent.pid  # Save PID
python3 futures_agent.py --loop --interval 2 >> journal/futures_agent_cron.log 2>&1
```

**Log written:**
```
═══════════════════════════════════════════════════════════
  FUTURES AGENT START: 2026-04-01 09:30:01 ET
  MODE: LIVE LOOP (2-min scan interval)
  BROKER: Interactive Brokers (IBKR)
  INSTRUMENTS: MES (Micro E-mini S&P 500), MNQ (Micro Nasdaq 100)
  PID: 45612
═══════════════════════════════════════════════════════════
```

---

## 🔌 STEP 3: IBKR Connection (9:30:02 AM)

**File: `futures_agent.py` - main()**

### Initialize IBKR Executor:
```python
IBKR_EXECUTOR = IBKRExecutor(paper_trading=True)
if not IBKR_EXECUTOR.connect():
    print("❌ Failed to connect to IBKR")
    return
```

**What happens:**
```python
# In IBKRExecutor.connect():
self.ib.connect('127.0.0.1', 7497, clientId=1)
# Connects to TWS on localhost:7497 (paper trading port)
```

**TWS side:**
- Accepts connection on port 7497
- Validates client
- Sends account info

**Log written:**
```
========================================================================
  FUTURES AGENT - IBKR TRADING MODE
========================================================================
  ⚙️  Initializing IBKR connection...
  ✅ Connected to IBKR (PAPER trading)
  ✅ Connected to IBKR paper account
  📊 Trading: MES (Micro E-mini S&P 500) and MNQ (Micro Nasdaq 100)
========================================================================
```

---

## 🔄 STEP 4: Agent Loop Starts (9:30:03 AM)

**File: `futures_agent.py` - run_loop()**

### Check if in killzone:
```python
is_kz, kz_label = in_killzone()
# Returns: (True, "NY_AM")
```

**Killzone check logic:**
```python
# Current time: 9:30 AM ET
# NY_AM killzone: 9:30 AM - 11:30 AM
# Result: True, we're in the killzone!
```

**Log written:**
```
  🔄 Agent starting in loop mode (interval: 2min)
     Dry run: False
     Symbols: ['QQQ', 'SPY']
     Killzones enforced: True
     A+ threshold: 80/100
     Max trades/day: 5
```

---

## 📊 STEP 5: First Scan Starts (9:30:05 AM)

**File: `futures_agent.py` - scan_and_act()**

### Pre-flight checks:

#### 1. Get account equity from IBKR:
```python
summary = IBKR_EXECUTOR.get_account_summary()
equity = float(summary.get('NetLiquidation', '25000'))
# equity = $1,000,000 (paper account)
```

#### 2. Pre-flight checks:
```python
preflight = [
    ("Killzone", in_killzone()),              # ✓ NY_AM
    ("Trade Limit", trades_today < 5),        # ✓ 0/5
    ("Max Losses", losses_today < 2),         # ✓ 0/2
    ("Daily Loss Limit", daily_pnl > -$20k),  # ✓ $0
    ("Cooldown", no_recent_loss()),           # ✓ None
]
```

**Log written:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AGENT CYCLE  |  2026-04-01 09:30:05 ET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  💰 IBKR Account Equity: $1,000,000.00

  PRE-FLIGHT CHECKS:
    ✓ Killzone: NY_AM (current ET: 09:30)
    ✓ Trade Limit: Trades today: 0/5
    ✓ Max Losses: Losses today: 0/2
    ✓ Loss Limit: Daily P&L: $0.00 (limit -$20,000.00)
    ✓ Cooldown: No recent loss — no cooldown
  📊 IBKR mode: positions managed by broker-side stops
```

**Result:** All checks pass ✓ → Continue

---

## 📈 STEP 6: Multi-Timeframe Analysis (9:30:06 AM)

### Analyzing SPY:

#### 6.1 - Get live price (Alpaca API):
```python
live_snap = get_live_price("SPY")
# Returns: {'bid': 635.68, 'ask': 635.70, 'last': 635.69}
snap_price = (635.68 + 635.70) / 2  # $635.69
```

#### 6.2 - Weekly liquidity map:
```python
weekly_ctx = get_weekly_context("SPY", 635.69)
# Fetches 1Week bars, detects:
# - PWH: $639.12
# - PWL: $633.11 (VERY_CLOSE - 0.41% away!)
# - Equal lows: $634.03
```

**Log written:**
```
────────────────────────────────────────────────────────────────────────
  ANALYZING SPY  (multi-timeframe)
────────────────────────────────────────────────────────────────────────

  SPY  bid=$635.68  ask=$635.70  last_close=$635.69  vol=12,456

  📅 WEEKLY LIQUIDITY MAP for SPY
     PWH: $639.12   PWL: $633.11
     This Week: H=$638.45  L=$631.80
     Key Levels (6):
       ▼ $    633.11  VERY_CLOSE   (0.41%)  Prior Week Low
       ▼ $    634.03  VERY_CLOSE   (0.27%)  Equal Lows x2 (liquidity pool)
     ➤ Nearest BELOW: $633.11 — Prior Week Low
```

#### 6.3 - Monthly liquidity map:
```python
monthly_ctx = get_monthly_context("SPY", 635.69)
# Fetches 1Month bars, detects:
# - PML: $628.49
# - Equal lows at monthly timeframe
```

#### 6.4 - Daily bias:
```python
bias_data = get_daily_bias("SPY")
# Fetches 1Day bars (last 90 days)
# Calculates:
# - EMA 9/21: Price below both → BEARISH
# - RSI: 42 (not oversold)
# Result: daily_bias = "bearish"
```

**Log written:**
```
  📅 DAILY BIAS for SPY
     Bias: BEARISH
     Price: $635.69
     EMA 9: $637.24 (price below)
     EMA 21: $638.91 (price below)
     RSI: 42.3 (neutral territory)
```

#### 6.5 - Intraday analysis:
```python
intraday = get_intraday_analysis("SPY", "bearish")
# Cascades through timeframes:
# - 15Min: Structure/context
# - 5Min: Setup confirmation
# - 1Min: Entry timing

# Detects:
# - FVG (Fair Value Gap) at $636.50-$636.00
# - Market structure shift (MSS) bearish
# - Price in premium (above 50% of recent range)

# Returns:
{
    "recommendation": "sell",
    "confidence": 85,
    "detected_setup": "FVG_entry",
    "trade": {
        "entry": 635.69,
        "stop_loss": 636.00,
        "take_profit": 634.80,
        "risk_reward": 2.87
    },
    "market_state": {...}
}
```

**Log written:**
```
  📅 INTRADAY ANALYSIS for SPY
     15Min: FVG detected @ $636.50-$636.00
     5Min: Confirms bearish structure
     1Min: Entry trigger activated

     Setup: FVG_entry (short)
     Confidence: 85%
     Entry: $635.69
     Stop: $636.00 (+$0.31 risk)
     Target: $634.80 (-$0.89 reward)
     R:R: 2.87:1
```

---

## ⭐ STEP 7: A+ Scoring System (9:30:08 AM)

**File: `futures_agent.py` - score_setup()**

### 7.1 - Base criteria (9 checks):
```python
checks = {
    "market_structure_shift": True,       # 20 pts ✓
    "killzone_timing": True,              # 10 pts ✓ (NY_AM)
    "liquidity_target": True,             # 10 pts ✓ (PWL)
    "ema_confirmation": True,             # 5 pts ✓
    "htf_alignment": True,                # 5 pts ✓
    "rsi_not_extreme": True,              # 5 pts ✓
    "volume_confirmation": False,         # 0 pts ✗
    "clean_price_action": True,           # 5 pts ✓
    "risk_reward_met": True,              # 5 pts ✓ (2.87:1 > 2:1)
}
base_score = 65  # Sum of met criteria
```

### 7.2 - HTF liquidity bonus:
```python
# Weekly PWL at $633.11 (0.41% away - VERY_CLOSE)
weekly_bonus = 25 pts

# Monthly equal lows at $634.03 (0.27% away - VERY_CLOSE)
monthly_bonus = 20 pts (capped at 45 total)

htf_total = 45 pts  # Capped at HTF_BONUS_CAP
```

### 7.3 - Smart regime adjustment:
```python
# Weekly context says: "high_volatility"
regime = "high_volatility"
setup = "FVG_entry"

# From REGIME_SETUP_MODIFIERS:
# high_volatility + FVG_entry = +5 pts (gaps clearer in volatility)
regime_adjustment = +5 pts
```

### 7.4 - FOMC timing:
```python
fomc_timing = get_fomc_timing()
# Returns: {"stage": "normal", "hours_until": 168}
# No FOMC this week
fomc_adjustment = 0 pts
```

### 7.5 - Video insights validation:
```python
validation = validate_setup_against_videos(
    setup_type="FVG_entry",
    direction="sell",
    confidence=85
)
# Finds 3 matching examples in video database
video_validation = 10 pts

tf_check = check_timeframe_alignment("1Day", "15Min")
# HTF bias from daily, LTF entry from 15Min - aligned
timeframe_bonus = 5 pts

video_bonus = 15 pts
```

### 7.6 - Discord signal check:
```python
discord_bonus, discord_reason = calculate_signal_bonus("SPY", "sell", 635.69)
# Checks recent Discord signals
# No active signal matching this setup
discord_bonus = 0 pts
```

### Final score calculation:
```python
total_score = (
    65        # base_score
    + 45      # htf_total
    + 5       # regime_adjustment
    + 0       # fomc_adjustment
    + 15      # video_bonus
    + 0       # discord_bonus
) = 130
```

**Log written:**
```
  A+ SCORE: 130  (base: 65 + HTF: +45 + regime: +5 + fomc: +0 + video: +15 + discord: +0)
  Threshold: 80  |  HTF cap: 45
  Using NY_AM killzone weights

    ✓ market_structure_shift: 20pts
    ✓ killzone_timing: 10pts (NY_AM)
    ✓ liquidity_target: 10pts
    ✓ ema_confirmation: 5pts
    ✓ htf_alignment: 5pts
    ✓ rsi_not_extreme: 5pts
    ✗ volume_confirmation: 0pts
    ✓ clean_price_action: 5pts
    ✓ risk_reward_met: 5pts (2.87:1)

    ✓ weekly_liquidity: +25pts — PWL $633.11 (VERY_CLOSE 0.41%)
    ✓ monthly_liquidity: +20pts — Equal Lows $634.03 (VERY_CLOSE 0.27%)
    ✓ regime_adjustment: +5pts — high_volatility + FVG_entry
    ✓ video_validation: +15pts — 3 matching examples + timeframe aligned
```

**Result:** Score 130 >= 80 threshold ✅ → **TRADE SIGNAL!**

---

## 🎯 STEP 8: Signal Validation (9:30:09 AM)

### Check R:R ratio:
```python
if trade["risk_reward"] < 2.0:
    # Skip - R:R too low
    pass

# Our R:R = 2.87 ✓
```

### Check live price hasn't moved:
```python
live = get_live_price("SPY")
live_mid = (live["bid"] + live["ask"]) / 2  # $635.69
entry_price = 635.69
slippage_pct = abs(635.69 - 635.69) / 635.69  # 0%

if slippage_pct > 0.5%:
    # Skip - price moved too much
    pass

# Our slippage = 0% ✓
exec_price = 635.69
```

**Log written:**
```
  💹 Live quote: bid=$635.68  ask=$635.70  mid=$635.69  (entry was $635.69)

  🎯 TRADE SIGNAL: SELL SPY
     Daily Bias:  BEARISH
     Entry (15m): $635.69
     Exec Price:  $635.69
     Stop:        $636.00
     Target:      $634.80
     R:R:         2.87:1
     A+ Score:    130 (base 65 + HTF +45)
     Weekly Lvl:  Prior Week Low @ $633.11
```

---

## 🔄 STEP 9: Futures Translation (9:30:10 AM)

**File: `futures_agent.py` - inside try block**

### Translate SPY → MES:
```python
futures_signal = translate_signal(
    signal={
        "symbol": "SPY",
        "side": "sell",
        "entry": 635.69,
        "stop": 636.00,
        "target": 634.80,
        "score": 130,
        "setup": "FVG_entry",
    },
    account_equity=1_000_000,  # IBKR account
    risk_pct=0.02,              # 2% risk
    use_micro=True              # MES (not ES)
)
```

**Translation logic:**
```python
# SPY → MES conversion:
# MES = SPY × 10, rounded to 0.25 tick

entry_futures = 635.69 × 10 = 6356.9 → 6357.00 (rounded)
stop_futures = 636.00 × 10 = 6360.0 → 6360.00
target_futures = 634.80 × 10 = 6348.0 → 6348.00

# Risk/Reward in futures terms:
# MES point value = $5
risk_points = 6360.00 - 6357.00 = 3 points
risk_dollars = 3 × $5 = $15 per contract

reward_points = 6357.00 - 6348.00 = 9 points
reward_dollars = 9 × $5 = $45 per contract

rr_ratio = $45 / $15 = 3:1

# Position sizing (2% account risk):
account_risk = $1,000,000 × 0.02 = $20,000
contracts = $20,000 / $15 = 1,333 contracts

# But wait, that's too many! Capped at reasonable size:
recommended_contracts = 33  # Practical limit for testing

total_risk = 33 × $15 = $495
total_reward = 33 × $45 = $1,485
```

**Log written:**
```
  🔄 Translating to futures signal...

  📊 FUTURES SIGNAL:
     Contract: MES (Micro E-mini S&P 500)
     Side: SELL
     Entry: 6357.00
     Stop: 6360.00
     Target: 6348.00
     Contracts: 33
     Risk: $495.00
     Reward: $1,485.00
     R:R: 3.00:1
```

---

## 📤 STEP 10: IBKR Order Placement (9:30:11 AM)

**File: `ibkr_executor.py` - place_bracket_order()**

### Check connection:
```python
if not IBKR_EXECUTOR or not IBKR_EXECUTOR.connected:
    raise Exception("IBKR not connected")

# Connected ✓
```

### Get MES contract:
```python
contract = Future('MES', '202606', 'CME')  # June 2026 expiry
self.ib.qualifyContracts(contract)
# TWS validates contract with CME
```

### Create bracket order:
```python
bracket = self.ib.bracketOrder(
    action='SELL',
    quantity=33,
    limitPrice=6357.0,      # Entry
    takeProfitPrice=6348.0, # Target
    stopLossPrice=6360.0    # Stop
)

# Returns 3 orders:
# [0] Entry: SELL 33 MES @ 6357.0 LIMIT
# [1] Take Profit: BUY 33 MES @ 6348.0 LIMIT (attached to entry)
# [2] Stop Loss: BUY 33 MES @ 6360.0 STOP (attached to entry)
```

### Submit to IBKR:
```python
trades = []
for order in bracket:
    trade = self.ib.placeOrder(contract, order)
    trades.append(trade)

# TWS sends orders to CME
# CME validates and acknowledges

order_ids = [123, 124, 125]
```

**What happens at TWS/IBKR:**
1. Receives 3 orders from API
2. Validates account has margin ($1,200 × 33 = $39,600 required)
3. Validates contract exists and is tradeable
4. Submits orders to CME exchange
5. CME places orders in book
6. Orders become active

**Log written:**
```
  ✅ PAPER BRACKET ORDER PLACED
     SELL 33 MES
     Entry: 6357.0
     Stop: 6360.0
     Target: 6348.0
     Order IDs: [123, 124, 125]
```

---

## 📝 STEP 11: Logging (9:30:12 AM)

### Log futures signal:
```python
log_futures_signal(futures_signal)
# Writes to: journal/futures_signals.jsonl
```

**File written: `journal/futures_signals.jsonl`:**
```json
{
  "timestamp": "2026-04-01T09:30:12-04:00",
  "original_signal": {
    "symbol": "SPY",
    "side": "sell",
    "entry": 635.69,
    "stop": 636.00,
    "target": 634.80,
    "score": 130,
    "setup": "FVG_entry"
  },
  "futures_signal": {
    "symbol": "MES",
    "contract_name": "Micro E-mini S&P 500",
    "side": "sell",
    "entry": 6357.0,
    "stop": 6360.0,
    "target": 6348.0,
    "risk_per_contract": 15.0,
    "reward_per_contract": 45.0,
    "risk_reward_ratio": 3.0,
    "recommended_contracts": 33,
    "total_risk": 495.0,
    "total_reward": 1485.0,
    "margin_required": 39600
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

### Log decision:
```python
_log_sym_decision(
    sym="SPY",
    decision="order_placed_ibkr",
    reason=f"SELL 33 MES @ 6357.0 — orders [123, 124, 125]",
    scores={"base": 65, "htf": 45, "regime": 5, "video": 15, "final": 130},
    ...
)
# Writes to: journal/decisions.jsonl
```

**File written: `journal/decisions.jsonl`:**
```json
{
  "timestamp": "2026-04-01T09:30:12-04:00",
  "symbol": "SPY",
  "decision": "order_placed_ibkr",
  "reason": "SELL 33 MES @ 6357.0 — orders [123, 124, 125]",
  "detected_setup": "FVG_entry",
  "recommendation": "sell",
  "daily_bias": "bearish",
  "scores": {
    "base": 65,
    "weekly_bonus": 25,
    "monthly_bonus": 20,
    "htf_total": 45,
    "regime_adjustment": 5,
    "video_bonus": 15,
    "discord_bonus": 0,
    "final": 130
  },
  "trade_levels": {
    "entry": 6357.0,
    "stop_loss": 6360.0,
    "take_profit": 6348.0,
    "risk_reward": 3.0,
    "contracts": 33,
    "order_ids": [123, 124, 125],
    "futures_symbol": "MES"
  }
}
```

### Update daily state:
```python
_record_trade()
# Updates: journal/daily_state.json
# - trades_taken: 0 → 1
# - last_trade_time: 09:30:12
```

**Log written:**
```
  ✅ IBKR order placed: [123, 124, 125] [BRACKET ORDER - broker-side stops active]
```

---

## 📊 STEP 12: TWS Order Display (9:30:12 AM)

**In TWS Orders Panel:**

| Order ID | Status | Side | Qty | Symbol | Type | Price | Filled |
|----------|--------|------|-----|--------|------|-------|--------|
| 123 | Submitted | SELL | 33 | MES JUN26 | LMT | 6357.0 | 0 |
| 124 | Submitted | BUY | 33 | MES JUN26 | LMT | 6348.0 | 0 |
| 125 | Submitted | BUY | 33 | MES JUN26 | STP | 6360.0 | 0 |

**Order linkage (OCO - One Cancels Other):**
- Order 123 (entry) is parent
- Orders 124 & 125 (TP/SL) are children
- When 123 fills, 124 & 125 activate
- When 124 OR 125 fills, the other cancels

---

## ⏸️ STEP 13: Wait for Fill (9:30:13 - 9:35:42 AM)

### Market price moves:
```
9:30:13 - MES @ 6358.0 (above our 6357.0 entry)
9:31:45 - MES @ 6357.5 (getting close)
9:32:18 - MES @ 6357.25 (almost there)
9:35:42 - MES @ 6357.0 ✓ FILLED!
```

### Entry order fills (9:35:42 AM):

**CME Exchange:**
- Matches our SELL 33 MES @ 6357.0 with market BUY order
- Fills all 33 contracts
- Sends fill report to IBKR

**IBKR TWS:**
- Receives fill confirmation
- Updates order 123 status: Submitted → Filled
- Activates child orders 124 & 125
- Sends notification to API

**TWS Orders Panel updates:**

| Order ID | Status | Side | Qty | Symbol | Type | Price | Filled | Avg Price |
|----------|--------|------|-----|--------|------|-------|--------|-----------|
| 123 | **Filled** | SELL | 33 | MES JUN26 | LMT | 6357.0 | **33** | **6357.0** |
| 124 | **Submitted** | BUY | 33 | MES JUN26 | LMT | 6348.0 | 0 | - |
| 125 | **Submitted** | BUY | 33 | MES JUN26 | STP | 6360.0 | 0 | - |

**TWS Portfolio Panel:**

| Symbol | Position | Mkt Price | Avg Cost | Unrealized P&L |
|--------|----------|-----------|----------|----------------|
| MES JUN26 | **-33** (short) | 6357.0 | 6357.0 | $0.00 |

---

## 📈 STEP 14: Price Movement & Target Hit (9:35:43 - 10:12:15 AM)

### Market drops (as expected):
```
9:35:43 - MES @ 6357.0 (entry)
9:38:12 - MES @ 6355.0 (-2 points, +$330)
9:42:08 - MES @ 6353.0 (-4 points, +$660)
9:51:33 - MES @ 6350.0 (-7 points, +$1,155)
10:08:24 - MES @ 6348.5 (-8.5 points, +$1,402.50)
10:12:15 - MES @ 6348.0 ✓ TARGET HIT!
```

### Take profit order fills (10:12:15 AM):

**CME Exchange:**
- Matches our BUY 33 MES @ 6348.0 with market SELL order
- Fills all 33 contracts
- Sends fill report to IBKR

**IBKR TWS:**
- Receives fill confirmation
- Updates order 124 status: Submitted → Filled
- **Automatically cancels order 125 (stop loss)** - OCO triggered!
- Position closed

**TWS Orders Panel final:**

| Order ID | Status | Side | Qty | Symbol | Type | Price | Filled | Avg Price |
|----------|--------|------|-----|--------|------|-------|--------|-----------|
| 123 | Filled | SELL | 33 | MES JUN26 | LMT | 6357.0 | 33 | 6357.0 |
| 124 | **Filled** | BUY | 33 | MES JUN26 | LMT | 6348.0 | **33** | **6348.0** |
| 125 | **Cancelled** | BUY | 33 | MES JUN26 | STP | 6360.0 | 0 | - |

**TWS Portfolio Panel:**

| Symbol | Position | Mkt Price | Avg Cost | Unrealized P&L | Realized P&L |
|--------|----------|-----------|----------|----------------|--------------|
| MES JUN26 | **0** (closed) | 6348.0 | - | $0.00 | **+$1,485.00** |

---

## 💰 STEP 15: Calculate P&L (10:12:16 AM)

### Trade summary:
```
Entry:  SELL 33 MES @ 6357.0
Exit:   BUY 33 MES @ 6348.0
Points: 6357.0 - 6348.0 = 9 points profit
Value:  9 points × $5/point × 33 contracts = $1,485

Commissions: 33 contracts × 2 (round-trip) × $0.25 = $16.50
Net profit: $1,485.00 - $16.50 = $1,468.50
```

### Account update:
```
Starting balance: $1,000,000.00
+ Realized P&L:   $   1,485.00
- Commissions:    $      16.50
─────────────────────────────────
Ending balance:   $1,001,468.50
```

**TWS Account Window:**
```
Net Liquidation: $1,001,468.50
Available Funds: $1,001,468.50
Buying Power:    $4,005,874.00
Today's P&L:     +$1,468.50 (+0.15%)
```

---

## 📊 STEP 16: Next Scan (10:14:00 AM)

**Agent continues scanning:**

**Log written:**
```
  📊 CYCLE STATS
     Setups found:   1
     Trades:         1
     Elapsed:        42.3min

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CYCLE COMPLETE  |  10:14:00 ET
  Trades today: 1/5 | Losses: 0/2
  Daily P&L:    +$1,468.50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ⏳ Next scan in 2 minutes...
```

**Agent sleeps for 2 minutes, then repeats from STEP 5.**

---

## 🔄 STEP 17: Continuous Operation Until Killzone Ends

### 10:16:00 AM - Scan 2:
```
Analyzing SPY... Score 72 < 80 → Skip
Analyzing QQQ... Score 68 < 80 → Skip
Next scan in 2 minutes...
```

### 10:18:00 AM - Scan 3:
```
Analyzing SPY... Score 65 < 80 → Skip
Analyzing QQQ... Score 91 >= 80 → TRADE SIGNAL!
[Repeats full workflow for QQQ → MNQ]
```

### This continues until...

### 11:30:00 AM - Killzone ends:
```python
is_kz, kz_label = in_killzone()
# Returns: (False, None)

# Agent detects: No longer in killzone
print("Outside killzone (11:30 ET) — next opens in ~30 min, sleeping...")
time.sleep(300)  # Sleep 5 min, check again
```

### Agent sleeps until next killzone:

```
11:35:00 - Check killzone → False, sleep
11:40:00 - Check killzone → False, sleep
11:45:00 - Check killzone → False, sleep
...
12:00:00 - Check killzone → True! (NY Lunch)
          → Resume scanning
```

---

## 🛑 STEP 18: Market Close (4:00 PM)

### Agent detects market closed:
```python
if not market_is_open():
    print("Market closed — sleeping 60s before recheck...")
    time.sleep(60)
    continue
```

### Agent remains running, checking every 60 seconds:
```
4:01 PM - Market closed, sleep
4:02 PM - Market closed, sleep
...
8:00 PM - Next killzone (Asia)!
          → Resume scanning
```

---

## ✅ Complete Workflow Summary

**Time: 9:30:00 AM → 10:14:00 AM (44 minutes)**

| Step | Time | Action | Duration |
|------|------|--------|----------|
| 1 | 9:30:00 | Cron trigger | 1 sec |
| 2 | 9:30:01 | Shell checks (PID, TWS) | 1 sec |
| 3 | 9:30:02 | IBKR connection | 1 sec |
| 4 | 9:30:03 | Agent loop starts | 2 sec |
| 5 | 9:30:05 | Pre-flight checks | 1 sec |
| 6 | 9:30:06 | Multi-timeframe analysis | 2 sec |
| 7 | 9:30:08 | A+ scoring (130 pts) | 1 sec |
| 8 | 9:30:09 | Signal validation | 1 sec |
| 9 | 9:30:10 | Futures translation (SPY→MES) | 1 sec |
| 10 | 9:30:11 | IBKR bracket order | 1 sec |
| 11 | 9:30:12 | Logging (futures_signals.jsonl) | 1 sec |
| 12 | 9:30:12 | TWS displays orders | instant |
| 13 | 9:30:13 - 9:35:42 | Wait for entry fill | 5 min 29 sec |
| 14 | 9:35:43 - 10:12:15 | Price drops to target | 36 min 32 sec |
| 15 | 10:12:16 | Calculate P&L: +$1,468.50 | 1 sec |
| 16 | 10:14:00 | Next scan starts | - |
| 17 | 10:14 - 11:30 | Continuous scanning | 1 hr 16 min |
| 18 | 11:30+ | Killzone ends, sleep | - |

**Result:**
- ✅ 1 trade executed
- ✅ Profit: +$1,468.50
- ✅ R:R achieved: 3:1
- ✅ All logged correctly
- ✅ Agent continues running

---

## 🎯 Key Takeaways

**What happens automatically:**
1. Cron triggers agent at killzone
2. Agent connects to IBKR
3. Analyzes SPY/QQQ every 2 minutes
4. Detects A+ setups (score 80+)
5. Translates to MES/MNQ
6. Places bracket orders on IBKR
7. TWS manages exits (TP/SL)
8. Logs everything
9. Repeats until killzone ends

**Zero manual intervention required!**

**Files involved:**
- `crontab` - Triggers at 9:30 AM
- `run_futures_agent.sh` - Checks & launches
- `futures_agent.py` - Main logic
- `ibkr_executor.py` - IBKR API
- `futures_translator.py` - SPY→MES conversion
- `journal/futures_signals.jsonl` - Trade log
- `journal/decisions.jsonl` - Decision log
- `journal/futures_agent_cron.log` - Execution log

**TWS involvement:**
- Accepts API connection (port 7497)
- Receives bracket orders
- Manages order lifecycle
- Reports fills back to agent
- Handles broker-side stops

🚀 **That's the complete workflow from cron to profit!**
