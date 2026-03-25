# Trading Agent Service - Automated Operation

## Overview

The trading agent runs as a **macOS LaunchAgent service** that:
- Automatically starts on system boot
- Runs continuously in the background
- Scans every 2 minutes during killzones
- Sleeps outside killzones (no wasted resources)
- Auto-restarts if it crashes
- Places broker-side stop-loss orders for protection

## Quick Start

### IMMEDIATE: Start Now (Background)
```bash
cd /Users/rhingar/Documents/trainings/dumpster-fire
./start_agent_now.sh
```
Choose option 2 for background mode. Agent will run and scan every 2 min during killzones.

### Check if Running
```bash
pgrep -f "python3.*agent.py" && echo "✓ Agent is running" || echo "✗ Agent not running"
```

### View Live Logs
```bash
tail -f logs/agent_$(date +%Y%m%d).log
```

### Stop the Agent
```bash
pkill -f "python3.*agent.py.*--loop"
```

---

## Auto-Start Service (Optional - Requires Permissions)

For auto-start on boot, use the LaunchAgent service:

### Enable Full Disk Access (Required)
1. Open System Preferences → Privacy & Security → Full Disk Access
2. Click the lock to make changes
3. Click + and add: `/usr/bin/python3`
4. Restart your Mac

### Start the Service
```bash
./agent_control.sh start
```

### Check Status
```bash
./agent_control.sh status
```

### Stop the Service
```bash
./agent_control.sh stop
```

---

## How It Works

### Service Architecture

```
macOS LaunchAgent (com.trading.agent)
    ↓
start_agent.sh (wrapper script)
    ↓
agent.py --loop --interval 2
    ↓
Scans SPY/QQQ every 2 min during killzones
    ↓
Places bracket orders (broker-side stops)
```

### Killzone Schedule (ET)

| Killzone | Time (ET) | Time (PT) | When Active |
|----------|-----------|-----------|-------------|
| Asia | 8:00 PM - 12:00 AM | 5:00 PM - 9:00 PM | Evening |
| London | 2:00 AM - 5:00 AM | 11:00 PM - 2:00 AM | Late night |
| NY AM | 9:30 AM - 11:00 AM | 6:30 AM - 8:00 AM | Morning |
| NY Lunch | 12:00 PM - 1:00 PM | 9:00 AM - 10:00 AM | Mid-day |
| NY PM | 1:30 PM - 4:00 PM | 10:30 AM - 1:00 PM | Afternoon |

**Agent behavior:**
- Inside killzone → scans every 2 minutes
- Outside killzone → sleeps until next killzone
- Market closed → sleeps 60s, rechecks market status

---

## File Structure

```
/Users/rhingar/Documents/trainings/dumpster-fire/
├── agent.py                          # Main trading agent
├── start_agent.sh                    # Wrapper script (logging)
├── agent_control.sh                  # Control script (start/stop/status)
├── logs/
│   ├── agent_YYYYMMDD.log           # Daily logs from wrapper
│   ├── agent_stdout.log              # LaunchAgent stdout
│   └── agent_stderr.log              # LaunchAgent stderr
└── journal/
    ├── agent_state.json              # Daily trade state
    ├── cycle_stats.jsonl             # Per-cycle stats
    ├── analyses/                     # Analysis results
    ├── trades/                       # Trade executions
    └── decisions/                    # Decision logs

/Users/rhingar/Library/LaunchAgents/
└── com.trading.agent.plist           # LaunchAgent config
```

---

## Service Configuration

**LaunchAgent Location:**
```
/Users/rhingar/Library/LaunchAgents/com.trading.agent.plist
```

**Key Settings:**
- `RunAtLoad: true` → Auto-starts on boot
- `KeepAlive: true` → Auto-restarts if crashes
- `ThrottleInterval: 10` → 10s delay before restart

---

## Monitoring

### Check Service Status
```bash
./agent_control.sh status
```

Output shows:
- Service loaded status
- Process running status (PID)
- Process uptime
- Last 5 log lines

### View Logs in Real-Time
```bash
./agent_control.sh logs
```

Or directly:
```bash
tail -f logs/agent_$(date +%Y%m%d).log
```

### Check Recent Trades
```bash
python3 -c "from journal import list_entries; list_entries('trades', limit=5)"
```

### Check Account Status
```bash
python3 alpaca_trader.py
```

---

## Logs

### Log Files

1. **Daily Agent Log** (`logs/agent_YYYYMMDD.log`)
   - Timestamped entries
   - Full agent output
   - Cycle stats
   - Trade decisions
   - Rotates daily

2. **LaunchAgent Logs**
   - `logs/agent_stdout.log` → Standard output
   - `logs/agent_stderr.log` → Errors/warnings

### Log Rotation

Logs rotate daily automatically:
- New file created each day: `agent_YYYYMMDD.log`
- Old logs kept for history
- Clean up manually: `rm logs/agent_2026*.log`

---

## Troubleshooting

### Service Won't Start

**Check if plist is valid:**
```bash
plutil -lint ~/Library/LaunchAgents/com.trading.agent.plist
```

**Check launchd errors:**
```bash
tail -f logs/agent_stderr.log
```

**Manual test:**
```bash
./start_agent.sh
```

### Agent Not Scanning

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
python3 -c "from alpaca_trader import api; print(api.get_clock().is_open)"
```

### Agent Crashes

Service auto-restarts after 10 seconds (ThrottleInterval).

**Check crash reason:**
```bash
tail -50 logs/agent_stderr.log
```

Common issues:
- Missing environment variables → check `.env` file
- API keys expired → update `.env` file
- Network issues → check internet connection

### Stop Hanging Process

```bash
pkill -f "python3.*agent.py.*--loop"
```

Then restart service:
```bash
./agent_control.sh restart
```

---

## Uninstalling the Service

### Stop and Remove
```bash
./agent_control.sh stop
rm ~/Library/LaunchAgents/com.trading.agent.plist
```

### Keep Files, Just Disable
```bash
./agent_control.sh stop
```

Service won't auto-start on next boot.

---

## Environment Variables

Service loads `.env` file automatically. Required variables:

```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
```

If using Gemini analysis:
```bash
GEMINI_API_KEY=your_gemini_key
```

---

## Safety Features

### Built-in Guardrails
- Max 2 trades per day
- 5% max position size
- 2:1 minimum risk:reward
- 2% daily loss limit
- 30-min cooldown after loss
- 1.5× ATR stop loss

### Broker-Side Protection
- Stop-loss orders active 24/7
- Take-profit orders active 24/7
- Works even if agent crashes
- No slippage from delayed exits

### State Persistence
- Daily state saved to `journal/agent_state.json`
- Survives restarts
- Tracks trades taken
- Tracks daily P&L
- Tracks cooldown timers

---

## Performance

**Typical resource usage:**
- CPU: <1% (sleeps outside killzones)
- Memory: ~50-100 MB
- Network: Minimal (2-min API calls during killzones)

**API usage per cycle:**
- ~10-14 Alpaca API calls
- ~30 indicator computations
- ~2-4 live quotes
- All within free tier limits

---

## Maintenance

### Daily
- Check status: `./agent_control.sh status`
- Review trades: `ls -lt journal/trades/`

### Weekly
- Review logs: `./agent_control.sh logs`
- Check cycle stats: `tail -20 journal/cycle_stats.jsonl`

### Monthly
- Clean old logs: `rm logs/agent_202601*.log`
- Review performance metrics

---

## Support

**View all commands:**
```bash
./agent_control.sh
```

**Check agent help:**
```bash
python3 agent.py --help
```

**Test in dry-run mode:**
```bash
./agent_control.sh stop
python3 agent.py --loop --interval 2 --dry-run
```

---

## Next Steps

1. **Start the service:**
   ```bash
   ./agent_control.sh start
   ```

2. **Verify it's running:**
   ```bash
   ./agent_control.sh status
   ```

3. **Watch for first trade:**
   ```bash
   ./agent_control.sh logs
   ```

4. **Check positions:**
   ```bash
   python3 alpaca_trader.py
   ```

The agent is now fully automated and will scan during killzones automatically!
