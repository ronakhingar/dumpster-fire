# dumpster-fire 🔥

Autonomous trading agent for SPY/QQQ on Alpaca paper trading with broker-side stop protection.

## Architecture

```
agent.py              ← Main autonomous agent (scan → score → trade loop)
├── analyze.py        ← Full analysis: indicators + setup detection + trade levels
│   ├── indicator_engine.py  ← Deterministic EMA, RSI, MACD, ATR, VWAP
│   └── alpaca_trader.py     ← Alpaca API wrapper (data + execution + bracket orders)
├── memories.py       ← Trading knowledge base (A+ criteria, guardrails, killzones)
└── journal.py        ← Persists every analysis and trade to disk as JSON
```

## Knowledge Base

Distilled from TTT Mastermind 9 & 10 sessions, A+ Trade Rating Guide, Liquidity playbooks, and ICT concepts:

- **A+ Scoring** — 9 criteria totaling 100 points + up to 45 HTF bonus. Only setups scoring ≥80 qualify.
- **Self-Learning** — Daily review adjusts criteria weights based on actual win/loss outcomes
- **Killzones** — Asia, London, NY AM, NY Lunch, NY PM (ET times)
- **Macro Windows** — 20-min high-probability algo bursts
- **Guardrails** — max 2 trades/day, 5% position size, 2:1 min R:R, 2% daily loss limit, 30-min cooldown after loss
- **Broker-Side Stops** — All trades use Alpaca bracket orders with automatic stop-loss and take-profit execution

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your Alpaca paper trading keys
```

## Automated Service (Recommended)

The agent runs as a macOS LaunchAgent service - auto-starts on boot, scans every 2 min during killzones:

```bash
# Start the service (auto-starts on boot)
./agent_control.sh start

# Check status
./agent_control.sh status

# View live logs
./agent_control.sh logs

# Stop service
./agent_control.sh stop
```

See [AGENT_SERVICE.md](AGENT_SERVICE.md) for full documentation.

## Self-Learning System

Agent reviews weekly performance (Saturdays) and adjusts scoring weights:

```bash
# View learned weights
cat learned_weights.json

# View today's review
cat journal/reviews/review_$(date +%Y-%m-%d).md

# View learning history (what changed, when, and why)
python3 view_learning_history.py

# Track a specific criterion over time
python3 view_learning_history.py --criterion premium_discount

# Reset weights to defaults
python3 daily_review.py --reset
```

See [LEARNING_SYSTEM.md](LEARNING_SYSTEM.md) for full documentation.

## Manual Usage

```bash
# Single scan-and-act cycle
python3 agent.py

# Dry run — analyze only, no trades
python3 agent.py --dry-run

# Continuous loop during killzones (2-min interval)
python3 agent.py --loop --interval 2

# Standalone analysis
python3 analyze.py SPY 1Day
python3 analyze.py QQQ 1Day
```

## Guardrails

| Rule | Value |
|------|-------|
| Max trades/day | 2 |
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
