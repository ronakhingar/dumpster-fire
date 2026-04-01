# Discord App Setup Checklist

## Current Status
✅ Discord app installed and running (PID: 19699)
✅ Monitor service running (PID: 5926)
✅ Python has Full Disk Access
⚠️ Need to configure Discord notifications

---

## Setup Steps

### Step 1: Enable Notifications in Discord App

1. **Open Discord app**
2. Click your profile icon (bottom left)
3. **User Settings** (�gear icon) → **Notifications**
4. Under "Server Notification Settings":
   - Find your trading server
   - Click the server name
   - For each channel you want to monitor:
     - `#stock-alerts`
     - `#day-trade-alerts`
     - `#swings`
   - Set to: **"All Messages"** (not @mentions only)
5. Scroll down to "Enable Desktop Notifications"
   - ✅ Enable this checkbox

### Step 2: Enable Notifications in macOS

1. **Open System Settings**
2. **Notifications** (search for it if needed)
3. Find **Discord** in the left sidebar
4. Enable:
   - ✅ **Allow Notifications**
   - ✅ **Show in Notification Center**
   - ✅ **Banners** (Style: Banners or Alerts)
   - ✅ **Sounds** (optional)
   - ✅ **Badge App Icon** (optional)

---

## Test the Setup

### Send a Test Message

1. **In Discord web or another device**, send a test message to one of your monitored channels:
   ```
   Test signal: SPY at $500
   ```

2. **Check if notification appears** on your Mac:
   - Should see a notification banner
   - Should hear sound (if enabled)
   - Check Notification Center (swipe from right edge)

3. **Check if monitor captured it** (wait ~2 minutes for next poll):
   ```bash
   cd ~/Projects/dumpster-fire
   tail -f logs/discord_monitor.log
   ```

   Should see:
   ```
   ✓ Captured: Test signal: SPY at $500
   ```

4. **Check raw journal**:
   ```bash
   cat journal/discord_raw.jsonl
   ```

---

## Troubleshooting

### No Notifications Appearing?

**Check Discord Focus Assist:**
- Discord Settings → Notifications → Do Not Disturb
- Make sure it's OFF

**Check macOS Focus:**
- Menu bar → Control Center → Focus
- Make sure Focus is OFF or allows Discord

**Check Channel Mute:**
- Right-click channel in Discord
- Make sure "Mute Channel" is NOT enabled

### Notifications Appear But Not Captured?

**Check Notification Database Path:**
```bash
find ~/Library -name "db" -path "*NotificationCenter*" 2>/dev/null
```

If path is different, update `discord_monitor.py` line 27:
```python
NOTIF_DB = Path.home() / "Library" / "Application Support" / "NotificationCenter" / "ACTUAL_PATH" / "db"
```

**Check Monitor Logs:**
```bash
tail -50 logs/discord_monitor.log
```

**Restart Monitor:**
```bash
./discord_control.sh restart
```

---

## Expected Behavior

**After setup**:
1. New Discord message arrives
2. macOS shows notification banner
3. Monitor checks database every 2 minutes
4. Finds new notification
5. Saves to `journal/discord_raw.jsonl`
6. Extractor processes it
7. Creates signal in `journal/discord_signals.json`
8. Agent uses it for scoring (+26 pts max)

**Timeline**:
- Message posted: 10:00:00 AM
- Notification appears: 10:00:01 AM (instant)
- Monitor checks: 10:02:00 AM (next 2-min cycle)
- Signal extracted: 10:02:05 AM (immediately after)
- Available to agent: 10:02:05 AM

**Delay**: ~2 minutes from message to signal availability

---

## Verify It's Working

**Watch in real-time:**
```bash
# Terminal 1: Watch monitor
tail -f logs/discord_monitor.log

# Terminal 2: Watch extractor
tail -f logs/discord_extractor.log

# Terminal 3: Watch signals file
watch -n 5 'cat journal/discord_signals.json'
```

**Send test message** → Should see it flow through all 3 terminals

---

## Privacy Notes

**What the monitor reads:**
- Only notifications that appear on YOUR Mac
- Only Discord channels you have access to
- Only messages that trigger notifications

**What it does NOT do:**
- ❌ Does NOT access Discord API
- ❌ Does NOT read chat history
- ❌ Does NOT send data anywhere
- ❌ Does NOT need Input Monitoring
- ❌ Does NOT monitor your keyboard/mouse

**This is exactly what the server admin approved** - reading only your own device notifications.

---

## Next Steps

1. ✅ Configure Discord app notifications
2. ✅ Configure macOS notifications
3. ✅ Send test message
4. ✅ Verify capture in logs
5. ✅ Start trading with automated signals!

Once configured, signals will flow automatically from Discord → Agent with no manual intervention.
