# ⏰ Dual Agent Cron Automation

Both agents now run automatically at all killzones!

## 📋 Cron Schedule

Both **agent.py** (stocks) and **futures_agent.py** (futures) run at:

| Killzone | Time (ET) | Days | Description |
|----------|-----------|------|-------------|
| **Asia** | 8:00 PM | Mon-Fri | Evening session |
| **London** | 2:00 AM | Tue-Sat | Early morning (crosses midnight) |
| **NY AM** | 9:30 AM | Mon-Fri | Market open |
| **NY Lunch** | 12:00 PM | Mon-Fri | Midday reversal |
| **NY PM** | 1:30 PM | Mon-Fri | Afternoon session |

**Both agents scan every 2 minutes during their active killzone.**

---

## 🤖 What Runs Automatically

### Stock Agent (Alpaca)
```bash
# Launched by cron at each killzone:
./run_agent.sh
  → python3 agent.py --loop --interval 2
  → Trades SPY/QQQ on Alpaca
  → Logs to: journal/agent_cron.log
```

### Futures Agent (IBKR)
```bash
# Launched by cron at each killzone:
./run_futures_agent.sh
  → Checks TWS is running
  → python3 futures_agent.py --loop --interval 2
  → Trades MES/MNQ on IBKR
  → Logs to: journal/futures_agent_cron.log
```

---

## ✅ Installation Complete

Crontab is already installed and active:
```bash
# View current crontab:
crontab -l

# You should see 5 entries for each agent (10 total)
```

---

## 📊 Monitoring

### Check if agents are running:
```bash
# Stock agent:
ps aux | grep "agent.py --loop"

# Futures agent:
ps aux | grep "futures_agent.py --loop"

# Both should show if in active killzone
```

### Watch live logs:
```bash
# Stock agent:
tail -f journal/agent_cron.log

# Futures agent:
tail -f journal/futures_agent_cron.log
```

### Check PID files:
```bash
# Stock agent PID:
cat journal/agent.pid

# Futures agent PID:
cat journal/futures_agent.pid
```

---

## 🚦 Requirements

### Stock Agent (agent.py)
- ✅ Alpaca API keys in `.env`
- ✅ No other requirements

### Futures Agent (futures_agent.py)
- ✅ Alpaca API keys in `.env` (for market data)
- ✅ IBKR credentials in `.env`
- ⚠️ **TWS must be running** on port 7497 (paper) or 7496 (live)

**Important:** If TWS is not running, futures agent will log a warning and skip that cycle.

---

## 🔧 Safety Features

### PID Locking
- Prevents duplicate agent processes
- If agent is already running, cron job exits gracefully
- Check with: `cat journal/agent.pid` or `cat journal/futures_agent.pid`

### TWS Check (Futures Agent)
- Script checks if TWS is running before starting
- If TWS not found, logs warning and exits
- No errors if TWS offline

### Log Rotation
- Logs automatically rotate at 5MB
- Old logs compressed and cleaned up

---

## 🛠️ Manual Control

### Stop agents:
```bash
# Kill stock agent:
kill $(cat journal/agent.pid)

# Kill futures agent:
kill $(cat journal/futures_agent.pid)

# Or kill both:
pkill -f "agent.py --loop"
pkill -f "futures_agent.py --loop"
```

### Start manually:
```bash
# Stock agent:
./run_agent.sh

# Futures agent (TWS must be running):
./run_futures_agent.sh
```

### Disable cron:
```bash
# Edit crontab:
crontab -e

# Comment out lines with # to disable
# Or remove entire crontab:
crontab -r
```

---

## 📈 Expected Behavior

### During Killzones (e.g., 9:30 AM - 11:30 AM ET):
```
9:30 AM - Cron launches both agents
9:32 AM - First scan completes
9:34 AM - Second scan completes
... scans every 2 minutes ...
11:30 AM - Killzone ends, agents sleep
11:32 AM - Next killzone check
12:00 PM - NY Lunch killzone starts, agents wake up
```

### Outside Killzones:
```
Both agents check every 60 seconds if killzone opened
When killzone starts, agents wake up and begin scanning
When killzone ends, agents sleep until next killzone
```

---

## 🐛 Troubleshooting

### Stock agent not running:
```bash
# Check log:
tail journal/agent_cron.log

# Common issues:
# - Alpaca credentials missing/invalid
# - Market closed
# - Not in killzone

# Test manually:
python3 agent.py --dry-run
```

### Futures agent not running:
```bash
# Check log:
tail journal/futures_agent_cron.log

# Common issues:
# - TWS not running (most common!)
# - IBKR API not enabled in TWS
# - Wrong port (7497 for paper, 7496 for live)

# Test TWS connection:
python3 ibkr_executor.py test

# Test futures agent manually:
python3 futures_agent.py --dry-run
```

### Both agents running but not trading:
```bash
# Check if in killzone:
python3 -c "from agent import in_killzone; print(in_killzone())"

# Check daily limits:
# - Max 5 trades/day per agent
# - Max 2 losses/day per agent
# - Daily loss limit

# View decisions log:
tail journal/decisions.jsonl
```

---

## 🌍 AWS Migration Ready

When moving to AWS:

1. **Update crontab path:**
   ```bash
   # Change this line in crontab:
   AGENT_DIR=/Users/rhingar/Projects/dumpster-fire
   # To:
   AGENT_DIR=/home/ubuntu/dumpster-fire
   ```

2. **Set environment variables:**
   ```bash
   # Add to ~/.bashrc:
   export ALPACA_API_KEY=xxx
   export ALPACA_SECRET_KEY=xxx
   export IBKR_PAPER_USERNAME=xxx
   export IBKR_PAPER_PASSWORD=xxx
   ```

3. **Install TWS/IB Gateway on EC2:**
   - Use IB Gateway (lightweight version)
   - Configure to start on boot
   - Ensure port 7497 accessible

4. **Install crontab:**
   ```bash
   cd /home/ubuntu/dumpster-fire
   crontab crontab_dual_agents.txt
   ```

---

## ✅ Summary

**What's automated:**
- ✅ Stock agent runs at all killzones (Alpaca)
- ✅ Futures agent runs at all killzones (IBKR)
- ✅ Both scan every 2 minutes
- ✅ PID locking prevents duplicates
- ✅ TWS check for futures agent
- ✅ Separate logs for each agent
- ✅ Automatic log rotation

**What you need to do:**
- Keep TWS running for futures agent (can automate this too)
- Monitor logs occasionally
- Nothing else!

**Commands to remember:**
```bash
# Watch both agents:
tail -f journal/agent_cron.log journal/futures_agent_cron.log

# Check if running:
ps aux | grep "agent.py --loop"
ps aux | grep "futures_agent.py --loop"

# Verify crontab:
crontab -l | grep agent
```

🚀 **Both agents are now fully automated!**
