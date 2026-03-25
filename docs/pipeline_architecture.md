# Data Pipeline Architecture — Decision Record

Created: 2026-03-24
Status: Approved, pending Discord bot approval + Gemini API key

## Overview

Two data sources feed into the trading agent's knowledge base:
1. **Discord trading channel** — moderator trade calls with chart screenshots (since 2021)
2. **Training videos** — Mastermind sessions covering trading, TA, and psychology

Both are processed through batch pipelines into Postgres, with results either:
- Loaded into agent memory at startup (materialized views, cached stats)
- Baked into `memories.py` (distilled trading rules from video insights)

## Scale

| Source                    | Volume           | Growth         |
|---------------------------|------------------|----------------|
| Discord messages          | ~54,000          | ~10/day        |
| Discord chart screenshots | ~18,000          | ~5/day         |
| Training videos           | ~300 (est.)      | Periodic batch |
| Video transcripts         | ~300 hrs         | Tied to videos |
| Targeted chart frames     | ~5,000           | Tied to videos |

## Architecture Decisions

### Why Postgres over MongoDB
- Relational queries (JOINs, GROUP BY) are core to our analytics (win rates,
  trader credibility, setup patterns)
- Materialized views for pre-computed agent runtime data
- 54k rows is trivial for Postgres — no need for a document store
- SQL is more natural for aggregation-heavy workloads
- Single Docker container, zero operational complexity

### Why Postgres over SQLite
- Agent needs remote-queryable data (live polling writes + agent reads)
- Future: dashboard, additional data sources, multi-process access
- Materialized views (SQLite doesn't have them)
- Better concurrent write handling during batch + live polling overlap

### Why NOT a heavy orchestrator (Airflow/Prefect/Luigi)
- Only ~300 videos and ~54k messages — not big data
- Simple DAG: discover → transcribe → extract → parse → compile
- Python + concurrent.futures + pipeline_state table gives us:
  - Parallelism (ProcessPoolExecutor)
  - Resumability (pipeline_state tracks progress per source)
  - Crash recovery (commit after each chunk)
- Adding Airflow would mean another Docker container, web UI, scheduler,
  and DAG definitions for a pipeline that runs a handful of times

### Why Gemini 2.0 Flash over OpenAI for batch processing
- **Cost: $0** using the API free tier (1,500 RPD)
- 1M token context window allows aggressive batching:
  - 200 Discord messages per request (vs 20 on OpenAI)
  - 10 chart images per request
  - Reduces total API calls from ~28,700 to ~2,870
- Image tokenization: ~258 tokens/image vs OpenAI's ~2,125 (8x cheaper)
- Free tier is separate from the Gemini Pro subscription
- Requires a Gemini API key from Google AI Studio (free)

### Why local Whisper over Whisper API
- **Cost: $0** vs $108 for API
- Apple Silicon MPS acceleration: ~5x faster than CPU
- .m4a audio files are lighter than video (no need to decode video frames)
- Existing .cc.vtt caption files skip transcription entirely
- Parallelism at file level (4 workers = 4 separate files simultaneously)
- Each worker processes one complete file start-to-finish — no chunk
  interleaving, no transcript ordering issues

### Why frames stored on filesystem, not Postgres
- 36,000 frames × ~50KB each = ~1.8GB — bloats the DB
- Postgres stores path + metadata only
- Frames are only accessed during batch analysis, not agent runtime
- Easy to back up, move, or delete independently of the DB

### Why materialized views for agent runtime
- Agent scans every 2 minutes — queries must be sub-millisecond
- Raw table scans on 54k+ rows are fast but unnecessary overhead per cycle
- Materialized views pre-compute:
  - trader_stats: per-trader win rate, total trades, credibility
  - setup_win_rates: historical win rate by setup type + symbol
- Refreshed daily (data changes slowly — ~10 new messages/day)
- Agent loads these into memory at startup, not per-cycle

### Why a "hot signals" approach for live Discord
- Agent doesn't need to query all 54k historical messages every 2 min
- Only recent signals matter (last 30 min of trade calls)
- discord_live_signals table holds ~50-100 rows max (pruned every 4 hours)
- Single indexed query: symbol + timestamp DESC

## Cost Analysis

### One-time backfill: $0

| Component                      | Tool                        | Cost |
|--------------------------------|-----------------------------|------|
| Video transcription (300 hrs)  | Whisper local (MPS, 4x)    | $0   |
| Frame extraction (36k frames)  | FFmpeg local                | $0   |
| Discord text parsing (54k)     | Gemini 2.0 Flash free tier  | $0   |
| Discord chart analysis (18k)   | Gemini 2.0 Flash free tier  | $0   |
| Video transcript analysis      | Gemini 2.0 Flash free tier  | $0   |
| Video frame analysis (5k)      | Gemini 2.0 Flash free tier  | $0   |
| Postgres                       | Docker local                | $0   |
| **Total**                      |                             | **$0** |

### Ongoing monthly: ~$0.09

| Component                      | Tool                        | Monthly |
|--------------------------------|-----------------------------|---------|
| Discord live polling (~10/day) | Gemini 2.0 Flash free tier  | $0      |
| Chart analysis (~5 images/day) | Gemini 2.0 Flash free tier  | $0      |
| Materialized view refresh      | Postgres (local)            | $0      |
| Agent runtime (deterministic)  | No LLM                      | $0      |

### Alternative cost comparison

| Approach                            | Cost    | Time     |
|-------------------------------------|---------|----------|
| **Gemini free + local Whisper**     | **$0**  | 5 nights |
| Gemini paid + local Whisper         | ~$4.50  | 1 night  |
| OpenAI Batch API + local Whisper    | ~$10.33 | 1 night  |
| OpenAI Batch API + Whisper API      | ~$118   | 1 night  |

## Batch Schedule (9pm - 4am PST)

| Night | Task                         | Details                                    |
|-------|------------------------------|--------------------------------------------|
| 1-3   | Whisper transcription        | ~100 videos/night, 4 parallel workers      |
| 1     | Discord text backfill        | 270 Gemini calls (~20 min)                 |
| 2-3   | Discord chart analysis       | 1,800 Gemini calls across 2 nights         |
| 4     | Video transcript parsing     | 300 Gemini calls (~25 min)                 |
| 5     | Video frame analysis         | 500 targeted Gemini calls (~35 min)        |
| 5     | Compile insights → memories  | Final synthesis into memories.py            |

Whisper runs in parallel with Gemini calls (separate processes).

## Postgres Schema

### Raw tables (batch pipeline writes)
- `media_sources` — registered video/audio files + processing status
- `transcripts` — timestamped transcript segments (from Whisper or .vtt)
- `frames` — extracted frame metadata (file path on disk, not binary)
- `session_chats` — Zoom chat messages from newChat.txt files
- `video_trades` — trade setups extracted from video content
- `video_insights` — rules/patterns extracted from sessions
- `discord_messages` — raw Discord messages
- `discord_trades` — parsed trade signals from Discord
- `pipeline_state` — resumable processing progress per source + stage

### Agent-facing (pre-computed, read-only at runtime)
- `trader_stats` (materialized view) — per-trader win rate, credibility
- `setup_win_rates` (materialized view) — win rate by setup type + symbol
- `discord_live_signals` — rolling window of recent trade calls (~4hr TTL)

### Indexes (only on agent-queried tables)
- `discord_messages(timestamp DESC)` — live polling cursor
- `discord_trades(author_name, result)` — materialized view refresh
- `discord_live_signals(symbol, created_at DESC)` — 2-min cycle query
- `trader_stats(author_name)` — startup cache load
- `setup_win_rates(setup_type, symbol)` — startup cache load

## Data Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│ Discord JSON │     │ .m4a / .mp4  │     │ .vtt / .txt      │
│ (export)     │     │ (videos)     │     │ (existing capts)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────────┘
       │                    │                    │
       ▼                    ▼                    ▼
  ┌─────────┐     ┌──────────────┐     ┌──────────────┐
  │ Gemini  │     │ Whisper      │     │ Direct parse │
  │ Flash   │     │ (local MPS)  │     │ (VTT → text) │
  └────┬────┘     └──────┬───────┘     └──────┬───────┘
       │                 │                    │
       ▼                 ▼                    ▼
  ┌──────────────────────────────────────────────┐
  │              POSTGRES                         │
  │  ┌────────────┐  ┌────────────┐              │
  │  │ Raw tables │→ │ Mat. views │ ← refreshed  │
  │  └────────────┘  └─────┬──────┘    daily     │
  └─────────────────────────┼────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   agent.py      │
                   │   (2-min loop)  │
                   │                 │
                   │ • loads stats   │
                   │   at startup    │
                   │ • queries live  │
                   │   signals only  │
                   │ • rules baked   │
                   │   into memory   │
                   └─────────────────┘
```

## Prerequisites (before building)

1. [ ] Discord bot approved by server admin
2. [ ] Gemini API key from Google AI Studio
3. [ ] `brew install ffmpeg`
4. [ ] Postgres connection details confirmed
5. [ ] Discord channel exported as JSON (DiscordChatExporter)
