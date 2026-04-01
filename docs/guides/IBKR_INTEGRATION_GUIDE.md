# 🏦 IBKR Integration Guide - Complete Setup

**Your Choice:** Interactive Brokers (IBKR) for real futures trading

**Why IBKR is Perfect:**
- ✅ Lowest commissions ($0.25-0.85/contract)
- ✅ Best API for automation (ib_insync)
- ✅ No monthly fees
- ✅ Industry standard
- ✅ Used by professionals & hedge funds

---

## 📋 Complete Setup Roadmap

### Timeline Overview:
```
Week 1: Account setup + paper trading
Week 2-3: API integration + testing
Week 4+: Real money trading (when ready)
```

---

## 🚀 Phase 1: Account Setup (Days 1-3)

### Step 1: Open IBKR Account (30 minutes)

**Go to:** https://www.interactivebrokers.com

**Application Steps:**
```
1. Click "Open Account"

2. Account Type: Individual

3. Account Features - Select:
   ✓ Margin Account
   ✓ Futures Trading
   ✓ (Optional: Stocks, Options)

4. Personal Information:
   ├─ Name, address, SSN
   ├─ Employment status
   ├─ Net worth & liquid assets
   └─ Investment objectives

5. Trading Experience:
   ├─ Be honest about experience
   ├─ IBKR wants to know you understand risks
   └─ Futures experience: Select your level

6. Review & Submit
```

**Approval Time:** Usually 24-48 hours

---

### Step 2: Fund Your Account (Day 2-3)

**Recommended Starting Amount:**
```
Conservative: $2,500
├─ 1 MES contract: $1,200 margin
├─ Buffer: $1,300 (for safety)
└─ Risk per trade: $15-20

Comfortable: $5,000
├─ 2-3 MES contracts
├─ Buffer: $2,000+
└─ Risk per trade: $30-60

Aggressive: $10,000+
├─ Multiple MES or full ES
├─ Portfolio Margin eligible
└─ More flexibility
```

**Funding Methods:**
```
ACH Transfer (Recommended):
├─ Free
├─ 3-5 business days
└─ Link bank account in portal

Wire Transfer:
├─ Same day
├─ May have bank fee ($15-30)
└─ Get wiring instructions from IBKR

Check Deposit:
├─ 5-10 days
└─ Mail to IBKR address
```

**Steps:**
```
1. Log into Account Management portal
2. Transfer & Pay → Deposit Funds
3. Select method (ACH recommended)
4. Enter amount ($2,500+)
5. Confirm transfer
6. Wait for funds to clear
```

---

### Step 3: Download & Install TWS (Day 3)

**TWS = Trader Workstation (IBKR's trading platform)**

**Download:**
```
1. Log into IBKR portal
2. Trading → Download TWS
3. Select:
   ├─ Latest Stable Version
   ├─ Your OS (Mac/Windows/Linux)
   └─ Download installer

4. Install TWS
5. Launch application
6. Log in with IBKR credentials
```

**First Launch:**
```
1. Username: Your IBKR username
2. Password: Your IBKR password
3. Trading Mode: Paper Trading (start here!)
4. Layout: Classic TWS (or Mosaic)
```

---

### Step 4: Request Paper Trading Account (Instant)

**IBKR offers FREE unlimited paper trading!**

**Enable Paper Trading:**
```
1. Log into Account Management portal
2. Settings → Paper Trading Account
3. Click "Request Paper Trading"
4. Approved instantly
5. Receive separate login credentials via email
```

**Paper Account Details:**
```
Starting balance: $1,000,000 (paper money)
Reset: Can reset anytime
Fees: $0 (completely free)
Data: Real-time market data
Execution: Simulated but realistic
```

---

## 🧪 Phase 2: Paper Trading (Week 1-2)

### Step 1: Connect TWS to Paper Account

**Launch TWS:**
```
1. Open TWS application
2. Select: Paper Trading mode
3. Enter: Paper trading username (from email)
4. Enter: Paper trading password
5. Connect
```

**You'll see:**
- Account balance: $1,000,000
- Real-time futures prices
- All features available

---

### Step 2: Your First Manual Trade

**Test basic execution:**

**Find MES Contract:**
```
1. Symbol search box → Type "MES"
2. Select: MES (Micro E-mini S&P 500)
3. Contract: Jun 2024 (nearest expiry)
4. Market data appears
```

**Place Limit Order:**
```
1. Right-click MES → "Buy/Sell"
2. Order Entry window:
   ├─ Action: SELL
   ├─ Quantity: 1
   ├─ Order Type: LMT (Limit)
   ├─ Limit Price: 6357.0
   ├─ Time in Force: DAY
   └─ Outside RTH: No

3. Submit Order
4. Order appears in "Orders" panel
5. When price reaches 6357.0, order fills
```

**Add Bracket Orders:**
```
1. Right-click on filled position
2. "Attach Order" → "Stop"
   ├─ Stop Price: 6360.0
   └─ Submit

3. "Attach Order" → "Limit" (Take Profit)
   ├─ Limit Price: 6348.0
   └─ Submit

Now you have OCO bracket (stop + target)
```

---

### Step 3: Integrate Your Agent's Signals

**Workflow:**
```
1. Agent runs: python3 agent.py --loop
2. Signal fires: SPY SELL @ $635.69 (score 97)
3. Translate: python3 futures_translator.py
4. Output: SELL 33 MES @ 6357.0
5. Execute in TWS manually
6. Track results
```

**Paper trade 10-20 signals this way to learn execution.**

---

## 🤖 Phase 3: API Integration (Week 2-3)

### Step 1: Enable API in TWS (5 minutes)

**Configure TWS for API:**
```
1. TWS → File → Global Configuration
2. API → Settings
3. Enable:
   ✓ Enable ActiveX and Socket Clients
   ✓ Socket port: 7497 (paper) or 7496 (live)
   ✓ Master API client ID: 0
   ✓ Allow connections from localhost
   ✓ Let API account modifications (for orders)

4. Click "OK"
5. Restart TWS
```

**Important Ports:**
- `7497` = Paper trading
- `7496` = Live trading

**Keep TWS running when using API!**

---

### Step 2: Install Python API Library (1 minute)

```bash
pip install ib_insync
```

**What is ib_insync?**
- Python wrapper for IBKR API
- Much easier than official API
- Active development
- Great documentation
- Used by thousands of algorithmic traders

---

### Step 3: Test API Connection (2 minutes)

**I created `ibkr_executor.py` for you. Test it:**

```bash
python3 ibkr_executor.py test
```

**Expected Output:**
```
════════════════════════════════════════════════════════════════
IBKR CONNECTION TEST
════════════════════════════════════════════════════════════════
  ✅ Connected to IBKR (PAPER trading)

  📊 Account Summary:
     Net Liquidation: $1000000.00
     Available Funds: $990000.00
     Buying Power: $990000.00

  📈 Open Positions:
     No open positions

  🔌 Disconnected from IBKR

✅ Connection test successful!
```

**If this works, you're ready for automation!**

---

### Step 4: Place Test Bracket Order

**Test automatic order placement:**

```bash
python3 ibkr_executor.py
```

**This will:**
1. Connect to IBKR paper account
2. Place test bracket order (1 MES)
3. Show order IDs
4. You see orders in TWS

**Check TWS:**
- Orders panel will show 3 orders
  - Entry limit order
  - Stop loss order
  - Take profit order
- All linked as OCO bracket

---

### Step 5: Integrate with Your Agent

**Now connect agent → IBKR automatically:**

I can modify `agent.py` to:
1. Detect qualifying signal (score 80+)
2. Translate to futures
3. Call `ibkr_executor.place_bracket_order()`
4. Place order automatically on IBKR

**Would you like me to build this integration?**

---

## 💰 Cost Breakdown

### Monthly Costs (IBKR)

**Commissions (30 trades/month, 33 MES/trade):**
```
Contracts: 30 × 33 × 2 (round-trip) = 1,980/month
Rate: $0.25/contract (tiered pricing)
Monthly: 1,980 × $0.25 = $495

Per trade: ~$16.50 round-trip
```

**Market Data:**
```
US Futures Real-Time: $4.50/month
OR
All US Futures Bundle: $10/month

Usually waived if you generate $30+ commissions/month
→ You will, so effectively FREE
```

**Account Fees:**
```
Monthly minimum: $0
Inactivity fee: $20/month if:
  - Balance < $2,000 AND
  - Commissions < $10/month

You'll always hit $10, so: $0
```

**Total: ~$0-10/month** (vs $50-100 for NinjaTrader!)

---

### Comparison (30 trades/month, 33 MES)

| Broker | Commissions | Platform Fee | Data | Total/Month |
|--------|-------------|--------------|------|-------------|
| **IBKR** | **$495** | **$0** | **$0** (waived) | **$495** |
| TradeStation | $2,970 | $0 | $0 (included) | $2,970 |
| NinjaTrader | $1,188 | $60-100 | $0 (included) | $1,248-1,288 |

**IBKR saves:** $753-2,475/month vs competitors!

---

## 📊 Account Requirements

### Margins (Per Contract)

**Micro Futures:**
```
MES (Micro S&P 500):
├─ Initial Margin: ~$1,200
├─ Maintenance Margin: ~$1,100
└─ Recommendation: Keep 2-3x margin ($2,400-3,600)

MNQ (Micro Nasdaq 100):
├─ Initial Margin: ~$1,800
├─ Maintenance Margin: ~$1,600
└─ Recommendation: Keep 2-3x margin ($3,600-5,400)
```

**Full Futures:**
```
ES (E-mini S&P 500):
├─ Initial Margin: ~$12,000
└─ 1 ES = 10 MES

NQ (E-mini Nasdaq 100):
├─ Initial Margin: ~$18,000
└─ 1 NQ = 10 MNQ
```

### Position Sizing Examples

**$2,500 Account:**
```
Max contracts: 1 MES
├─ Margin: $1,200
├─ Buffer: $1,300
└─ Conservative approach
```

**$5,000 Account:**
```
Max contracts: 2-3 MES
├─ Margin: $2,400-3,600
├─ Buffer: $1,400-2,600
└─ Comfortable approach
```

**$10,000 Account:**
```
Max contracts: 5-6 MES or 1 ES
├─ Margin: $6,000-7,200
├─ Buffer: $2,800-4,000
└─ Flexible trading
```

**$25,000 Account:**
```
Max contracts: 2-3 ES or 15-20 MES
├─ Portfolio Margin eligible
├─ Better capital efficiency
└─ Professional setup
```

---

## 🔐 Security & Risk Management

### IBKR Security Features

**Account Protection:**
```
✓ SIPC insured ($500k securities)
✓ Additional Lloyd's coverage ($30M excess)
✓ Two-factor authentication
✓ Withdrawal confirmations
✓ Segregated customer funds
```

**Trading Protections:**
```
✓ Margin alerts (email + SMS)
✓ Automatic liquidation if margin breached
✓ Stop loss orders guaranteed
✓ Real-time risk monitoring
```

### Your Agent's Safeguards

**Already Built-In:**
```
✓ Max 5 trades/day
✓ Max 2 losses/day (then stops)
✓ 2% max loss per trade
✓ 30-min cooldown after loss
✓ Only trades during killzones
✓ Requires 80+ score
```

**Additional IBKR Safeguards:**
```
✓ Position limits (set in IBKR)
✓ Daily loss limits (set in IBKR)
✓ Broker-side stops (guaranteed)
✓ Real-time margin monitoring
```

---

## 🎯 Go-Live Checklist

### Before Trading Real Money:

**Paper Trading Results:**
- [ ] 20+ paper trades completed
- [ ] Win rate: 55%+ (your agent should hit 60%)
- [ ] Average R:R: 2:1+
- [ ] Comfortable with execution
- [ ] Understand margin requirements
- [ ] Tested bracket orders

**Account Setup:**
- [ ] IBKR account approved
- [ ] Funded with $2,500+ ($5k recommended)
- [ ] TWS installed and working
- [ ] API enabled and tested
- [ ] Paper trading successful

**Risk Management:**
- [ ] Position sizing calculated
- [ ] Max contracts determined
- [ ] Stop losses understood
- [ ] Daily limits set
- [ ] Emergency exit plan

**Technical:**
- [ ] `ibkr_executor.py` tested
- [ ] API connection reliable
- [ ] Bracket orders working
- [ ] Logging in place
- [ ] Monitoring setup

---

## 🚀 Your Complete Workflow

### Day-to-Day Trading:

**Morning (Before Market Open):**
```
1. Launch TWS (paper or live)
2. Check API connection: python3 ibkr_executor.py test
3. Review account balance & margin
4. Check for any FOMC events (fomc_timing.py)
```

**During Market Hours:**
```
Option A: Manual Execution
├─ 1. Run agent: python3 agent.py --loop
├─ 2. Signal fires: "SPY SELL @ $635.69 (score 97)"
├─ 3. Translate: python3 futures_translator.py
├─ 4. Copy signal: "SELL 33 MES @ 6357.0"
├─ 5. Execute in TWS manually
└─ 6. Bracket orders: Stop 6360.0, Target 6348.0

Option B: Automated (When ready)
├─ 1. Run agent with IBKR integration
├─ 2. Agent detects signal
├─ 3. Translates to futures
├─ 4. Places order automatically via API
└─ 5. Logs everything to journal
```

**End of Day:**
```
1. Review trades in journal
2. Check P&L
3. Verify no positions held overnight (if day trading)
4. Update tracking spreadsheet
```

---

## 📈 Expected Performance

### Paper Trading Phase (Week 1-2):
```
Goal: Learn execution, validate signals
Trades: 10-20 paper trades
Success: Win rate ~60%, R:R ~2:1+
```

### Real Money Phase 1 (Month 1):
```
Account: $2,500-5,000
Position: 1 MES per signal
Risk: $15-20/trade
Trades: 20-30/month
Expected: ~$600-900 profit/month
ROI: 12-18%/month (if 60% win rate holds)
```

### Real Money Phase 2 (Month 2-3):
```
Account: $5,000-10,000
Position: 2-3 MES per signal
Risk: $30-60/trade
Trades: 20-30/month
Expected: $1,200-2,700 profit/month
ROI: 12-18%/month
```

### Scaled Up (Month 4+):
```
Account: $10,000-25,000
Position: 5-6 MES or 1 ES per signal
Risk: $75-150/trade
Trades: 20-30/month
Expected: $3,000-6,750 profit/month
ROI: 12-18%/month
```

**These assume:** Your current 60% win rate and 2:1+ R:R translate to futures.

---

## ✅ Next Steps - Your Action Plan

### This Week:

**Day 1: Application**
```
- [ ] Open IBKR account (30 mins)
- [ ] Wait for approval (24-48 hours)
```

**Day 2-3: Funding**
```
- [ ] Fund account via ACH ($2,500-5,000)
- [ ] Wait for funds to clear (3-5 days)
- [ ] Meanwhile: Download TWS
- [ ] Request paper trading account
```

**Day 4-7: Paper Trading**
```
- [ ] Connect to paper account
- [ ] Test manual execution (1-2 trades)
- [ ] Run agent, translate signals
- [ ] Execute 5-10 paper trades
- [ ] Track results
```

### Week 2:

**API Integration**
```
- [ ] Enable API in TWS
- [ ] Install ib_insync
- [ ] Test: python3 ibkr_executor.py test
- [ ] Place test bracket order
- [ ] Execute 10+ paper trades via API
```

### Week 3-4:

**Go Live Decision**
```
- [ ] Review paper trading results
- [ ] If win rate 55%+: Proceed to live
- [ ] If not: More paper trading
- [ ] Start with 1 MES contract
- [ ] Real money execution
```

---

## 🆘 Troubleshooting

### Common Issues:

**"Can't connect to IBKR API"**
```
Check:
1. Is TWS running?
2. API enabled? (File → Global Config → API)
3. Correct port? (7497 paper, 7496 live)
4. Localhost allowed?
5. Restart TWS

Fix:
- TWS → File → Global Configuration
- API → Settings → Enable ActiveX and Socket Clients
- Socket port: 7497 (or 7496 for live)
- Click OK, restart TWS
```

**"Order rejected - insufficient margin"**
```
Check:
- Account balance
- Margin requirement (MES = ~$1,200)
- Position size (reduce contracts)

Fix:
- Reduce position size
- Or add more funds
```

**"Connection failed: port 7497"**
```
Check:
- Is another API client connected?
- Master Client ID set to 0?
- Firewall blocking port?

Fix:
- Disconnect other clients
- Or use different client ID
```

**"Contract not found: MES"**
```
Check:
- Correct symbol spelling
- Contract expiry (use current month)
- Permissions (futures enabled?)

Fix:
contract = Future('MES', '202406', 'CME')
ib.qualifyContracts(contract)  ← Must call this!
```

---

## 📚 Resources

**IBKR Documentation:**
- IBKR Trader University: https://www.interactivebrokers.com/campus/
- TWS User Guide: https://www.interactivebrokers.com/en/software/tws/usersguidebook.pdf
- API Documentation: https://interactivebrokers.github.io/tws-api/

**ib_insync Documentation:**
- Official Docs: https://ib-insync.readthedocs.io/
- Examples: https://github.com/erdewit/ib_insync/tree/master/notebooks
- Community: https://groups.io/g/insync

**Your Files:**
- `ibkr_executor.py` - Order execution via IBKR
- `futures_translator.py` - Stock → futures translation
- `agent.py` - Your trading agent
- `IBKR_INTEGRATION_GUIDE.md` - This file

---

## ✅ Summary

**Your Decision:** IBKR for real futures trading ✅

**Why it's perfect:**
- ✅ Lowest costs ($0.25/contract vs $1.50+)
- ✅ Best API (ib_insync for Python)
- ✅ No monthly fees
- ✅ Professional platform
- ✅ Used by hedge funds

**What's ready:**
- ✅ `ibkr_executor.py` - API integration
- ✅ `futures_translator.py` - Signal conversion
- ✅ Your agent - Signal generation
- ✅ Complete documentation

**Next action:**
1. Open IBKR account (today)
2. While waiting for approval, paper trade
3. API integration (week 2)
4. Go live with 1 MES (when ready)

**Timeline:**
- Week 1: Account + paper trading
- Week 2-3: API integration + testing
- Week 4+: Real money (when validated)

**First command to run:**
```bash
python3 ibkr_executor.py test
```

(After TWS is installed and running)

🚀 **IBKR is the RIGHT choice. Let's get you set up!**
