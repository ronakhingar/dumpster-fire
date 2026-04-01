# Discord Bot Setup - Real-time Signal Monitor

## Quick Start

### 1. Set Your Bot Token

```bash
export DISCORD_BOT_TOKEN="your_token_here"
```

Or add it permanently to your `~/.zshrc`:

```bash
echo 'export DISCORD_BOT_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### 2. Run the Bot

```bash
./start_discord_bot.sh
```

Or directly:

```bash
python3 discord_bot_monitor.py
```

---

## What It Does

✅ **Monitors 3 channels:** #stock-alerts, #day-trade-alerts, #swings
✅ **Market hours only:** 9 AM - 4 PM EST (weekdays)
✅ **Checks every 2 minutes** for new messages
✅ **Real-time capture:** Also captures messages instantly as they're posted
✅ **Downloads images:** Saves chart attachments automatically
✅ **JSONL format:** Compatible with existing signal extractors

---

## Output Structure

```
discord_history/realtime/
├── stock-alerts.jsonl
├── day-trade-alerts.jsonl
├── swings.jsonl
├── stock-alerts_files/
│   ├── 123456789_chart.png
│   └── ...
├── day-trade-alerts_files/
└── swings_files/
```

**Message format:**

```json
{
  "id": "1234567890",
  "timestamp": "2026-03-31T10:30:00+00:00",
  "author": "TraderName",
  "author_id": "987654321",
  "content": "SPY short setup at 635",
  "channel": "stock-alerts",
  "attachments": [
    {
      "filename": "chart.png",
      "url": "https://cdn.discordapp.com/...",
      "local_path": "discord_history/realtime/stock-alerts_files/1234567890_chart.png"
    }
  ]
}
```

---

## Running in Background

### Option 1: Screen (keeps running even after logout)

```bash
screen -S discord-bot
export DISCORD_BOT_TOKEN="your_token"
./start_discord_bot.sh

# Detach: Ctrl+A then D
# Reattach: screen -r discord-bot
```

### Option 2: nohup

```bash
export DISCORD_BOT_TOKEN="your_token"
nohup python3 discord_bot_monitor.py > discord_bot.log 2>&1 &
```

### Option 3: LaunchAgent (auto-start on login)

Create `~/Library/LaunchAgents/com.user.discord-bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.discord-bot</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/rhingar/Projects/dumpster-fire/discord_bot_monitor.py</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>DISCORD_BOT_TOKEN</key>
        <string>YOUR_TOKEN_HERE</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>/Users/rhingar/Projects/dumpster-fire</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/rhingar/Projects/dumpster-fire/discord_bot.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/rhingar/Projects/dumpster-fire/discord_bot_error.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.user.discord-bot.plist
```

---

## Integration with Signal Extractor

The bot saves messages in JSONL format. To process them:

**Option 1: Manual processing**

```bash
python3 discord_signal_extractor_enhanced.py discord_history/realtime/stock-alerts.jsonl
```

**Option 2: Create a processor script**

```bash
#!/bin/bash
# process_realtime_signals.sh

for channel in stock-alerts day-trade-alerts swings; do
    jsonl_file="discord_history/realtime/${channel}.jsonl"

    if [ -f "$jsonl_file" ]; then
        echo "Processing $channel..."
        python3 discord_signal_extractor_enhanced.py "$jsonl_file"
    fi
done
```

**Option 3: Add to cron** (run every 5 minutes during market hours)

```cron
*/5 9-16 * * 1-5 /Users/rhingar/Projects/dumpster-fire/process_realtime_signals.sh
```

---

## Troubleshooting

### Bot won't connect

- Check token is correct: `echo $DISCORD_BOT_TOKEN`
- Verify bot has been added to the Discord server
- Check bot permissions (Read Messages, Read Message History, View Channel)

### Bot can't see channels

- Make sure bot has access to the specific channels
- Check channel permissions in Discord server settings

### Bot not capturing messages

- Verify market hours (9 AM - 4 PM EST, weekdays only)
- Check bot logs for errors
- Ensure channels are named exactly: `stock-alerts`, `day-trade-alerts`, `swings`

### Check bot status

```bash
ps aux | grep discord_bot_monitor
tail -f discord_bot.log  # if running with nohup or LaunchAgent
```

---

## Next Steps

Once bot is running:

1. **Test it:** Post a test message in one of the monitored channels
2. **Verify output:** Check `discord_history/realtime/` for JSONL files
3. **Process signals:** Run signal extractor on captured data
4. **Automate:** Set up cron job to process signals every 5 minutes

**Full automation pipeline:**

```
Discord Bot (every 2 min)
    ↓
JSONL files
    ↓
Signal Extractor (every 5 min)
    ↓
opportunities.jsonl
    ↓
Agent (killzone times)
    ↓
Trades executed
```
