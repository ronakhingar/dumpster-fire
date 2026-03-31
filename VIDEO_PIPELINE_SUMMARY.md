# Video Processing Pipeline - Summary

## Overview

You have a **fully automated video processing pipeline** that:
1. **Extracts audio transcripts** from Mastermind trading videos
2. **Extracts frames** from videos (every 30 seconds + scene changes + when speaker mentions charts)
3. **Uses Gemini AI** to analyze transcripts and extract trade setups + insights
4. **Stores everything in PostgreSQL** for analysis

---

## Current Status

### ✅ **What's Already Done:**

**Videos Processed:** 12 Mastermind recordings from `tt/` directory
- Categories: psychology, TA (Technical Analysis), trading
- Format: Zoom recordings (.m4a audio + .mp4 video + .cc.vtt captions + chat logs)

**Frames Extracted:** 2,918 frames total
- Strategy 1: Scene change detection (visual transitions = chart switches)
- Strategy 2: Transcript cues (when speaker says "look at this chart", "notice how", etc.)
- Strategy 3: Baseline every 30 seconds (ensures no gaps)
- Stored in: `data/frames/1/` through `data/frames/12/`

**Example frame naming:**
```
frame_000000.0s.jpg   ← Start of video
frame_000030.0s.jpg   ← 30 second mark
frame_000065.4s.jpg   ← Scene change detected
frame_000133.7s.jpg   ← Transcript cue ("look at this chart")
```

---

## Pipeline Stages

### **Stage 1: Discover** ✅ COMPLETE
```bash
python3 pipeline.py discover
```
- Scans `tt/` directory for `.m4a` audio files
- Registers in `media_sources` table
- Found 12 sources

### **Stage 2: Transcribe** ✅ COMPLETE
```bash
python3 pipeline.py transcribe [--model medium]
```
- Uses Whisper AI OR parses `.cc.vtt` caption files
- Creates timestamped transcript segments
- Stored in `transcripts` table
- Models: tiny/base/small/medium/large

### **Stage 3: Extract Frames** ✅ COMPLETE
```bash
python3 pipeline.py frames
```
- Extracts frames using 3 strategies:
  1. **Scene changes** - FFmpeg detects visual transitions
  2. **Transcript cues** - When speaker references charts
  3. **Baseline** - Every 30 seconds
- Deduplicates within 3-second window
- Stored in `data/frames/{source_id}/` + `frames` table

### **Stage 4: Parse Chats** ✅ COMPLETE
```bash
python3 pipeline.py chats
```
- Parses Zoom `newChat.txt` files
- Stores in `session_chats` table
- Captures questions/discussions during sessions

### **Stage 5: Analyze Transcripts** ⚠️ NEEDS DATABASE
```bash
python3 pipeline.py analyze
```
- **Uses Gemini AI** to extract:
  - **Trades:** Symbol, direction, setup_type, entry/exit criteria, result
  - **Insights:** Trading rules, principles, psychology tips
- Processes 200 segments per batch (6 second delays for rate limiting)
- Stores in `video_trades` and `video_insights` tables

---

## Database Schema

**PostgreSQL Tables:**

### Video Pipeline Tables
- `media_sources` - Video/audio file registry
- `transcripts` - Timestamped speech segments
- `frames` - Extracted frame metadata + file paths
- `session_chats` - Zoom chat messages
- `video_trades` - Extracted trade setups from videos
- `video_insights` - Trading rules/principles learned

### Discord Pipeline Tables
- `discord_messages` - Discord signal messages
- `discord_trades` - Parsed Discord trade signals

### Shared
- `pipeline_state` - Resumable progress tracking per stage

---

## What You Were Building

### **The Process:**

1. **Fetch Videos** ✅
   - Already have 12 Mastermind videos in `tt/` directory
   - Psychology, TA, and trading categories

2. **Audio Transcripts** ✅
   - Whisper AI transcription complete
   - Timestamped segments stored

3. **Image Analysis Every 30 Seconds** ✅
   - 2,918 frames extracted using smart detection:
     - Scene changes = likely new chart
     - Transcript cues = "look at this chart"
     - Baseline 30s intervals = complete coverage

4. **Using Chart Data For Something** ⚠️ PARTIALLY COMPLETE
   - **Goal:** Extract trade setups shown in videos
   - **Method:** Gemini AI analyzes transcripts to find:
     - What trades were discussed/demonstrated
     - Entry/exit criteria
     - Setup types (2022_model, IFVG, unicorn, etc.)
     - Trading rules and principles
   - **Status:** Needs database running to complete analysis

---

## What's Missing to Complete

### 1. **Database Not Running**
```bash
# Error when running pipeline:
KeyError: 'DATABASE_URL'
```

**Fix:**
- Start PostgreSQL container (Docker Compose)
- Add `DATABASE_URL` to `.env` file
- Run: `python3 pipeline.py analyze`

### 2. **Gemini Analysis Incomplete**
The frames are extracted but **Gemini hasn't analyzed transcripts yet** to:
- Extract trade setups from speech
- Identify which frames show which setups
- Store insights about trading rules mentioned

---

## How to Resume

### **Step 1: Start Database**
```bash
docker-compose up -d postgres
```

### **Step 2: Add to .env**
```bash
# Add to .env file:
DATABASE_URL=postgresql://trading_agent:tr4d1ng_s3cur3_2026@localhost:25433/trading
GEMINI_API_KEY=your_gemini_api_key_here
```

### **Step 3: Check Pipeline Status**
```bash
python3 pipeline.py status
```

Should show:
- 12 sources discovered ✓
- Transcripts complete ✓
- Frames extracted ✓
- Chats parsed ✓
- **Analysis: pending/in_progress**

### **Step 4: Run Analysis**
```bash
# Run Gemini analysis on all transcripts
python3 pipeline.py analyze
```

**This will:**
- Send transcript batches to Gemini API
- Extract trade setups and insights
- Store in `video_trades` and `video_insights` tables
- Takes ~6 seconds per batch (rate limiting)
- **Resumable** - can stop and restart anytime

### **Step 5: Automated Daily Processing**
```bash
# Already configured in run_pipeline.sh
# Add to cron for daily analysis:
0 17 * * * /Users/rhingar/Projects/dumpster-fire/run_pipeline.sh
```

Runs daily at 5 PM (when Gemini free tier quota resets), auto-removes when done.

---

## What This Enables

Once analysis is complete, you'll have:

### **Video Trade Database**
Query all trade setups demonstrated in Mastermind videos:
```sql
SELECT setup_type, symbol, direction, notes
FROM video_trades
WHERE setup_type = '2022_model';
```

### **Trading Rules Learned**
```sql
SELECT category, description, evidence, confidence
FROM video_insights
WHERE category = 'entry_timing'
ORDER BY confidence DESC;
```

### **Frame→Trade Correlation**
Link extracted frames to specific trade discussions:
```sql
SELECT f.file_path, vt.symbol, vt.setup_type, vt.notes
FROM frames f
JOIN video_trades vt ON f.source_id = vt.source_id
WHERE f.is_chart = true
  AND ABS(f.timestamp_sec - vt.video_time) < 10;
```

### **Combined Knowledge Base**
- **Discord signals** (real-time from channels)
- **Video demonstrations** (Mastermind recordings)
- **Trading insights** (rules extracted from both)

→ Feed all of this into your **trading agent** for better decision-making!

---

## Files Involved

### Core Pipeline
- `pipeline.py` - Main processing script (5 stages)
- `run_pipeline.sh` - Automated daily runner (cron-ready)
- `db/init.sql` - Database schema
- `tt/` - Source video directory

### Outputs
- `data/frames/` - Extracted frame images (2,918 files)
- Database tables - All extracted data

### Logs
- `journal/pipeline_cron.log` - Daily run logs
- `journal/pipeline.pid` - Prevents duplicate runs

---

## Summary

You built a **complete video processing pipeline** that:

✅ **Discovers** videos from Mastermind recordings
✅ **Transcribes** audio using Whisper AI
✅ **Extracts frames** smartly (scene changes + cues + baseline 30s)
✅ **Parses chats** from Zoom sessions
⚠️ **Analyzes transcripts** with Gemini (needs database to finish)

**Next Step:** Start database and run `python3 pipeline.py analyze` to complete the Gemini extraction of trade setups and insights from the 12 videos.

**End Goal:** Build a comprehensive trading knowledge base combining:
- Real-time Discord signals
- Historical Mastermind video demonstrations
- Extracted trading rules and principles

→ All feeding into your autonomous trading agent!
