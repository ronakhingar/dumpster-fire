#!/usr/bin/env python3
"""
Video/audio processing pipeline.

Stages (each is resumable via pipeline_state table):
  1. discover   — scan tt/ and register sources in media_sources
  2. transcribe — Whisper on .m4a (or parse .cc.vtt where available)
  3. frames     — FFmpeg: scene detection + transcript cues + baseline
  4. chats      — parse Zoom newChat.txt into session_chats
  5. analyze    — Gemini extracts trades + insights from transcripts

Usage:
  python3 pipeline.py                  # run full pipeline
  python3 pipeline.py discover         # run from specific stage
  python3 pipeline.py analyze          # run analysis + remaining
  python3 pipeline.py --model medium   # use larger Whisper model
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]
TT_DIR = Path(__file__).parent / "tt"
FRAMES_DIR = Path(__file__).parent / "data" / "frames"
WHISPER_MODEL = "small"


# ─── Database helpers ─────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DB_URL)


def upsert_pipeline_state(conn, source_type, source_ref, stage, status,
                          last_offset=0, error=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_state (source_type, source_ref, stage, status,
                                        last_offset, error, started_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (source_type, source_ref, stage)
            DO UPDATE SET status = EXCLUDED.status,
                          last_offset = EXCLUDED.last_offset,
                          error = EXCLUDED.error,
                          completed_at = CASE WHEN EXCLUDED.status IN ('completed','failed')
                                              THEN NOW() ELSE NULL END
        """, (source_type, source_ref, stage, status, last_offset, error))
    conn.commit()


def get_pipeline_state(conn, source_type, source_ref, stage):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM pipeline_state
            WHERE source_type = %s AND source_ref = %s AND stage = %s
        """, (source_type, source_ref, stage))
        return cur.fetchone()


# ─── Stage 1: Discover ───────────────────────────────────────────────────────

def parse_path_metadata(file_path):
    """Extract category/program/session from directory structure."""
    parts = Path(file_path).relative_to(TT_DIR).parts
    category = parts[0] if len(parts) > 0 else "unknown"
    program = parts[1] if len(parts) > 1 else None
    session = parts[2] if len(parts) > 2 else None
    return category, program, session


def discover():
    """Scan tt/ and register all .m4a audio sources in media_sources."""
    print("\n══ STAGE 1: DISCOVER ══════════════════════════════════════")
    conn = get_conn()

    audio_files = sorted(TT_DIR.rglob("*.m4a"))
    registered = 0
    skipped = 0

    for af in audio_files:
        file_path = str(af)
        category, program, session = parse_path_metadata(file_path)
        file_size = af.stat().st_size

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO media_sources (file_path, filename, category,
                                               program, session, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_path) DO NOTHING
                    RETURNING id
                """, (file_path, af.name, category, program, session, file_size))
                result = cur.fetchone()
            conn.commit()

            if result:
                registered += 1
                print(f"  + {category}/{program}/{session}/{af.name}")
            else:
                skipped += 1
        except Exception as e:
            conn.rollback()
            print(f"  ✗ Error registering {af.name}: {e}")

    print(f"\n  Registered: {registered}  Skipped (already exists): {skipped}")
    conn.close()


# ─── Stage 2: Transcribe ─────────────────────────────────────────────────────

def find_companion_file(m4a_path, extension):
    """Find a companion file (.cc.vtt, .mp4, newChat.txt) for an .m4a source."""
    base = Path(m4a_path).parent
    stem = Path(m4a_path).stem.replace(".m4a", "")
    # Strip the ".m4a" that might be in the stem
    stem = Path(m4a_path).stem

    for f in base.iterdir():
        if f.suffix == extension and f.stem.startswith(stem.split("_Recording")[0]):
            return str(f)
        if extension == ".txt" and f.name.endswith("newChat.txt"):
            if stem.split("_Recording")[0] in f.name:
                return str(f)
    return None


def parse_vtt(vtt_path):
    """Parse a WebVTT caption file into transcript segments."""
    segments = []
    with open(vtt_path, "r") as f:
        content = f.read()

    blocks = re.split(r"\n\n+", content.strip())
    idx = 0
    for block in blocks:
        lines = block.strip().split("\n")
        # Find the timestamp line
        ts_line = None
        text_lines = []
        for line in lines:
            if "-->" in line:
                ts_line = line
            elif ts_line and line.strip() and line.strip() != "WEBVTT":
                text_lines.append(line.strip())

        if ts_line and text_lines:
            match = re.match(
                r"(\d+:\d+:\d+\.\d+)\s*-->\s*(\d+:\d+:\d+\.\d+)", ts_line
            )
            if match:
                start = _ts_to_seconds(match.group(1))
                end = _ts_to_seconds(match.group(2))
                text = " ".join(text_lines)
                segments.append({
                    "idx": idx,
                    "start": start,
                    "end": end,
                    "text": text,
                    "confidence": 1.0,
                })
                idx += 1

    return segments


def _ts_to_seconds(ts):
    """Convert HH:MM:SS.mmm to seconds."""
    parts = ts.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def transcribe_with_whisper(m4a_path, model_name):
    """Run Whisper on an .m4a file and return transcript segments."""
    import whisper

    print(f"    Loading Whisper model '{model_name}'...")
    model = whisper.load_model(model_name)

    print(f"    Transcribing {Path(m4a_path).name}...")
    t0 = time.time()
    result = model.transcribe(m4a_path, verbose=False)
    elapsed = time.time() - t0
    print(f"    Done in {elapsed:.0f}s ({len(result['segments'])} segments)")

    segments = []
    for i, seg in enumerate(result["segments"]):
        segments.append({
            "idx": i,
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "confidence": round(seg.get("avg_logprob", 0) * -1, 3),
        })

    return segments


def store_transcript(conn, source_id, segments):
    """Insert transcript segments into the database."""
    with conn.cursor() as cur:
        for seg in segments:
            cur.execute("""
                INSERT INTO transcripts (source_id, segment_idx, start_sec,
                                         end_sec, text, confidence)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (source_id, seg["idx"], seg["start"], seg["end"],
                  seg["text"], seg["confidence"]))
    conn.commit()


def transcribe_all(model_name=None):
    """Transcribe all pending sources. Uses VTT where available, else Whisper."""
    print("\n══ STAGE 2: TRANSCRIBE ════════════════════════════════════")
    model = model_name or WHISPER_MODEL
    conn = get_conn()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, file_path, filename, category, program, session
            FROM media_sources
            WHERE status IN ('pending', 'transcribing')
            ORDER BY id
        """)
        sources = cur.fetchall()

    if not sources:
        print("  No pending sources to transcribe.")
        conn.close()
        return

    print(f"  Found {len(sources)} sources to transcribe\n")

    for src in sources:
        sid = src["id"]
        fpath = src["file_path"]
        ref = src["file_path"]

        state = get_pipeline_state(conn, "video", ref, "transcription")
        if state and state["status"] == "completed":
            print(f"  ⏭ Already transcribed: {src['filename']}")
            continue

        upsert_pipeline_state(conn, "video", ref, "transcription", "in_progress")

        with conn.cursor() as cur:
            cur.execute("UPDATE media_sources SET status = 'transcribing' WHERE id = %s", (sid,))
        conn.commit()

        try:
            vtt_path = find_companion_file(fpath, ".vtt")
            # Also check for .cc.vtt specifically
            if not vtt_path:
                base_dir = Path(fpath).parent
                for f in base_dir.iterdir():
                    if f.name.endswith(".cc.vtt"):
                        vtt_path = str(f)
                        break

            if vtt_path and os.path.exists(vtt_path):
                print(f"  📄 Parsing VTT: {Path(vtt_path).name}")
                segments = parse_vtt(vtt_path)
                print(f"     {len(segments)} segments from captions")
            else:
                print(f"  🎤 Whisper ({model}): {src['filename']}")
                segments = transcribe_with_whisper(fpath, model)

            store_transcript(conn, sid, segments)

            with conn.cursor() as cur:
                cur.execute("UPDATE media_sources SET status = 'transcribed' WHERE id = %s", (sid,))
            conn.commit()

            upsert_pipeline_state(conn, "video", ref, "transcription", "completed",
                                  last_offset=len(segments))
            print(f"  ✓ Stored {len(segments)} segments for source {sid}\n")

        except Exception as e:
            conn.rollback()
            upsert_pipeline_state(conn, "video", ref, "transcription", "failed",
                                  error=str(e))
            with conn.cursor() as cur:
                cur.execute("UPDATE media_sources SET status = 'pending' WHERE id = %s", (sid,))
            conn.commit()
            print(f"  ✗ Failed: {e}\n")

    conn.close()


# ─── Stage 3: Extract frames ─────────────────────────────────────────────────

CHART_CUE_PHRASES = re.compile(
    r"look at|as you can see|here'?s the|this chart|this setup|on the (\d+ ?min|"
    r"daily|weekly|monthly|hour)|order block|fair value gap|FVG|liquidity|"
    r"displacement|market structure|break of structure|change of character|"
    r"let me show|pay attention|notice how|right here|this level|"
    r"this candle|entry model|stop loss|target",
    re.IGNORECASE,
)


def _get_transcript_cue_timestamps(conn, source_id):
    """Find timestamps where the speaker references a chart or setup."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT start_sec, end_sec, text FROM transcripts
            WHERE source_id = %s ORDER BY segment_idx
        """, (source_id,))
        segments = cur.fetchall()

    cue_times = []
    for seg in segments:
        if CHART_CUE_PHRASES.search(seg["text"]):
            midpoint = (seg["start_sec"] + seg["end_sec"]) / 2
            cue_times.append(midpoint)

    return cue_times


def _extract_scene_changes(mp4_path, out_dir):
    """Use FFmpeg scene detection to find visual transitions."""
    scene_list = out_dir / "scenes.txt"
    cmd = [
        "ffmpeg", "-i", mp4_path,
        "-vf", "select='gt(scene,0.3)',showinfo",
        "-vsync", "vfr",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    timestamps = []
    for line in result.stderr.split("\n"):
        match = re.search(r"pts_time:(\d+\.?\d*)", line)
        if match:
            timestamps.append(float(match.group(1)))
    return timestamps


def _extract_frame_at(mp4_path, timestamp_sec, out_path):
    """Extract a single frame at an exact timestamp."""
    cmd = [
        "ffmpeg", "-ss", str(timestamp_sec),
        "-i", mp4_path,
        "-frames:v", "1",
        "-q:v", "3",
        "-y", str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    return Path(out_path).exists()


def _deduplicate_timestamps(timestamps, min_gap=3.0):
    """Remove timestamps within min_gap seconds of each other."""
    if not timestamps:
        return []
    timestamps = sorted(set(timestamps))
    deduped = [timestamps[0]]
    for ts in timestamps[1:]:
        if ts - deduped[-1] >= min_gap:
            deduped.append(ts)
    return deduped


def extract_frames_for_source(conn, source_id, mp4_path):
    """
    Smart frame extraction using three strategies combined:
      1. Scene change detection — catches visual transitions (chart switches)
      2. Transcript cues — frames when speaker says "look at this chart" etc.
      3. Baseline every 30s — ensures no long gaps without coverage
    All timestamps are deduplicated within a 3-second window.
    """
    out_dir = FRAMES_DIR / str(source_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"    Extracting frames from {Path(mp4_path).name}...")
    t0 = time.time()

    # Strategy 1: Scene changes
    print(f"      Detecting scene changes...")
    scene_ts = _extract_scene_changes(mp4_path, out_dir)
    print(f"      Found {len(scene_ts)} scene changes")

    # Strategy 2: Transcript cues
    cue_ts = _get_transcript_cue_timestamps(conn, source_id)
    print(f"      Found {len(cue_ts)} transcript cue points")

    # Strategy 3: Baseline every 30s (get video duration first)
    dur_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", mp4_path,
    ]
    dur_result = subprocess.run(dur_cmd, capture_output=True, text=True)
    duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0
    baseline_ts = [i * 30.0 for i in range(int(duration / 30) + 1)]

    # Merge and deduplicate
    all_ts = _deduplicate_timestamps(scene_ts + cue_ts + baseline_ts, min_gap=3.0)
    print(f"      Total unique timestamps after dedup: {len(all_ts)}")

    # Extract each frame
    extracted = 0
    for ts in all_ts:
        frame_name = f"frame_{ts:08.1f}s.jpg"
        out_path = out_dir / frame_name
        if _extract_frame_at(mp4_path, ts, out_path):
            is_cue = any(abs(ts - c) < 3 for c in cue_ts)
            is_scene = any(abs(ts - s) < 3 for s in scene_ts)
            rel_path = str(out_path.relative_to(Path(__file__).parent))
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO frames (source_id, timestamp_sec, file_path,
                                        is_chart, description)
                    VALUES (%s, %s, %s, %s, %s)
                """, (source_id, ts, rel_path,
                      is_cue or is_scene,
                      "scene_change" if is_scene else ("transcript_cue" if is_cue else "baseline")))
            extracted += 1
    conn.commit()

    elapsed = time.time() - t0
    print(f"    Extracted {extracted} frames in {elapsed:.0f}s "
          f"(scene:{len(scene_ts)} cue:{len(cue_ts)} baseline:{len(baseline_ts)})")

    return extracted


def extract_frames_all():
    """Extract frames for all transcribed sources that have .mp4 files."""
    print("\n══ STAGE 3: EXTRACT FRAMES ════════════════════════════════")
    conn = get_conn()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, file_path, filename FROM media_sources
            WHERE status IN ('transcribed', 'extracting')
            ORDER BY id
        """)
        sources = cur.fetchall()

    if not sources:
        print("  No transcribed sources ready for frame extraction.")
        conn.close()
        return

    for src in sources:
        sid = src["id"]
        ref = src["file_path"]

        state = get_pipeline_state(conn, "video", ref, "frame_extraction")
        if state and state["status"] == "completed":
            print(f"  ⏭ Frames already extracted: {src['filename']}")
            continue

        # Find the companion .mp4
        mp4_path = None
        base_dir = Path(src["file_path"]).parent
        for f in base_dir.iterdir():
            if f.suffix == ".mp4" and f.stat().st_size > 0:
                mp4_path = str(f)
                break

        if not mp4_path:
            print(f"  ⏭ No .mp4 found for: {src['filename']}")
            upsert_pipeline_state(conn, "video", ref, "frame_extraction",
                                  "completed", error="no_mp4_found")
            continue

        upsert_pipeline_state(conn, "video", ref, "frame_extraction", "in_progress")

        with conn.cursor() as cur:
            cur.execute("UPDATE media_sources SET status = 'extracting' WHERE id = %s", (sid,))
        conn.commit()

        try:
            count = extract_frames_for_source(conn, sid, mp4_path)
            with conn.cursor() as cur:
                cur.execute("UPDATE media_sources SET status = 'processed' WHERE id = %s", (sid,))
            conn.commit()
            upsert_pipeline_state(conn, "video", ref, "frame_extraction",
                                  "completed", last_offset=count)
            print(f"  ✓ {count} frames stored for source {sid}\n")
        except Exception as e:
            conn.rollback()
            upsert_pipeline_state(conn, "video", ref, "frame_extraction",
                                  "failed", error=str(e))
            with conn.cursor() as cur:
                cur.execute("UPDATE media_sources SET status = 'transcribed' WHERE id = %s", (sid,))
            conn.commit()
            print(f"  ✗ Failed: {e}\n")

    conn.close()


# ─── Stage 4: Parse chat logs ────────────────────────────────────────────────

def parse_chat_file(chat_path):
    """Parse a Zoom newChat.txt file. Format: HH:MM:SS\\tAuthor:\\tMessage"""
    messages = []
    current = None

    with open(chat_path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            match = re.match(r"^(\d{2}:\d{2}:\d{2})\t(.+?):\t(.*)$", line)
            if match:
                if current:
                    messages.append(current)
                current = {
                    "timestamp": match.group(1),
                    "author": match.group(2),
                    "message": match.group(3),
                }
            elif current and line.strip():
                current["message"] += "\n" + line.strip()

    if current:
        messages.append(current)

    return messages


def parse_chats():
    """Parse all chat logs for registered sources."""
    print("\n══ STAGE 4: PARSE CHAT LOGS ═══════════════════════════════")
    conn = get_conn()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, file_path, filename FROM media_sources ORDER BY id")
        sources = cur.fetchall()

    parsed_count = 0
    for src in sources:
        ref = src["file_path"]
        state = get_pipeline_state(conn, "video", ref, "chat_parse")
        if state and state["status"] == "completed":
            continue

        chat_path = None
        base_dir = Path(src["file_path"]).parent
        for f in base_dir.iterdir():
            if f.name.endswith("newChat.txt"):
                chat_path = str(f)
                break

        if not chat_path:
            upsert_pipeline_state(conn, "video", ref, "chat_parse",
                                  "completed", error="no_chat_file")
            continue

        upsert_pipeline_state(conn, "video", ref, "chat_parse", "in_progress")

        try:
            messages = parse_chat_file(chat_path)
            with conn.cursor() as cur:
                for msg in messages:
                    cur.execute("""
                        INSERT INTO session_chats (source_id, author, message, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, (src["id"], msg["author"], msg["message"], msg["timestamp"]))
            conn.commit()
            upsert_pipeline_state(conn, "video", ref, "chat_parse",
                                  "completed", last_offset=len(messages))
            print(f"  ✓ {len(messages):>3} messages from {Path(chat_path).name}")
            parsed_count += len(messages)
        except Exception as e:
            conn.rollback()
            upsert_pipeline_state(conn, "video", ref, "chat_parse",
                                  "failed", error=str(e))
            print(f"  ✗ Failed: {e}")

    print(f"\n  Total chat messages parsed: {parsed_count}")
    conn.close()


# ─── Stage 5: Gemini transcript analysis ──────────────────────────────────────

GEMINI_BATCH_SIZE = 200  # segments per request (fits in 1M context)

def _build_analysis_prompt(session_label, start_time, end_time, transcript_text):
    return (
        "You are analyzing a trading education session transcript.\n\n"
        "Extract TWO types of information:\n\n"
        "1. TRADES — Any specific trade setups discussed, demonstrated, or reviewed:\n"
        '   Return as JSON array "trades" with fields:\n'
        '   - symbol (string or null): ticker if mentioned (e.g. "NQ", "ES", "SPY")\n'
        '   - direction ("long" / "short" / null)\n'
        '   - setup_type (string): the model/pattern name (e.g. "2022_model", "IFVG", '
        '"unicorn", "liquidity_sweep", "FVG_entry", "order_block", "SMT_divergence", '
        '"power_of_three")\n'
        "   - entry_criteria (object): what conditions must be met\n"
        "   - exit_criteria (object or null): stop loss / target logic\n"
        '   - result ("win" / "loss" / "breakeven" / null): if outcome was discussed\n'
        "   - notes (string): brief context of what was taught about this trade\n\n"
        "2. INSIGHTS — Trading rules, principles, or guidelines stated by the instructor:\n"
        '   Return as JSON array "insights" with fields:\n'
        '   - category: one of "setup_rule", "risk_management", "psychology", '
        '"market_structure", "entry_timing", "exit_strategy", "confluence"\n'
        "   - description (string): the rule/principle in clear language\n"
        "   - evidence (string): direct quote or paraphrase from the transcript\n"
        "   - confidence (float 0-1): how explicitly this was stated vs inferred\n"
        "   - tags (array of strings): relevant keywords\n\n"
        'Return ONLY valid JSON with keys "trades" and "insights". '
        'If nothing relevant, return empty arrays.\n\n'
        f"Transcript (session: {session_label}, timestamps {start_time} - {end_time}):\n\n"
        f"{transcript_text}\n"
    )


def _init_gemini():
    """Initialize Gemini client using the google.genai SDK."""
    from google import genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def _call_gemini_with_retry(client, prompt, max_retries=5):
    """Call Gemini API with retry on rate limit / transient errors."""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"      ⚠ Invalid JSON on attempt {attempt+1}, retrying...")
            time.sleep(3)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource" in err_str or "quota" in err_str or "503" in err_str or "unavailable" in err_str:
                # Extract retryDelay from error if present
                retry_match = re.search(r"retryDelay.*?(\d+)s", str(e))
                base_wait = int(retry_match.group(1)) + 2 if retry_match else 15
                wait = base_wait * (attempt + 1)
                print(f"      ⚠ Rate limited (attempt {attempt+1}), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"      ⚠ Gemini error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    raise
    return {"trades": [], "insights": []}


def _store_gemini_results(conn, source_id, segment_start_id, results):
    """Store extracted trades and insights in Postgres."""
    trades_stored = 0
    insights_stored = 0

    with conn.cursor() as cur:
        for trade in results.get("trades", []):
            cur.execute("""
                INSERT INTO video_trades
                    (source_id, symbol, direction, setup_type,
                     entry_criteria, exit_criteria, result, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                source_id,
                trade.get("symbol"),
                trade.get("direction"),
                trade.get("setup_type"),
                json.dumps(trade.get("entry_criteria")) if trade.get("entry_criteria") else None,
                json.dumps(trade.get("exit_criteria")) if trade.get("exit_criteria") else None,
                trade.get("result"),
                trade.get("notes"),
            ))
            trades_stored += 1

        for insight in results.get("insights", []):
            tags = insight.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            cur.execute("""
                INSERT INTO video_insights
                    (source_id, category, description, evidence,
                     confidence, tags)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                source_id,
                insight.get("category", "setup_rule"),
                insight.get("description", ""),
                insight.get("evidence", ""),
                insight.get("confidence", 0.5),
                tags,
            ))
            insights_stored += 1

    conn.commit()
    return trades_stored, insights_stored


def analyze_transcripts():
    """Use Gemini to extract trades and insights from transcripts."""
    print("\n══ STAGE 5: ANALYZE TRANSCRIPTS (Gemini) ══════════════════")
    conn = get_conn()
    client = _init_gemini()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, file_path, filename, category, program, session
            FROM media_sources
            WHERE status = 'processed' OR status = 'transcribed'
            ORDER BY id
        """)
        sources = cur.fetchall()

    if not sources:
        print("  No sources ready for analysis.")
        conn.close()
        return

    total_trades = 0
    total_insights = 0
    total_requests = 0

    for src in sources:
        sid = src["id"]
        ref = src["file_path"]
        label = f"{src['category']}/{src['program']}/{src['session']}"

        state = get_pipeline_state(conn, "video", ref, "transcript_analysis")
        if state and state["status"] == "completed":
            print(f"  ⏭ Already analyzed: {label}")
            continue

        # Get all segments for this source
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, segment_idx, start_sec, end_sec, text
                FROM transcripts WHERE source_id = %s
                ORDER BY segment_idx
            """, (sid,))
            segments = cur.fetchall()

        if not segments:
            upsert_pipeline_state(conn, "video", ref, "transcript_analysis",
                                  "completed", error="no_segments")
            continue

        existing_state = get_pipeline_state(conn, "video", ref, "transcript_analysis")
        last_offset = existing_state["last_offset"] if existing_state else 0

        upsert_pipeline_state(conn, "video", ref, "transcript_analysis", "in_progress")

        print(f"\n  📊 Analyzing: {label} ({len(segments)} segments, "
              f"resuming from offset {last_offset})")

        src_trades = 0
        src_insights = 0

        # Process in batches
        for batch_start in range(last_offset, len(segments), GEMINI_BATCH_SIZE):
            batch = segments[batch_start:batch_start + GEMINI_BATCH_SIZE]
            if not batch:
                break

            transcript_text = "\n".join(
                f"[{s['start_sec']:.0f}s - {s['end_sec']:.0f}s] {s['text']}"
                for s in batch
            )

            start_time = f"{batch[0]['start_sec']:.0f}s"
            end_time = f"{batch[-1]['end_sec']:.0f}s"

            prompt = _build_analysis_prompt(label, start_time, end_time,
                                               transcript_text)

            print(f"    Batch {batch_start//GEMINI_BATCH_SIZE + 1}: "
                  f"segments {batch_start}-{batch_start+len(batch)-1} "
                  f"({start_time} - {end_time})")

            try:
                results = _call_gemini_with_retry(client, prompt)
                t, i = _store_gemini_results(conn, sid, batch[0]["id"], results)
                src_trades += t
                src_insights += i
                total_requests += 1

                upsert_pipeline_state(conn, "video", ref, "transcript_analysis",
                                      "in_progress",
                                      last_offset=batch_start + len(batch))

                print(f"      → {t} trades, {i} insights")

                # Free tier: ~10 RPM + token quota; 6s between requests keeps us safe
                time.sleep(6)

            except Exception as e:
                print(f"      ✗ Batch failed: {e}")
                upsert_pipeline_state(conn, "video", ref, "transcript_analysis",
                                      "in_progress",
                                      last_offset=batch_start,
                                      error=str(e))
                break

        upsert_pipeline_state(conn, "video", ref, "transcript_analysis",
                              "completed", last_offset=len(segments))
        total_trades += src_trades
        total_insights += src_insights
        print(f"  ✓ {label}: {src_trades} trades, {src_insights} insights")

    print(f"\n  Total: {total_trades} trades, {total_insights} insights "
          f"({total_requests} API requests)")
    conn.close()


# ─── Pipeline status ──────────────────────────────────────────────────────────

def show_status():
    """Print current pipeline status from the database."""
    print("\n══ PIPELINE STATUS ════════════════════════════════════════")
    conn = get_conn()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT ms.id, ms.filename, ms.category, ms.program, ms.session,
                   ms.status AS source_status,
                   (SELECT COUNT(*) FROM transcripts t WHERE t.source_id = ms.id) AS segments,
                   (SELECT COUNT(*) FROM frames f WHERE f.source_id = ms.id) AS frames,
                   (SELECT COUNT(*) FROM session_chats sc WHERE sc.source_id = ms.id) AS chats,
                   (SELECT COUNT(*) FROM video_trades vt WHERE vt.source_id = ms.id) AS trades,
                   (SELECT COUNT(*) FROM video_insights vi WHERE vi.source_id = ms.id) AS insights
            FROM media_sources ms
            ORDER BY ms.id
        """)
        sources = cur.fetchall()

    if not sources:
        print("  No sources registered. Run: python3 pipeline.py discover")
        conn.close()
        return

    print(f"\n  {'ID':>3}  {'Status':<13} {'Segs':>5} {'Frames':>6} {'Chats':>5} {'Trades':>6} {'Rules':>5}  Source")
    print(f"  {'─'*90}")
    for s in sources:
        label = f"{s['category']}/{s['program']}/{s['session']}"
        print(f"  {s['id']:>3}  {s['source_status']:<13} {s['segments']:>5} "
              f"{s['frames']:>6} {s['chats']:>5} {s['trades']:>6} {s['insights']:>5}  {label}")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT stage, status, COUNT(*) as cnt
            FROM pipeline_state WHERE source_type = 'video'
            GROUP BY stage, status ORDER BY stage, status
        """)
        states = cur.fetchall()

    if states:
        print(f"\n  Pipeline state summary:")
        for st in states:
            print(f"    {st['stage']:<20} {st['status']:<12} {st['cnt']}")

    conn.close()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Video/audio processing pipeline")
    parser.add_argument("stage", nargs="?", default="all",
                        choices=["all", "discover", "transcribe", "frames",
                                 "chats", "analyze", "status"],
                        help="Pipeline stage to run (default: all)")
    parser.add_argument("--model", default=WHISPER_MODEL,
                        choices=["tiny", "base", "small", "medium", "large"],
                        help=f"Whisper model size (default: {WHISPER_MODEL})")
    args = parser.parse_args()

    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║  TRADING VIDEO PIPELINE                                 ║")
    print(f"║  Model: {args.model:<10}  Stage: {args.stage:<10}              ║")
    print(f"║  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<38}  ║")
    print(f"╚══════════════════════════════════════════════════════════╝")

    if args.stage == "status":
        show_status()
        return

    stages = [
        ("discover", discover),
        ("transcribe", lambda: transcribe_all(model_name=args.model)),
        ("frames", extract_frames_all),
        ("chats", parse_chats),
        ("analyze", analyze_transcripts),
    ]
    stage_names = [s[0] for s in stages]

    if args.stage == "all":
        start_idx = 0
    else:
        start_idx = stage_names.index(args.stage)

    # Always run from the requested stage through the end of the pipeline.
    # Each stage is idempotent — skips completed work automatically.
    for name, fn in stages[start_idx:]:
        fn()

    show_status()


if __name__ == "__main__":
    main()
