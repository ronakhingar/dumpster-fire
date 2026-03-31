#!/usr/bin/env python3
"""
Video insights database loader.

Queries PostgreSQL for trading insights extracted from Mastermind videos.
Implements caching to avoid hitting DB on every agent scan.

Usage:
    from video_insights_loader import (
        get_video_insights,
        get_matching_trades,
        validate_setup_against_videos,
    )

    # Load all insights (cached for 24h)
    insights = get_video_insights()

    # Get matching trade examples
    trades = get_matching_trades("FVG_entry", direction="short")

    # Validate current setup
    validation = validate_setup_against_videos(
        setup_type="FVG_entry",
        direction="short",
        confidence=75
    )
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = Path(__file__).parent / "journal" / "video_insights_cache.json"
CACHE_TTL_HOURS = 24  # Refresh daily


class VideoInsightsLoader:
    """Lazy-loading singleton for video insights."""

    _instance = None
    _cache = None
    _last_loaded = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_connection(self):
        """Create PostgreSQL connection."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return None
        try:
            return psycopg2.connect(db_url)
        except Exception as e:
            print(f"  ⚠ Video insights DB connection failed: {e}")
            return None

    def _load_from_cache(self) -> Optional[dict]:
        """Load from cache if fresh."""
        if not CACHE_FILE.exists():
            return None

        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)

            loaded_at = datetime.fromisoformat(cache["loaded_at"])
            age = datetime.now() - loaded_at

            if age < timedelta(hours=CACHE_TTL_HOURS):
                return cache["data"]
        except Exception as e:
            print(f"  ⚠ Cache read error: {e}")

        return None

    def _save_to_cache(self, data: dict):
        """Save to cache file."""
        cache = {
            "loaded_at": datetime.now().isoformat(),
            "data": data
        }
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            print(f"  ⚠ Cache write error: {e}")

    def load(self) -> dict:
        """
        Load video insights with caching.

        Returns dict with:
        - insights_by_category: {category: [insights]}
        - trades_by_setup: {setup_type: [trades]}
        - psychology_reminders: [insights]
        - market_structure_rules: [insights]
        - entry_timing_rules: [insights]
        - total_insights: int
        - total_trades: int
        """
        # Try cache first
        cached = self._load_from_cache()
        if cached:
            return cached

        # Load from database
        conn = self._get_connection()
        if not conn:
            return self._empty_data()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Load insights by category
                cur.execute("""
                    SELECT category, description, evidence,
                           confidence, tags
                    FROM video_insights
                    ORDER BY confidence DESC
                """)
                insights = cur.fetchall()

                # Load trades by setup type
                cur.execute("""
                    SELECT setup_type, direction, entry_criteria,
                           exit_criteria, notes, result
                    FROM video_trades
                    WHERE setup_type IS NOT NULL
                    ORDER BY created_at DESC
                """)
                trades = cur.fetchall()

            # Organize data
            data = self._organize_data(insights, trades)

            # Cache it
            self._save_to_cache(data)

            print(f"  📚 Loaded {len(insights)} insights + {len(trades)} trades from videos")

            return data

        except Exception as e:
            print(f"  ⚠ Video insights query error: {e}")
            return self._empty_data()
        finally:
            conn.close()

    def _organize_data(self, insights: list, trades: list) -> dict:
        """Organize insights and trades into useful structure."""
        data = {
            "insights_by_category": {},
            "trades_by_setup": {},
            "psychology_reminders": [],
            "market_structure_rules": [],
            "entry_timing_rules": [],
            "risk_management_rules": [],
            "confluence_factors": [],
            "total_insights": len(insights),
            "total_trades": len(trades),
        }

        # Group insights by category
        for insight in insights:
            cat = insight["category"]
            if cat not in data["insights_by_category"]:
                data["insights_by_category"][cat] = []
            data["insights_by_category"][cat].append(dict(insight))

            # Also add to specific lists
            if cat == "psychology":
                data["psychology_reminders"].append(dict(insight))
            elif cat == "market_structure":
                data["market_structure_rules"].append(dict(insight))
            elif cat == "entry_timing":
                data["entry_timing_rules"].append(dict(insight))
            elif cat == "risk_management":
                data["risk_management_rules"].append(dict(insight))
            elif cat == "confluence":
                data["confluence_factors"].append(dict(insight))

        # Group trades by setup type
        for trade in trades:
            setup = trade["setup_type"]
            if setup not in data["trades_by_setup"]:
                data["trades_by_setup"][setup] = []
            data["trades_by_setup"][setup].append(dict(trade))

        return data

    def _empty_data(self) -> dict:
        """Return empty structure if DB unavailable."""
        return {
            "insights_by_category": {},
            "trades_by_setup": {},
            "psychology_reminders": [],
            "market_structure_rules": [],
            "entry_timing_rules": [],
            "risk_management_rules": [],
            "confluence_factors": [],
            "total_insights": 0,
            "total_trades": 0,
        }


# Singleton instance
_loader = VideoInsightsLoader()


def get_video_insights() -> dict:
    """
    Get cached video insights.

    Returns dict with all insights organized by category and setup type.
    Data is cached for 24h to avoid DB queries on every scan.
    """
    return _loader.load()


def get_matching_trades(setup_type: str, direction: str = None) -> list[dict]:
    """
    Get video trades matching setup type and direction.

    Args:
        setup_type: Setup type (e.g., "FVG_entry", "liquidity_sweep")
        direction: Optional direction filter ("long" or "short")

    Returns:
        List of matching trade dicts with notes, entry_criteria, etc.
    """
    insights = get_video_insights()
    matches = insights["trades_by_setup"].get(setup_type, [])

    if direction:
        matches = [t for t in matches if t.get("direction") == direction]

    return matches


def validate_setup_against_videos(
    setup_type: str,
    direction: str,
    confidence: int
) -> dict:
    """
    Validate current setup against documented video examples.

    Args:
        setup_type: Detected setup type
        direction: Trade direction ("buy" or "sell")
        confidence: Analysis confidence score

    Returns:
        {
            "matches_found": int,
            "validation_score": int (0-10 bonus points),
            "similar_trades": list[dict]
        }
    """
    # Map buy/sell to long/short
    trade_direction = "long" if direction == "buy" else "short"

    matches = get_matching_trades(setup_type, trade_direction)

    # Calculate validation bonus
    validation_score = 0
    if len(matches) >= 5:
        validation_score = 10  # Strong validation
    elif len(matches) >= 3:
        validation_score = 7   # Good validation
    elif len(matches) >= 1:
        validation_score = 5   # Some validation

    return {
        "matches_found": len(matches),
        "validation_score": validation_score,
        "similar_trades": matches[:5],  # Top 5
    }


def get_psychology_reminders(limit: int = 3) -> list[dict]:
    """
    Get top psychology insights.

    Args:
        limit: Maximum number of reminders to return

    Returns:
        List of psychology insight dicts with description and evidence.
    """
    insights = get_video_insights()
    return insights["psychology_reminders"][:limit]


def check_timeframe_alignment(
    htf_bias_timeframe: str,
    ltf_entry_timeframe: str
) -> dict:
    """
    Check if timeframe usage matches video principles.

    Args:
        htf_bias_timeframe: High timeframe used for bias (e.g., "1Day")
        ltf_entry_timeframe: Low timeframe used for entry (e.g., "15Min")

    Returns:
        {
            "valid": bool,
            "principle_matched": dict or None,
            "bonus_points": int
        }
    """
    insights = get_video_insights()
    market_structure_rules = insights.get("market_structure_rules", [])

    # Look for the HTF bias + LTF entry principle
    htf_principle = None
    for rule in market_structure_rules:
        desc = rule.get("description", "").lower()
        if "high timeframe" in desc and "bias" in desc and "low timeframe" in desc:
            htf_principle = rule
            break

    if not htf_principle:
        return {"valid": True, "principle_matched": None, "bonus_points": 0}

    # Basic validation: HTF should be larger than LTF
    htf_order = {"1Month": 4, "1Week": 3, "1Day": 2, "15Min": 1, "5Min": 0, "1Min": -1}
    htf_rank = htf_order.get(htf_bias_timeframe, 0)
    ltf_rank = htf_order.get(ltf_entry_timeframe, 0)

    valid = htf_rank > ltf_rank

    return {
        "valid": valid,
        "principle_matched": htf_principle if valid else None,
        "bonus_points": 5 if valid else 0,
    }


def refresh_cache():
    """Force refresh the cache by deleting it."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print(f"  🔄 Video insights cache cleared")
