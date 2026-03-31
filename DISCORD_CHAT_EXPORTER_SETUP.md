# Discord Chat Exporter Setup

**Tool**: https://github.com/Tyrrrz/DiscordChatExporter
**Best option for exporting Discord history**

---

## Installation (macOS)

### Option 1: Download Pre-built Binary (EASIEST)

1. **Download latest release**:
   https://github.com/Tyrrrz/DiscordChatExporter/releases/latest

2. **Download**: `DiscordChatExporter.Cli.osx-x64.zip`

3. **Extract** the zip file

4. **Move to your project**:
   ```bash
   mv ~/Downloads/DiscordChatExporter.Cli /Users/rhingar/Projects/dumpster-fire/
   chmod +x DiscordChatExporter.Cli
   ```

### Option 2: Via Homebrew

```bash
# Install .NET runtime (required)
brew install --cask dotnet

# Clone and build
git clone https://github.com/Tyrrrz/DiscordChatExporter.git
cd DiscordChatExporter
dotnet build
```

---

## Get Your Discord Token (Same as Before)

### Console Method (Easiest):

1. Open Discord app
2. Press: `Cmd + Option + I`
3. Go to **Console** tab
4. Paste this code:
   ```javascript
   (webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
   ```
5. Copy the token that appears

---

## Export Your Channels

You already have the channel IDs in `discord_config.json`:
- stock-alerts: `545047039084593163`
- day-trade-alerts: `981926799212679248`
- swings: `661023267439509536`

### Export Command:

```bash
cd ~/Projects/dumpster-fire

# Export stock-alerts channel
./DiscordChatExporter.Cli export \
  --token "YOUR_TOKEN_HERE" \
  --channel 545047039084593163 \
  --format Json \
  --output discord_history/stock-alerts.json

# Export day-trade-alerts channel
./DiscordChatExporter.Cli export \
  --token "YOUR_TOKEN_HERE" \
  --channel 981926799212679248 \
  --format Json \
  --output discord_history/day-trade-alerts.json

# Export swings channel
./DiscordChatExporter.Cli export \
  --token "YOUR_TOKEN_HERE" \
  --channel 661023267439509536 \
  --format Json \
  --output discord_history/swings.json
```

### Or Export All at Once:

```bash
./DiscordChatExporter.Cli export \
  --token "YOUR_TOKEN_HERE" \
  --channel 545047039084593163 \
  --channel 981926799212679248 \
  --channel 661023267439509536 \
  --format Json \
  --output discord_history/
```

---

## Export Options

**Format options**:
- `Json` - Machine-readable (best for our use)
- `HtmlDark` - Human-readable, dark theme
- `HtmlLight` - Human-readable, light theme
- `PlainText` - Simple text
- `Csv` - Spreadsheet

**Date range** (optional):
```bash
--after "2024-01-01"   # Only messages after this date
--before "2024-03-30"  # Only messages before this date
```

**Message limit** (optional):
```bash
--limit 1000  # Only fetch 1000 messages
```

---

## Example: Export Last 3 Months

```bash
./DiscordChatExporter.Cli export \
  --token "YOUR_TOKEN_HERE" \
  --channel 545047039084593163 \
  --channel 981926799212679248 \
  --channel 661023267439509536 \
  --format Json \
  --after "2024-01-01" \
  --output discord_history/
```

---

## What You Get

Each channel exported as JSON with:
- Message content
- Timestamps
- Author information
- Attachments (images, charts)
- All metadata

Example structure:
```json
{
  "guild": { "name": "Trading Server" },
  "channel": { "name": "stock-alerts" },
  "messages": [
    {
      "id": "123456",
      "timestamp": "2024-03-26T15:00:00+00:00",
      "content": "SPY bearish at $520 resistance",
      "author": { "name": "Admin" }
    }
  ]
}
```

---

## Convert to Signal Format

After exporting, I'll create a converter script:

```bash
# Convert exported JSON to signal format
python3 convert_chat_export.py discord_history/stock-alerts.json

# Imports to history
cat discord_history/*_converted.jsonl >> journal/discord_signals_history.jsonl
```

---

## Advantages Over Other Methods

✅ **GUI available** (also has CLI version)
✅ **Well-maintained** (17k+ stars on GitHub)
✅ **Trusted** by Discord community
✅ **Exports everything** (attachments, embeds, etc.)
✅ **Date range filtering** (only get what you need)
✅ **Multiple formats** (JSON, HTML, CSV)
✅ **No programming** required

---

## Privacy & Safety

**Is this allowed?**
- ✅ Uses your personal token (not a bot)
- ✅ Only exports what YOU can see
- ✅ Widely used tool (17k+ stars)
- ✅ No server-side access needed

**Your Discord server admin cannot:**
- ❌ Stop you from using this
- ❌ Detect you're using it
- ❌ See what you export

You're just downloading YOUR OWN accessible data faster than manual copy-paste.

---

## Next Steps

1. ✅ Download DiscordChatExporter
2. ✅ Get your Discord token (Console method)
3. ✅ Run export command with your 3 channel IDs
4. ✅ I'll help convert to signal format
5. ✅ Import to backtest history
6. ✅ Run backtests with historical signals!

This is the BEST method - much easier than JavaScript in DevTools!
