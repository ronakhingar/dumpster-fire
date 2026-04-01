#!/usr/bin/env python3
"""
Discord Database Integration

Replaces JSON file storage with PostgreSQL database for Discord signals.
Provides full tracking, performance analysis, and author credibility scoring.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

ET = ZoneInfo("America/New_York")
DB_URL = os.getenv("DATABASE_URL")


def get_conn():
    """Get database connection."""
    if not DB_URL:
        raise ValueError("DATABASE_URL not set in environment")
    return psycopg2.connect(DB_URL)


# ═══ CHANNEL MANAGEMENT ═══════════════════════════════════════════════════════

def init_channels():
    """Initialize the three monitored Discord channels."""
    channels = [
        {
            "id": 545047039084593163,
            "name": "stock-alerts",
            "guild_id": 400345242882146314,
            "description": "Stock alerts and market updates",
            "priority": "high"
        },
        {
            "id": 981926799212679248,
            "name": "day-trade-alerts",
            "guild_id": 400345242882146314,
            "description": "Intraday trading signals",
            "priority": "high"
        },
        {
            "id": 661023267439509536,
            "name": "swings",
            "guild_id": 400345242882146314,
            "description": "Swing trade setups",
            "priority": "high"
        }
    ]

    conn = get_conn()
    with conn.cursor() as cur:
        for ch in channels:
            cur.execute("""
                INSERT INTO discord_channels (id, name, guild_id, description, priority)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    priority = EXCLUDED.priority
            """, (ch["id"], ch["name"], ch["guild_id"], ch["description"], ch["priority"]))
    conn.commit()
    conn.close()
    print(f"✓ Initialized {len(channels)} Discord channels")


# ═══ MESSAGE STORAGE ══════════════════════════════════════════════════════════

def save_message(message_id: int, author_id: int, author_name: str,
                 content: str, timestamp: datetime, channel_id: int = None,
                 attachments: dict = None, reactions: dict = None) -> int:
    """
    Save Discord message to database.

    Returns message_id (same as input, for chaining).
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO discord_messages
                (id, author_id, author_name, content, timestamp, attachments, reactions)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET content = EXCLUDED.content,
                reactions = EXCLUDED.reactions
        """, (message_id, author_id, author_name, content, timestamp,
              json.dumps(attachments) if attachments else None,
              json.dumps(reactions) if reactions else None))
    conn.commit()
    conn.close()
    return message_id


# ═══ SIGNAL EXTRACTION & STORAGE ══════════════════════════════════════════════

def save_signal(message_id: int, channel_id: int, extracted_data: dict) -> int:
    """
    Save extracted signal to database.

    Args:
        message_id: Discord message ID
        channel_id: Discord channel ID
        extracted_data: Dict with keys:
            - symbols: list
            - sentiment: str
            - confidence: str
            - support_levels: dict
            - resistance_levels: dict (optional)
            - key_insights: list
            - risk_factors: list
            - time_horizon: str (optional)
            - signal_type: str (default: 'market_analysis')
            - expires_at: datetime (default: 4 hours)

    Returns:
        signal_id (database primary key)
    """
    conn = get_conn()

    # Defaults
    signal_type = extracted_data.get("signal_type", "market_analysis")
    confidence = extracted_data.get("confidence", "medium")
    time_horizon = extracted_data.get("time_horizon")
    expires_at = extracted_data.get("expires_at")

    if not expires_at:
        expires_at = datetime.now(ET) + timedelta(hours=4)

    # Extract text snippet for reference
    raw_text_snippet = extracted_data.get("raw_text_snippet", "")[:500]

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO discord_signals (
                message_id, channel_id,
                signal_type, confidence, time_horizon,
                symbols, sentiment,
                support_levels, resistance_levels, price_targets,
                key_insights, risk_factors, catalysts,
                regime_context, technical_levels, volume_context,
                valuation_notes, sector_context,
                expires_at, raw_text_snippet,
                extraction_method, extraction_version
            )
            VALUES (
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s
            )
            RETURNING id
        """, (
            message_id, channel_id,
            signal_type, confidence, time_horizon,
            extracted_data.get("symbols", []),
            extracted_data.get("sentiment", "neutral"),
            json.dumps(extracted_data.get("support_levels", {})),
            json.dumps(extracted_data.get("resistance_levels")),
            json.dumps(extracted_data.get("price_targets")),
            extracted_data.get("key_insights", []),
            extracted_data.get("risk_factors", []),
            extracted_data.get("catalysts", []),
            extracted_data.get("regime_context"),
            json.dumps(extracted_data.get("technical_levels")),
            extracted_data.get("volume_context"),
            extracted_data.get("valuation_notes"),
            extracted_data.get("sector_context"),
            expires_at, raw_text_snippet,
            extracted_data.get("extraction_method", "pattern"),
            extracted_data.get("extraction_version", "1.0")
        ))
        signal_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    return signal_id


# ═══ ACTIVE SIGNALS FOR AGENT ════════════════════════════════════════════════

def get_active_signals(symbol: str = None) -> list:
    """
    Get active Discord signals ready for agent consumption.

    Args:
        symbol: Filter by symbol (SPY, QQQ) or None for all

    Returns:
        List of signal dicts
    """
    conn = get_conn()

    query = """
        SELECT
            s.id,
            s.message_id,
            c.name as channel_name,
            s.symbols,
            s.sentiment,
            s.confidence,
            s.time_horizon,
            s.support_levels,
            s.resistance_levels,
            s.key_insights,
            s.risk_factors,
            s.expires_at,
            m.author_name,
            m.content as full_message,
            EXTRACT(EPOCH FROM (NOW() - s.extracted_at))/60 as age_minutes
        FROM discord_signals s
        JOIN discord_messages m ON s.message_id = m.id
        JOIN discord_channels c ON s.channel_id = c.id
        WHERE s.expires_at > NOW()
          AND c.enabled = TRUE
    """

    params = []
    if symbol:
        query += " AND %s = ANY(s.symbols)"
        params.append(symbol)

    query += " ORDER BY s.extracted_at DESC"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        results = cur.fetchall()

    conn.close()

    # Convert to dict and parse JSON fields
    signals = []
    for row in results:
        sig = dict(row)
        # Parse JSON strings back to dicts
        if sig.get('support_levels'):
            sig['support_levels'] = json.loads(sig['support_levels'])
        if sig.get('resistance_levels'):
            sig['resistance_levels'] = json.loads(sig['resistance_levels'])
        signals.append(sig)

    return signals


def get_signal_for_symbol(symbol: str) -> dict:
    """Get most recent active signal for a symbol."""
    signals = get_active_signals(symbol)
    return signals[0] if signals else None


# ═══ PERFORMANCE TRACKING ════════════════════════════════════════════════════

def log_signal_usage(signal_id: int, trade_id: str, symbol: str,
                     signal_sentiment: str, signal_confidence: str,
                     score_bonus: int, trade_direction: str,
                     entry_price: float, signal_age_minutes: int):
    """
    Log that a signal influenced a trade.

    Call this when agent takes a trade influenced by a Discord signal.
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO signal_performance (
                signal_id, trade_id, symbol,
                signal_sentiment, signal_confidence, score_bonus,
                trade_direction, entry_price,
                signal_age_minutes, trade_opened_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (signal_id, trade_id, symbol, signal_sentiment, signal_confidence,
              score_bonus, trade_direction, entry_price, signal_age_minutes))

        # Update signal applied_to_trades array
        cur.execute("""
            UPDATE discord_signals
            SET applied_to_trades = array_append(applied_to_trades, %s),
                score_impact = jsonb_set(
                    COALESCE(score_impact, '{}'::jsonb),
                    ARRAY[%s],
                    %s::text::jsonb
                )
            WHERE id = %s
        """, (trade_id, trade_id, score_bonus, signal_id))

    conn.commit()
    conn.close()


def update_trade_outcome(trade_id: str, exit_price: float, pnl: float,
                        result: str, signal_accuracy: str = None):
    """
    Update trade outcome in signal performance tracking.

    Args:
        trade_id: Trade identifier
        exit_price: Exit price
        pnl: Profit/loss amount
        result: 'win', 'loss', 'breakeven'
        signal_accuracy: 'correct', 'incorrect', 'neutral'
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE signal_performance
            SET
                exit_price = %s,
                pnl = %s,
                result = %s,
                signal_accuracy = %s,
                trade_closed_at = NOW()
            WHERE trade_id = %s
        """, (exit_price, pnl, result, signal_accuracy, trade_id))

        # Get signal and author info for credibility update
        cur.execute("""
            SELECT sp.signal_id, m.author_id, m.author_name
            FROM signal_performance sp
            JOIN discord_signals s ON sp.signal_id = s.id
            JOIN discord_messages m ON s.message_id = m.id
            WHERE sp.trade_id = %s
        """, (trade_id,))
        row = cur.fetchone()

        if row:
            signal_id, author_id, author_name = row
            update_author_stats(conn, author_id, author_name, result == 'win', pnl)

    conn.commit()
    conn.close()


def update_author_stats(conn, author_id: int, author_name: str,
                       is_correct: bool, pnl: float):
    """Update author credibility stats after trade outcome."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO signal_author_stats (author_id, author_name, total_signals)
            VALUES (%s, %s, 0)
            ON CONFLICT (author_id) DO NOTHING
        """, (author_id, author_name))

        if is_correct:
            cur.execute("""
                UPDATE signal_author_stats
                SET
                    signals_used = signals_used + 1,
                    correct_calls = correct_calls + 1,
                    accuracy_rate = correct_calls::float / NULLIF(correct_calls + incorrect_calls, 0),
                    total_pnl_impact = total_pnl_impact + %s,
                    updated_at = NOW()
                WHERE author_id = %s
            """, (pnl, author_id))
        else:
            cur.execute("""
                UPDATE signal_author_stats
                SET
                    signals_used = signals_used + 1,
                    incorrect_calls = incorrect_calls + 1,
                    accuracy_rate = correct_calls::float / NULLIF(correct_calls + incorrect_calls, 0),
                    total_pnl_impact = total_pnl_impact + %s,
                    updated_at = NOW()
                WHERE author_id = %s
            """, (pnl, author_id))


# ═══ AUTHOR CREDIBILITY ═══════════════════════════════════════════════════════

def get_author_credibility(author_name: str) -> dict:
    """
    Get author's signal accuracy and track record.

    Returns dict with accuracy_rate, total_signals, avg_score_bonus, etc.
    """
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM signal_author_stats
            WHERE author_name = %s
        """, (author_name,))
        result = cur.fetchone()
    conn.close()

    return dict(result) if result else None


def get_top_authors(min_signals: int = 5, limit: int = 10) -> list:
    """Get top performing signal authors."""
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM top_signal_authors
            WHERE total_signals >= %s
            LIMIT %s
        """, (min_signals, limit))
        results = cur.fetchall()
    conn.close()

    return [dict(row) for row in results]


# ═══ ANALYTICS & REPORTING ════════════════════════════════════════════════════

def get_signal_effectiveness(channel_name: str = None) -> list:
    """
    Get signal effectiveness metrics by channel/sentiment/confidence.
    """
    conn = get_conn()

    query = "SELECT * FROM signal_effectiveness"
    params = []

    if channel_name:
        query += " WHERE channel_name = %s"
        params.append(channel_name)

    query += " ORDER BY win_rate DESC NULLS LAST"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        results = cur.fetchall()
    conn.close()

    return [dict(row) for row in results]


def get_recent_signals(hours: int = 24, limit: int = 20) -> list:
    """Get recent signals extracted in the last N hours."""
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                s.*,
                c.name as channel_name,
                m.author_name
            FROM discord_signals s
            JOIN discord_channels c ON s.channel_id = c.id
            JOIN discord_messages m ON s.message_id = m.id
            WHERE s.extracted_at > NOW() - INTERVAL '%s hours'
            ORDER BY s.extracted_at DESC
            LIMIT %s
        """, (hours, limit))
        results = cur.fetchall()
    conn.close()

    return [dict(row) for row in results]


# ═══ MIGRATION FROM JSON ══════════════════════════════════════════════════════

def migrate_json_signals_to_db():
    """
    Migrate existing JSON-based signals to database.

    Reads from journal/discord_signals_history.jsonl and imports to DB.
    """
    json_file = Path(__file__).parent / "journal" / "discord_signals_history.jsonl"

    if not json_file.exists():
        print("No JSON history file to migrate")
        return 0

    migrated = 0
    with open(json_file) as f:
        for line in f:
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                # Create fake message entry
                message_id = int(record.get("notification_id", "0").split("_")[-1])
                if message_id == 0:
                    message_id = int(datetime.now().timestamp() * 1000)

                # Save message
                save_message(
                    message_id=message_id,
                    author_id=0,  # Unknown
                    author_name="Historical",
                    content=record.get("raw_text", ""),
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    channel_id=None  # Unknown
                )

                # Save signal
                extracted_data = record.get("signals", {})
                extracted_data["raw_text_snippet"] = record.get("raw_text", "")[:500]
                extracted_data["expires_at"] = datetime.fromisoformat(record["expires_at"])

                save_signal(message_id, None, extracted_data)
                migrated += 1

            except Exception as e:
                print(f"⚠ Failed to migrate record: {e}")
                continue

    print(f"✓ Migrated {migrated} historical signals to database")
    return migrated


if __name__ == "__main__":
    import sys

    if "--init" in sys.argv:
        print("Initializing Discord channels...")
        init_channels()

    elif "--migrate" in sys.argv:
        print("Migrating JSON signals to database...")
        migrate_json_signals_to_db()

    elif "--test" in sys.argv:
        print("\nTesting Discord Database Integration:\n")

        # Test active signals
        print("Active signals:")
        signals = get_active_signals()
        print(f"  Found {len(signals)} active signals")

        for sig in signals[:3]:
            print(f"  • {sig['symbols']} - {sig['sentiment']} ({sig['confidence']})")
            print(f"    Age: {sig['age_minutes']:.0f} minutes")

        # Test author stats
        print("\nTop authors:")
        authors = get_top_authors(min_signals=1, limit=5)
        for author in authors:
            print(f"  • {author['author_name']}: {author['accuracy_rate']:.1%} "
                  f"({author['total_signals']} signals)")

        # Test effectiveness
        print("\nSignal effectiveness:")
        effectiveness = get_signal_effectiveness()
        for eff in effectiveness[:5]:
            print(f"  • {eff['channel_name']} {eff['sentiment']}/{eff['confidence']}: "
                  f"{eff['win_rate']:.1%} win rate ({eff['trades_influenced']} trades)")

    else:
        print("Discord Database Integration")
        print("Usage:")
        print("  python3 discord_db.py --init      # Initialize channels")
        print("  python3 discord_db.py --migrate   # Migrate JSON to DB")
        print("  python3 discord_db.py --test      # Test queries")
