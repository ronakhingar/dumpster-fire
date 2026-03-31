# Get Discord Token - Alternative Methods

Cmd+Option+I not working? Try these:

---

## Method 1: Enable Developer Mode First

1. **Open Discord app**
2. Click your profile icon (bottom left)
3. **User Settings** (�gear icon)
4. Scroll down → **Advanced**
5. Enable **"Developer Mode"** toggle
6. Close settings
7. Now try: **Cmd + Shift + I** (different shortcut)

---

## Method 2: Menu Bar Method

1. **Discord app open**
2. Click **"View"** in the menu bar (top of screen)
3. Look for **"Toggle Developer Tools"** or **"Developer"**
4. Click it to open DevTools

If you don't see View menu:
- Make sure Discord window is focused (click on it)
- Try right-clicking anywhere in Discord → "Inspect Element"

---

## Method 3: Alternative Keyboard Shortcuts

Try these (one might work):
- `Cmd + Option + I`
- `Cmd + Shift + I`
- `Ctrl + Shift + I`
- `F12`

---

## Method 4: Discord Settings File (NO DEVTOOLS NEEDED!)

**Easier method - extract token from Discord's config file:**

```bash
# Find Discord's token in local storage
cd ~/Library/Application\ Support/discord/Local\ Storage/leveldb

# Search for token
strings *.ldb | grep -E 'mfa\.[a-zA-Z0-9_-]{84}' | head -1
```

Or:

```bash
# More specific search
grep -r "token" ~/Library/Application\ Support/discord/ 2>/dev/null | grep -oE 'mfa\.[a-zA-Z0-9_-]{84}'
```

**This finds your token without opening DevTools!**

---

## Method 5: Discord Token Grabber Script

I can create a simple script that extracts your token:

```bash
python3 get_discord_token.py
```

---

## Which Method to Try?

**Easiest**: Method 4 (search config files)
**Most reliable**: Method 1 (enable developer mode first)
**No keyboard needed**: Method 2 (menu bar)

---

## Still Not Working?

Alternative: **Use DiscordChatExporter GUI version instead of CLI**

The GUI version has a built-in token getter!

1. Download: `DiscordChatExporter.zip` (not CLI version)
2. Run the app
3. Click "Get Token" button
4. It extracts token automatically

Download GUI version:
https://github.com/Tyrrrz/DiscordChatExporter/releases/latest
(Look for just "DiscordChatExporter.zip" without "Cli")

---

## Test if DevTools Opened

If you're not sure if DevTools opened, you should see:
- A new panel/window appear
- Tabs like: Console, Network, Elements, Sources
- Looks like web developer tools

---

## Next Steps

1. Try Method 1 (Enable Developer Mode) OR Method 4 (search files)
2. Get your token
3. Run DiscordChatExporter export command
4. I'll help convert to signals

Let me know which method works for you!
