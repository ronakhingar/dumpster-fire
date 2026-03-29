# Discord Signal Integration

Automatically captures and processes trading signals from Discord channels.

## Monitored Channels

1. **stock-alerts** (channel ID: 545047039084593163)
2. **day-trade-alerts** (channel ID: 981926799212679248)
3. **swings** (channel ID: 661023267439509536)

## Setup

### Method 1: Automatic Capture (Requires Desktop Notifications)

**Step 1: Enable Discord Notifications**

Discord App → Settings → Notifications:
- ✅ Enable Desktop Notifications
- Choose channels: stock-alerts, day-trade-alerts, swings

**Step 2: Silent Notifications in macOS**

System Settings → Notifications → Discord:
- Alert Style: **None**
- ✅ Notification Center: ON
- ❌ Sounds: OFF
- ❌ Banners: OFF

**Step 3: Install & Start Services**

```bash
# Install LaunchAgent services
./discord_control.sh install

# Start monitoring
./discord_control.sh start

# Check status
./discord_control.sh status
```

**How It Works:**
1. Discord sends notifications to macOS (silently)
2. Monitor reads from Notification Center database every 2 min
3. Extractor processes messages and extracts signals
4. Agent reads signals during trading cycles

---

### Method 2: Manual Entry (Works Now, No Setup Needed)

If desktop notifications are disabled, use manual signal entry:

**Quick Add:**
```bash
# Copy Discord message, then run:
./add_discord_signal.sh "QQQ correction -10%, targets $540 and $520"

# Or paste when prompted:
./add_discord_signal.sh
# (paste message, press Ctrl+D)
```

**Then extract signals:**
```bash
python3 discord_signal_extractor.py
```

---

## Signal Processing

### What Gets Extracted

From messages like:
> "QQQ is officially in a correction down 10% from highs almost at the 300MA (SPY is down 7.5%). realistic targets for SPY are $613 and $590. QQQ are $540 and $520."

Extracts:
- **Symbols:** SPY, QQQ
- **Sentiment:** bearish
- **Price Targets:** SPY support at $613, $590; QQQ support at $540, $520
- **Context:** "QQQ in correction -10%, at 300MA"
- **Confidence:** medium (inferred from tone)

### How Agent Uses Signals

During each trading cycle, agent:

1. **Checks for active signals** (not expired)
2. **Calculates bonus points:**
   - High-confidence alignment: +10 points
   - Medium-confidence alignment: +5 points
   - At support/resistance level: +8 points
   - Counter-signal: -5 points (warning)

3. **Logs influence:**
   ```
   ✓ Discord signal: bearish (medium conf.) - At support level $540.00
   Score: 75 base + 8 Discord = 83 (A+ qualified)
   ```

4. **Tracks usage:**
   - Which signals influenced which trades
   - Signal effectiveness over time

---

## Signal Expiry

- **Auto-expire:** 4 hours after creation
- Prevents stale signals from affecting trades
- History preserved in `journal/discord_signals_history.jsonl`

---

## Commands

```bash
# Control services
./discord_control.sh start      # Start monitoring
./discord_control.sh stop       # Stop monitoring
./discord_control.sh status     # Check status
./discord_control.sh test       # Test all components

# Manual operations
./add_discord_signal.sh         # Add signal manually
python3 discord_signal_extractor.py  # Extract signals now
python3 discord_integration.py  # Test integration

# View signals
cat journal/discord_signals.json  # Active signals
tail journal/discord_signals_history.jsonl  # All signals
```

---

## Files

```
discord_config.json              ← Configuration (channels, intervals)
discord_monitor.py               ← Captures notifications
discord_signal_extractor.py      ← Extracts trading signals
discord_integration.py           ← Agent integration module
discord_control.sh               ← Service control script
add_discord_signal.sh            ← Manual signal entry

journal/
  discord_raw.jsonl              ← Raw captured notifications
  discord_signals.json           ← Active signals (agent reads this)
  discord_signals_history.jsonl ← All processed signals
```

---

## Troubleshooting

**No notifications captured:**
1. Check Discord desktop notifications are enabled
2. Verify macOS notification settings (Alert: None, Center: ON)
3. Test: `./discord_control.sh test`
4. Fallback: Use manual entry (`./add_discord_signal.sh`)

**Signals not affecting trades:**
1. Check signal expiry (4 hours default)
2. Verify symbol match (SPY/QQQ only)
3. Check agent logs for "Discord signal" mentions
4. Test: `python3 discord_integration.py`

**Services not running:**
```bash
./discord_control.sh status
# If not running:
./discord_control.sh restart
```

---

## Example Workflow

**9:30 AM** - You see in Discord (day-trade-alerts):
```
SPY breaking below 650 support, next level 645.
High volume selloff, expect bounce at 645.
```

**Option A (Auto):** Notification captured automatically

**Option B (Manual):**
```bash
./add_discord_signal.sh "SPY breaking below 650 support, next level 645. High volume selloff, expect bounce at 645."
python3 discord_signal_extractor.py
```

**9:32 AM** - Agent cycle runs:
- Sees SPY at 646
- Detects potential long setup at support
- Reads Discord signal: bearish short-term, bounce expected at 645
- Adds +8 bonus (near support level)
- Score: 77 → 85 (A+ qualified)
- Logs: "Trade influenced by Discord: At support level $645"

**1:30 PM** - Signal expires (4 hours old)

---

## Integration with Agent

Agent automatically checks Discord signals during each cycle:

```python
# In agent.py (already integrated):
from discord_integration import calculate_signal_bonus, get_signal_summary

# During A+ scoring:
discord_bonus, discord_reason = calculate_signal_bonus(symbol, side, price)
total_score += discord_bonus

# Logging:
if discord_bonus != 0:
    print(f"  📱 Discord: +{discord_bonus} - {discord_reason}")
```

Signals are factored into trade decisions automatically - no manual intervention needed once set up.
