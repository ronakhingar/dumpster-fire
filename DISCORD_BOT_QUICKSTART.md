# Discord Bot - Quick Start Guide

## 🚀 3-Step Setup

### Step 1: Add Your Token

**Option A: Using the script** (easiest)

```bash
./set_discord_token.sh YOUR_TOKEN_HERE
```

**Option B: Manually edit .env**

```bash
nano .env
# Replace PASTE_YOUR_TOKEN_HERE with your actual token
# Save: Ctrl+O, Exit: Ctrl+X
```

---

### Step 2: Start the Bot

```bash
./start_discord_bot.sh
```

---

### Step 3: Verify It's Working

You should see:

```
══════════════════════════════════════════════════════════════════════
  DISCORD BOT MONITOR - STARTED
══════════════════════════════════════════════════════════════════════
  Bot User: YourBotName
  Connected to 1 server(s)

  📡 Monitoring channels:
     Server: Trading Signals
       ✓ #stock-alerts
       ✓ #day-trade-alerts
       ✓ #swings

  ⏰ Market Hours: 09:00 AM - 04:00 PM EST
  🔄 Check Interval: 2 minutes
  💾 Output: discord_history/realtime

══════════════════════════════════════════════════════════════════════

🔍 Scanning channels at 2026-03-31 10:30:00 EST
```

---

## 📂 Where Data is Saved

```
discord_history/realtime/
├── stock-alerts.jsonl               ← All messages
├── day-trade-alerts.jsonl
├── swings.jsonl
├── stock-alerts_files/              ← Chart images
│   └── 123456789_chart.png
├── day-trade-alerts_files/
└── swings_files/
```

---

## 🔧 Running in Background

### Option 1: Screen (survives logout)

```bash
screen -S discord-bot
./start_discord_bot.sh

# Detach: Ctrl+A then D
# Reattach later: screen -r discord-bot
```

### Option 2: nohup

```bash
nohup ./start_discord_bot.sh > discord_bot.log 2>&1 &

# Check logs
tail -f discord_bot.log

# Stop it
ps aux | grep discord_bot_monitor
kill <PID>
```

---

## 🧪 Test It

1. **Post a test message** in one of the monitored Discord channels
2. **Check output:**
   ```bash
   ls -lh discord_history/realtime/
   tail discord_history/realtime/stock-alerts.jsonl
   ```
3. **Verify image download:**
   ```bash
   ls discord_history/realtime/stock-alerts_files/
   ```

---

## 🔍 Check if Bot is Running

```bash
ps aux | grep discord_bot_monitor
```

Output should show:
```
rhingar  12345  python3 discord_bot_monitor.py
```

---

## ⚠️ Troubleshooting

### "Invalid token" error

- Double-check token in `.env` file
- Make sure no extra spaces or quotes
- Verify bot exists in Discord Developer Portal

### Bot connects but doesn't capture messages

- Check market hours (9 AM - 4 PM EST, weekdays only)
- Verify channel names are exact: `stock-alerts`, `day-trade-alerts`, `swings`
- Make sure bot has permissions in Discord server

### "No access to channel" warnings

- Go to Discord server settings
- Check bot role has "Read Messages" and "Read Message History" permissions
- Ensure bot can see the specific channels

---

## 📊 Integration with Trading System

Once bot is running and capturing data, you can process signals:

```bash
# Process captured signals
python3 discord_signal_extractor_enhanced.py discord_history/realtime/stock-alerts.jsonl

# Or automate it with cron (every 5 minutes during market hours)
*/5 9-16 * * 1-5 cd /Users/rhingar/Projects/dumpster-fire && python3 discord_signal_extractor_enhanced.py discord_history/realtime/stock-alerts.jsonl
```

---

## 🛑 Stop the Bot

```bash
# If running in terminal: Ctrl+C

# If running in background:
ps aux | grep discord_bot_monitor | grep -v grep | awk '{print $2}' | xargs kill
```

---

## 📝 Files Created

- **discord_bot_monitor.py** - Main bot script
- **start_discord_bot.sh** - Easy launcher
- **set_discord_token.sh** - Token setup helper
- **.env** - Token storage (never commit this!)
- **DISCORD_BOT_SETUP.md** - Detailed documentation
- **DISCORD_BOT_QUICKSTART.md** - This file

---

## ✅ Next Steps

1. ✅ Set token → `./set_discord_token.sh YOUR_TOKEN`
2. ✅ Start bot → `./start_discord_bot.sh`
3. ✅ Run in background → `screen -S discord-bot`
4. ✅ Test by posting in Discord
5. ✅ Verify data saved → `ls discord_history/realtime/`

**That's it! Your bot is now monitoring Discord 24/7.** 🎉
