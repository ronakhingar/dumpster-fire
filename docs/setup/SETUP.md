# Setup Guide - Trading Agent Installation

Complete guide to set up the autonomous trading agent from scratch.

---

## Overview

This trading agent:
- Trades SPY and QQQ on Alpaca paper trading
- Scans every 2 minutes during ICT killzones
- Uses deterministic technical analysis (no LLMs)
- Places broker-side bracket orders (stop-loss + take-profit)
- Runs continuously in the background

---

## Prerequisites

### System Requirements
- **macOS** (tested on macOS 14+)
- **Python 3.9+**
- **Git**
- **8GB+ RAM**
- **Stable internet connection**

### Required Accounts
1. **Alpaca Paper Trading Account** (free)
   - Sign up: https://alpaca.markets/
   - Get API keys for paper trading (not live trading)

2. **Optional: Google Gemini API** (for video analysis pipeline)
   - Get key: https://makersuite.google.com/app/apikey

---

## Installation Steps

### 1. Clone the Repository

```bash
cd ~/Documents  # or wherever you want to install
git clone <your-repo-url> dumpster-fire
cd dumpster-fire
```

### 2. Install Python Dependencies

```bash
# Install required packages
pip3 install -r requirements.txt

# Verify installation
python3 -c "import alpaca_trade_api, psycopg2, whisper; print('✓ All packages installed')"
```

**If you get errors:**
```bash
# On macOS, you may need:
brew install postgresql  # for psycopg2
```

### 3. Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit with your API keys
nano .env  # or use any text editor
```

**Add your Alpaca API keys:**
```bash
# Alpaca Paper Trading API Keys
ALPACA_API_KEY=your_alpaca_paper_key_here
ALPACA_SECRET_KEY=your_alpaca_paper_secret_here

# Optional: Gemini API (only needed for video analysis)
GEMINI_API_KEY=your_gemini_key_here

# Optional: Database (only needed for video pipeline)
DATABASE_URL=postgresql://user:pass@localhost/tradingdb
```

**Get your Alpaca keys:**
1. Log in to https://alpaca.markets/
2. Go to Paper Trading → API Keys
3. Generate new API key pair
4. **Important:** Use PAPER trading keys, not live!

### 4. Verify Connection

```bash
# Test Alpaca connection
python3 alpaca_trader.py
```

You should see:
```
Account  status=ACTIVE  equity=$100,000.00 ...
SPY  bid=$XXX.XX  ask=$XXX.XX ...
QQQ  bid=$XXX.XX  ask=$XXX.XX ...
✓ All functions operational.
```

### 5. Test Analysis Engine

```bash
# Run standalone analysis on SPY
python3 analyze.py SPY 1Day
```

You should see a detailed analysis with:
- Market state (price, EMAs, RSI, MACD, ATR, VWAP)
- Detected setup (if any)
- Trade levels (entry, stop, target)
- Confidence score
- Reasons for/against

### 6. Test Agent (Dry Run)

```bash
# Run one scan cycle without placing trades
python3 agent.py --dry-run
```

This will:
- Check pre-flight conditions
- Analyze SPY and QQQ
- Score setups against A+ criteria
- Show what trades WOULD be placed
- Log everything to `journal/`

---

## Running the Agent

### Quick Start (Background Mode)

```bash
./start_agent_now.sh
```

Choose option **2** for background mode. The agent will:
- Run continuously in the background
- Scan every 2 minutes during killzones
- Sleep outside killzones
- Log to `logs/agent_YYYYMMDD.log`

### Manual Control

```bash
# Start in foreground (see output, Ctrl+C to stop)
python3 agent.py --loop --interval 2

# Start in background
nohup python3 agent.py --loop --interval 2 > logs/agent.log 2>&1 &

# Check if running
pgrep -f "agent.py" && echo "✓ Running" || echo "✗ Not running"

# Stop agent
pkill -f "python3.*agent.py.*--loop"

# View logs
tail -f logs/agent_$(date +%Y%m%d).log
```

### Auto-Start on Boot (Optional)

Requires macOS Full Disk Access permissions.

**Enable Full Disk Access:**
1. System Preferences → Privacy & Security → Full Disk Access
2. Click lock to make changes
3. Click + and add `/usr/bin/python3`
4. Restart Mac

**Start service:**
```bash
./agent_control.sh start
./agent_control.sh status
```

See [AGENT_SERVICE.md](AGENT_SERVICE.md) for full service documentation.

---

## Monitoring

### Check Positions
```bash
python3 alpaca_trader.py
```

Shows:
- Account equity and cash
- Open positions with P&L
- Open orders (including bracket stops)
- Recent fills

### View Logs
```bash
# Real-time logs
tail -f logs/agent_$(date +%Y%m%d).log

# Recent trades
ls -lt journal/trades/ | head -5

# Recent decisions
ls -lt journal/decisions/ | head -5

# Cycle statistics
tail -10 journal/cycle_stats.jsonl | jq .
```

### Check Daily State
```bash
cat journal/agent_state.json
```

Shows:
- Current date
- Trades taken today
- Daily P&L
- Last loss time (for cooldown)

---

## Configuration

### Guardrails (memories.py)

Edit `memories.py` to customize:

```python
GUARDRAILS = {
    "max_trades_per_day": 2,        # Max trades per day
    "max_position_pct": 0.05,       # 5% of equity per trade
    "min_risk_reward": 2.0,         # Minimum 2:1 R:R
    "daily_loss_limit_pct": 0.02,   # 2% max daily drawdown
    "stop_atr_multiplier": 1.5,     # Stop = 1.5× ATR
    "require_killzone": True,       # Only trade in killzones
    "cooldown_after_loss_min": 30,  # 30 min cooldown after loss
}
```

### A+ Scoring (memories.py)

```python
A_PLUS_THRESHOLD = 80  # Minimum score to qualify (out of 100)

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

### Killzones (memories.py)

```python
KILLZONES = {
    "asia":     {"start": "20:00", "end": "00:00", "label": "Asia"},
    "london":   {"start": "02:00", "end": "05:00", "label": "London"},
    "ny_am":    {"start": "09:30", "end": "11:00", "label": "NY AM"},
    "ny_lunch": {"start": "12:00", "end": "13:00", "label": "NY Lunch"},
    "ny_pm":    {"start": "13:30", "end": "16:00", "label": "NY PM"},
}
```

All times are in **Eastern Time (ET)**.

---

## Troubleshooting

### Agent Won't Start

**Check Python version:**
```bash
python3 --version  # Should be 3.9 or higher
```

**Check dependencies:**
```bash
pip3 install -r requirements.txt
```

**Check .env file:**
```bash
cat .env | grep ALPACA
```

### "Operation not permitted" Errors

This is a macOS security feature. Two options:

1. **Use manual start** (easiest):
   ```bash
   ./start_agent_now.sh
   ```

2. **Grant Full Disk Access** (for auto-start):
   - System Preferences → Privacy & Security
   - Full Disk Access → Add `/usr/bin/python3`

### No Trades Being Placed

**Check if in killzone:**
```bash
python3 -c "
from datetime import datetime
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo('America/New_York'))
print(f'Current ET: {now.strftime(\"%H:%M\")}')
"
```

**Check market status:**
```bash
python3 -c "from alpaca_trader import api; clock = api.get_clock(); print(f'Market: {\"OPEN\" if clock.is_open else \"CLOSED\"}')"
```

**Check recent decisions:**
```bash
ls -lt journal/decisions/ | head -3
cat journal/decisions/<latest_file>.json | jq .
```

Common reasons for no trades:
- Outside killzone
- Market closed
- Daily trade limit reached (2/day)
- No A+ setups (score < 80)
- Daily loss limit hit

### API Errors

**"Invalid API key":**
- Verify keys in `.env` file
- Make sure using PAPER trading keys
- Keys should start with `PK` (paper key) not `AK` (live key)

**"429 Too Many Requests":**
- Alpaca rate limit hit
- Increase `--interval` (e.g., `--interval 5`)
- Default 2-min interval should be fine for paper trading

### Logs Show Errors

**Check error logs:**
```bash
tail -50 logs/agent_stderr.log
```

**Common issues:**
- Missing dependencies → reinstall with pip3
- Invalid symbols → only SPY and QQQ allowed
- Database errors → only needed for video pipeline

---

## Understanding the Journal

Every scan and trade is logged to `journal/`:

### Analyses (`journal/analyses/`)
```bash
2026-03-25_150000_SPY_15Min.json
```
Contains:
- Full market state (all indicators)
- Detected setup
- Recommendation (buy/sell/hold/no_trade)
- Confidence score
- Trade levels
- Reasons for/against

### Trades (`journal/trades/`)
```bash
2026-03-25_150001_sell_SPY.json
```
Contains:
- Order ID
- Symbol, side, qty
- Entry/stop/target prices
- Order status
- Timestamp

### Decisions (`journal/decisions/`)
```bash
2026-03-25_150001_order_placed_SPY.json
```
Contains:
- Outcome (order_placed, skipped, etc.)
- Full reasoning
- A+ score breakdown
- Criteria checklist
- HTF context (weekly/monthly levels)
- Market state

### Cycle Stats (`journal/cycle_stats.jsonl`)
```json
{
  "timestamp": "2026-03-25T15:00:00-04:00",
  "alpaca_api_calls": 14,
  "symbols_analyzed": 2,
  "setups_detected": 1,
  "trades_executed": 1,
  "elapsed_seconds": 2.4
}
```

---

## Bracket Orders Explained

Every trade automatically places 3 orders with Alpaca:

1. **Entry Order** (limit)
   - Buy/Sell at calculated entry price
   - Example: SELL 7 SPY @ $656.55

2. **Stop-Loss Order** (broker-side)
   - Automatically closes if price hits stop
   - Example: Stop @ $657.00 (for short)
   - **Active 24/7** even if agent crashes

3. **Take-Profit Order** (broker-side)
   - Automatically closes if price hits target
   - Example: Target @ $655.77 (for short)
   - **Active 24/7** even if agent crashes

**Verify bracket orders:**
```bash
python3 -c "from alpaca_trader import get_open_orders; get_open_orders()"
```

See [BRACKET_ORDERS.md](BRACKET_ORDERS.md) for implementation details.

---

## Advanced Setup

### Video Analysis Pipeline (Optional)

Process trading education videos to extract trades and insights.

**Requirements:**
```bash
# Install additional dependencies
pip3 install whisper openai-whisper google-generativeai

# Set up PostgreSQL database
brew install postgresql
createdb tradingdb

# Run pipeline
python3 pipeline.py
```

See `pipeline.py` docstring for full pipeline documentation.

### Database Setup (Optional)

Only needed for video analysis pipeline:

```sql
CREATE TABLE media_sources (
    id SERIAL PRIMARY KEY,
    file_path TEXT UNIQUE,
    filename TEXT,
    category TEXT,
    program TEXT,
    session TEXT,
    file_size BIGINT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- See pipeline.py for full schema
```

---

## Safety & Risk Management

### Built-in Protections

1. **Position Sizing**
   - Max 5% of equity per trade
   - Scales with ATR volatility

2. **Stop Loss**
   - 1.5× ATR from entry
   - Broker-side (always active)

3. **Risk:Reward**
   - Minimum 2:1 required
   - Target = 2× stop distance

4. **Daily Limits**
   - Max 2 trades per day
   - Max 2% daily drawdown
   - 30-min cooldown after loss

5. **Entry Filters**
   - Only trades in killzones
   - Only A+ setups (score ≥80)
   - Multi-timeframe alignment required
   - HTF liquidity confluence

### Paper Trading Only

**IMPORTANT:** This bot is configured for **paper trading only**.

To use with live trading (NOT recommended without extensive testing):
1. Change Alpaca base URL in `alpaca_trader.py`
2. Use live API keys (start with `AK` not `PK`)
3. Test extensively on paper first
4. Start with minimal position sizes
5. Monitor closely for first week

**We are not responsible for any financial losses.**

---

## Getting Help

### Check Logs First
```bash
tail -f logs/agent_$(date +%Y%m%d).log
```

### Review Documentation
- [README.md](README.md) - Overview
- [AGENT_SERVICE.md](AGENT_SERVICE.md) - Service management
- [BRACKET_ORDERS.md](BRACKET_ORDERS.md) - Stop-loss implementation
- [docs/pipeline_architecture.md](docs/pipeline_architecture.md) - Video pipeline

### Common Commands Reference
```bash
# Start agent
./start_agent_now.sh

# Check status
pgrep -f agent.py && echo "Running" || echo "Not running"

# View logs
tail -f logs/agent_$(date +%Y%m%d).log

# Stop agent
pkill -f "python3.*agent.py"

# Check positions
python3 alpaca_trader.py

# Test connection
python3 -c "from alpaca_trader import get_account; get_account()"

# Run dry-run
python3 agent.py --dry-run
```

---

## Next Steps After Setup

1. **Test with dry-run:**
   ```bash
   python3 agent.py --dry-run
   ```

2. **Start in background:**
   ```bash
   ./start_agent_now.sh  # Choose option 2
   ```

3. **Monitor first hour:**
   ```bash
   tail -f logs/agent_$(date +%Y%m%d).log
   ```

4. **Check first trade:**
   ```bash
   ls -lt journal/trades/ | head -1
   cat journal/trades/<latest>.json | jq .
   ```

5. **Verify bracket orders:**
   ```bash
   python3 alpaca_trader.py
   ```

6. **Review daily:**
   - Check logs for errors
   - Review trade decisions
   - Monitor performance metrics

---

## Uninstalling

```bash
# Stop agent
pkill -f "python3.*agent.py"

# Remove service (if installed)
./agent_control.sh stop
rm ~/Library/LaunchAgents/com.trading.agent.plist

# Remove files
cd ~/Documents
rm -rf dumpster-fire

# Uninstall packages (optional)
pip3 uninstall -r requirements.txt
```

---

**Ready to trade!** Start with `./start_agent_now.sh` and monitor the logs. 🚀
