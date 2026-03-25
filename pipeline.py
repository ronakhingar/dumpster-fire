#!/usr/bin/env python3
"""
Video/audio processing pipeline.

Stages (each is resumable via pipeline_state table):
  1. discover   — scan tt/ and register sources in media_sources
  2. transcribe — Whisper on .m4a (or parse .cc.vtt where available)
  3. frames     — FFmpeg: 1 frame per 30 seconds from .mp4
  4. chats      — parse Zoom newChat.txt into session_chats

Usage:
  python3 pipeline.py                  # run full pipeline
  python3 pipeline.py discover         # run single stage
  python3 pipeline.py transcribe       # run single stage
  python3 pipeline.py frames           # run single stage
  python3 pipeline.py chats            # run single stage
  python3 pipeline.py --model medium   # use larger Whisper model
"""

from __future__ import annotations

import argparse
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

def extract_frames_for_source(conn, source_id, mp4_path):
    """Extract 1 frame per 30 seconds from a video using FFmpeg."""
    out_dir = FRAMES_DIR / str(source_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-i", mp4_path,
        "-vf", "fps=1/30",
        "-q:v", "5",
        "-y",
        str(out_dir / "frame_%04d.jpg"),
    ]

    print(f"    Extracting frames from {Path(mp4_path).name}...")
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")

    frames = sorted(out_dir.glob("frame_*.jpg"))
    print(f"    Extracted {len(frames)} frames in {elapsed:.0f}s")

    with conn.cursor() as cur:
        for i, fp in enumerate(frames):
            timestamp_sec = i * 30.0
            rel_path = str(fp.relative_to(Path(__file__).parent))
            cur.execute("""
                INSERT INTO frames (source_id, timestamp_sec, file_path)
                VALUES (%s, %s, %s)
            """, (source_id, timestamp_sec, rel_path))
    conn.commit()

    return len(frames)


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
                   (SELECT COUNT(*) FROM session_chats sc WHERE sc.source_id = ms.id) AS chats
            FROM media_sources ms
            ORDER BY ms.id
        """)
        sources = cur.fetchall()

    if not sources:
        print("  No sources registered. Run: python3 pipeline.py discover")
        conn.close()
        return

    print(f"\n  {'ID':>3}  {'Status':<13} {'Segs':>5} {'Frames':>6} {'Chats':>5}  Source")
    print(f"  {'─'*80}")
    for s in sources:
        label = f"{s['category']}/{s['program']}/{s['session']}"
        print(f"  {s['id']:>3}  {s['source_status']:<13} {s['segments']:>5} "
              f"{s['frames']:>6} {s['chats']:>5}  {label}")

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
                                 "chats", "status"],
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

    stages = {
        "discover": discover,
        "transcribe": lambda: transcribe_all(model_name=args.model),
        "frames": extract_frames_all,
        "chats": parse_chats,
    }

    if args.stage == "all":
        for name, fn in stages.items():
            fn()
    else:
        stages[args.stage]()

    show_status()


if __name__ == "__main__":
    main()
