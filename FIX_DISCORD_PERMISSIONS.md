# Fix Discord Monitoring Service Permissions

## The Problem

**Status**: Exit code 512 = "Operation not permitted"

The Discord monitoring services (LaunchAgents) cannot access files in `~/Documents/` due to macOS privacy restrictions.

**Key Point**: You gave **cron** Full Disk Access, but these are **LaunchAgents** (not cron), which run in a different security context.

```
✗ LaunchAgent → Python → Documents folder = BLOCKED
✓ Terminal → Python → Documents folder = ALLOWED
✓ Cron → Python → Documents folder = ALLOWED (you already fixed this)
```

---

## Solution Options

### Option 1: Grant Python Full Disk Access (RECOMMENDED)

Grant the Python binary permission to access protected folders:

**Steps**:
1. Open **System Settings** → **Privacy & Security**
2. Click **Full Disk Access** (in left sidebar)
3. Click the **+** button at the bottom
4. Press **Cmd + Shift + G** and paste:
   ```
   /Library/Developer/CommandLineTools/usr/bin/python3
   ```
5. Click **Open** to add it
6. Enable the checkbox next to Python3
7. Restart the services:
   ```bash
   ./discord_control.sh restart
   ```

**Verification**:
```bash
./discord_control.sh status
# Should show: "✓ Monitor Process: RUNNING"
```

---

### Option 2: Use Cron Instead of LaunchAgents (EASIER)

Since you already gave cron Full Disk Access, just use cron instead:

**Steps**:
1. Stop and remove LaunchAgents:
   ```bash
   ./discord_control.sh stop
   rm ~/Library/LaunchAgents/com.trading.discord.*.plist
   ```

2. Add to crontab:
   ```bash
   crontab -e
   ```

3. Add these lines (runs every 2 minutes):
   ```cron
   # Discord signal monitoring (every 2 minutes)
   */2 * * * * cd /Users/rhingar/Documents/trainings/dumpster-fire && /usr/bin/python3 discord_monitor.py --once >> logs/discord_monitor.log 2>&1
   */2 * * * * cd /Users/rhingar/Documents/trainings/dumpster-fire && /usr/bin/python3 discord_signal_extractor.py >> logs/discord_extractor.log 2>&1
   ```

4. Verify cron is running:
   ```bash
   crontab -l  # List cron jobs
   tail -f logs/discord_monitor.log  # Watch logs
   ```

**Pros**: Works immediately (you already have cron access)
**Cons**: No auto-restart if script crashes

---

### Option 3: Move Project Out of Documents Folder

The Documents folder has special protection. Moving to a regular folder avoids the issue entirely.

**Steps**:
1. Move the project:
   ```bash
   mkdir -p ~/Projects
   mv ~/Documents/trainings/dumpster-fire ~/Projects/dumpster-fire
   cd ~/Projects/dumpster-fire
   ```

2. Update LaunchAgent plists:
   ```bash
   ./discord_control.sh stop
   # Edit discord_control.sh to change SCRIPT_DIR
   ./discord_control.sh install
   ./discord_control.sh start
   ```

**Pros**: Cleaner long-term solution
**Cons**: Need to update paths

---

### Option 4: Manual Capture (TESTING ONLY)

Run manually when you need to capture signals:

```bash
# Capture and extract (run whenever you want to check Discord)
python3 discord_monitor.py --once && python3 discord_signal_extractor.py
```

**Pros**: No permission issues, works immediately
**Cons**: Not automated

---

## Recommendation

**For immediate testing**: Use **Option 4** (manual capture)

**For production**: Use **Option 2** (cron) since you already have cron permissions set up

**For best setup**: Use **Option 1** (Full Disk Access for Python)

---

## Test After Fix

After applying any fix, test with:

```bash
# Check service status
./discord_control.sh status

# Should show:
# ✓ Monitor: LOADED
# ✓ Monitor Process: RUNNING (PID: XXXX)
# ✓ Extractor: LOADED

# Watch logs in real-time
tail -f logs/discord_monitor.log

# Manual test (should work immediately)
python3 discord_monitor.py --once
python3 discord_signal_extractor.py
python3 discord_integration.py
```

---

## Why Cron vs LaunchAgents?

| Feature | Cron | LaunchAgent |
|---------|------|-------------|
| **Permission context** | Terminal-like | Restricted system context |
| **Your current setup** | ✅ Has Full Disk Access | ❌ Needs permission |
| **Auto-restart** | ❌ No | ✅ Yes (KeepAlive) |
| **Ease of setup** | ✅ Simple | ⚠️ Need permissions |
| **Best for** | Scheduled tasks | Background services |

Since you're running every 2 minutes (like cron), using actual cron makes sense and avoids permission issues.

---

## Cron Setup Script (Quick Copy-Paste)

If you choose Option 2 (cron), here's the complete setup:

```bash
# 1. Stop LaunchAgents
./discord_control.sh stop
rm ~/Library/LaunchAgents/com.trading.discord.*.plist

# 2. Add to crontab (opens editor)
crontab -e

# 3. Paste these lines into the editor:
# Discord signal monitoring (every 2 minutes)
*/2 * * * * cd /Users/rhingar/Documents/trainings/dumpster-fire && /usr/bin/python3 discord_monitor.py --once >> logs/discord_monitor.log 2>&1
*/2 * * * * cd /Users/rhingar/Documents/trainings/dumpster-fire && /usr/bin/python3 discord_signal_extractor.py >> logs/discord_extractor.log 2>&1

# 4. Save and exit (:wq in vim)

# 5. Verify
crontab -l
tail -f logs/discord_monitor.log
```

Wait 2 minutes, and you should see activity in the logs!
