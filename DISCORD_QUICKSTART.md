# Discord Integration - Quick Start

## Your Monitored Channels

✅ **stock-alerts** (ID: 545047039084593163)
✅ **day-trade-alerts** (ID: 981926799212679248)
✅ **swings** (ID: 661023267439509536)

---

## Current Setup: Manual Entry (Desktop Notifications OFF)

Since you have Discord desktop notifications disabled, use **manual signal entry**:

### When You See Important Discord Messages:

**Quick Add (copy message first):**
```bash
./add_discord_signal.sh "Your Discord message text here"
python3 discord_signal_extractor.py
```

**Or step-by-step:**
```bash
# 1. Add the signal
./add_discord_signal.sh
# Paste message, press Ctrl+D

# 2. Extract signals (runs automatically)
python3 discord_signal_extractor.py
```

---

## How It Works

### 1. You Add Discord Message
```bash
./add_discord_signal.sh "QQQ correction -10%, targets $540 and $520"
```

### 2. Extractor Processes It
- Identifies symbols: SPY, QQQ
- Extracts price targets: $540, $520
- Determines sentiment: bearish
- Calculates confidence: medium

### 3. Agent Uses It Automatically
- Every 2-minute trading cycle
- Checks for active signals
- Applies scoring bonuses:
  - **High-confidence alignment:** +10 pts
  - **At support/resistance:** +8 pts
  - **Counter-signal:** -5 pts (warning)

### Example Output:
```
A+ SCORE: 83 (base: 70 + discord: +8)
  ✓ discord_signal: +8pts — At support level $540.00
```

---

## Signal Expiry

- **Auto-expire:** 4 hours after creation
- Prevents stale signals from affecting trades

---

## Test It Now

```bash
# Run complete test
./test_discord_flow.sh

# Check active signals
cat journal/discord_signals.json | python3 -m json.tool

# View signal history
tail journal/discord_signals_history.jsonl
```

---

## Optional: Enable Automatic Capture

If you want **fully automatic** capture (no manual entry):

### Step 1: Enable Discord Desktop Notifications
Discord App → Settings → Notifications:
- ✅ Enable Desktop Notifications
- Select your 3 channels

### Step 2: Make macOS Notifications Silent
System Settings → Notifications → Discord:
- Alert Style: **None**
- ✅ Notification Center: ON
- ❌ Sounds: OFF

### Step 3: Install Monitor Services
```bash
./discord_control.sh install
./discord_control.sh start
```

Now Discord messages auto-capture every 2 minutes (aligned with trading agent).

---

## Commands

```bash
# Manual workflow (current)
./add_discord_signal.sh         # Add signal
python3 discord_signal_extractor.py  # Extract

# Automatic services (optional)
./discord_control.sh install    # Set up services
./discord_control.sh start      # Start monitoring
./discord_control.sh status     # Check status

# View signals
cat journal/discord_signals.json
tail journal/discord_signals_history.jsonl
```

---

## What Gets Extracted

Example Discord message:
> "QQQ correction down 10%, at 300MA. SPY down 7.5%. Targets: SPY $613, $590. QQQ $540, $520."

Extracted:
```json
{
  "symbols": ["SPY", "QQQ"],
  "sentiment": "bearish",
  "price_targets": {
    "SPY": {"support": [613, 590]},
    "QQQ": {"support": [540, 520]}
  },
  "confidence": "medium"
}
```

---

## Verification

Check if agent is using Discord signals:

```bash
# Restart agent to load integration
./agent_control.sh restart

# Watch for Discord signal mentions in logs
./agent_control.sh logs | grep discord
```

You should see:
- `📱 Discord signal active: ...`
- `✓ discord_signal: +X pts — ...`

---

## Quick Reference

| Action | Command |
|--------|---------|
| Add signal | `./add_discord_signal.sh "message"` |
| Extract signals | `python3 discord_signal_extractor.py` |
| Test flow | `./test_discord_flow.sh` |
| View active | `cat journal/discord_signals.json` |
| View history | `tail journal/discord_signals_history.jsonl` |

**The agent reads `journal/discord_signals.json` automatically every 2 minutes during trading.**
