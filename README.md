# dumpster-fire 🔥

Autonomous trading agent for SPY/QQQ on Alpaca paper trading with broker-side stop protection.

## Project Structure

```
dumpster-fire/
├── src/                    # Core trading system
│   ├── agent.py            # Main autonomous agent (scan → score → trade)
│   ├── analyze.py          # Full analysis: indicators + setup detection
│   ├── indicator_engine.py # Deterministic EMA, RSI, MACD, ATR, VWAP
│   ├── alpaca_trader.py    # Alpaca API wrapper (data + execution)
│   ├── memories.py         # Trading knowledge base (A+ criteria, guardrails)
│   ├── journal.py          # Persists every analysis/trade to disk
│   ├── pipeline.py         # Gemini analysis pipeline
│   ├── daily_review.py     # Performance review & weight learning
│   ├── weekly_context.py   # Macro market context analysis
│   ├── alternative_data.py # External data sources (Polymarket, commodities)
│   └── fomc_timing.py      # FOMC calendar detection
├── discord/                # Discord integration
│   ├── discord_monitor.py  # Real-time signal capture
│   ├── discord_integration.py  # Signal scoring modifiers
│   ├── discord_signal_extractor.py # Parse signals from messages
│   └── discord_*.py        # Other Discord utilities
├── futures/                # Futures/IBKR trading
│   ├── futures_agent.py    # Futures trading agent (MES/MNQ)
│   ├── futures_translator.py  # Translate SPY/QQQ signals to futures
│   └── ibkr_executor.py    # Interactive Brokers execution
├── backtest/               # Backtesting engine
│   ├── backtest.py         # Main backtest runner
│   └── backtest_engine.py  # Historical analysis engine
├── video/                  # Video insights integration
│   └── video_insights_loader.py
├── scripts/                # Shell scripts
│   ├── run_agent.sh        # Launch agent (called by cron)
│   ├── run_pipeline.sh     # Launch pipeline
│   └── *.sh                # Other automation scripts
├── utils/                  # Utility scripts
│   ├── cleanup_*.py        # Image/log cleanup
│   └── notify_macos.py     # Desktop notifications
├── docs/                   # Documentation
│   ├── setup/              # Setup guides
│   ├── discord/            # Discord integration docs
│   ├── guides/             # Trading guides
│   ├── architecture/       # System architecture docs
│   └── analysis/           # Analysis reports
├── config/                 # Configuration files
│   ├── crontab_aws_ready.txt  # Cron schedule (AWS-ready)
│   └── requirements.txt    # Python dependencies
├── journal/                # Trade journal & logs
├── data/                   # Market data cache
└── README.md
```

## Knowledge Base

Distilled from TTT Mastermind 9 & 10 sessions, A+ Trade Rating Guide, Liquidity playbooks, and ICT concepts:

- **A+ Scoring** — 9 criteria totaling 100 points + up to 45 HTF bonus. Only setups scoring ≥80 qualify.
- **Self-Learning** — Daily review adjusts criteria weights based on actual win/loss outcomes
- **Killzones** — Asia, London, NY AM, NY Lunch, NY PM (ET times)
- **Macro Windows** — 20-min high-probability algo bursts
- **Guardrails** — max 5 trades/day, max 2 losses/day, 5% position size, 2:1 min R:R, 2% daily loss limit, 30-min cooldown after loss
- **Broker-Side Stops** — All trades use Alpaca bracket orders with automatic stop-loss and take-profit execution

## Setup

```bash
pip install -r config/requirements.txt
cp .env.example .env  # Add your Alpaca paper trading keys
```

## Automated Service (Recommended)

The agent runs via cron - auto-starts at killzone opens, scans every 2 min during trading hours:

```bash
# Install cron schedule (AWS-ready)
crontab config/crontab_aws_ready.txt

# View scheduled jobs
crontab -l

# Monitor agent logs
tail -f journal/agent_cron.log

# Monitor Discord
tail -f logs/discord_monitor.log
```

See [docs/setup/CRON_AUTOMATION_SETUP.md](docs/setup/CRON_AUTOMATION_SETUP.md) for full documentation.

## Self-Learning System

Agent reviews weekly performance (Saturdays) and adjusts scoring weights **per killzone** (Asia, London, NY AM, NY Lunch, NY PM).

Weekly review also analyzes macro market context and alternative data:
- **FOMC calendar** - detects upcoming Fed meetings
- **Daily trend analysis** - SPY/QQQ relative to 50/100/200-day MAs
- **VIX (fear gauge)** - volatility expectations
- **Polymarket prediction markets** - Fed decisions, jobs data sentiment
- **Commodities analysis** - Gold, oil, silver correlations with stocks
- **Financial news scanning** - Major market-moving events from past week
- **Market regime classification** - applies scoring modifiers based on combined signals

```bash
# View learned weights
cat learned_weights.json

# View today's review
cat journal/reviews/review_$(date +%Y-%m-%d).md

# View learning history (what changed, when, and why)
python3 -m utils.view_learning_history

# Track a specific criterion over time
python3 -m utils.view_learning_history --criterion premium_discount

# Reset weights to defaults
python3 -m src.daily_review --reset
```

See [LEARNING_SYSTEM.md](LEARNING_SYSTEM.md) for full documentation.

## Manual Usage

```bash
# Single scan-and-act cycle
python3 -m src.agent

# Dry run — analyze only, no trades
python3 -m src.agent --dry-run

# Continuous loop during killzones (2-min interval)
python3 -m src.agent --loop --interval 2

# Standalone analysis
python3 -m src.analyze SPY 1Day
python3 -m src.analyze QQQ 1Day

# Run backtest
python3 -m backtest.backtest --start 2026-01-01 --end 2026-03-31

# Futures agent (requires TWS running)
python3 -m futures.futures_agent --loop
```

## Guardrails

| Rule | Value |
|------|-------|
| Max trades/day | 5 |
| Max losses/day | 2 |
| Max position size | 5% of equity |
| Min risk:reward | 2:1 |
| Daily loss limit | 2% of equity |
| Stop loss | 1.5× ATR |
| Cooldown after loss | 30 minutes |
| Killzone required | Yes |
| Liquidity sweep required | Yes |
| MSS required | Yes |

## Hard Rules (from playbooks)

- No sweep = No trade
- No confirmation = No entry
- No displacement = No trade
- Minimum 2:1 risk-reward or skip
- Never long in premium, never short in discount
- Skip choppy / unclear bias days

## Discord Real-Time Signal Monitoring

Automated Discord bot captures trading signals from The Traveling Trader server in real-time:

**Monitored Channels:**
- #🚨┃stock-alerts
- #🎯┃day-trade-alerts
- #🏌🏻┃swings

**Active Hours:** 9 AM - 4 PM EST (weekdays)
**Check Interval:** Every 2 minutes + instant capture
**Output:** `discord_history/realtime/*.jsonl` + chart images

### Quick Start

```bash
# 1. Add your Discord user token to .env
./scripts/set_discord_token.sh YOUR_TOKEN_HERE

# 2. Start monitor (background via cron)
# Already handled by cron keepalive (every 5 minutes)
# Or manually:
python3 -m discord.discord_monitor --loop

# 3. Check status
./scripts/check_bot_status.sh
tail -f logs/discord_monitor.log
```

### Process Captured Signals

```bash
# Extract signals from captured messages
python3 -m discord.discord_signal_extractor_enhanced discord_history/realtime/stock-alerts.jsonl
python3 -m discord.discord_signal_extractor_enhanced discord_history/realtime/day-trade-alerts.jsonl
python3 -m discord.discord_signal_extractor_enhanced discord_history/realtime/swings.jsonl
```

**See [docs/discord/DISCORD_MONITOR_STATUS.md](docs/discord/DISCORD_MONITOR_STATUS.md) for full documentation.**
