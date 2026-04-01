#!/usr/bin/env python3
"""
Real-time FOMC timing detection for intraday trading decisions.

Provides precise timing (hours until/since FOMC) to adjust trading strategy.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# 2026 FOMC Meeting Schedule
# Announcement time is always 2:00 PM ET on the second day
FOMC_2026_SCHEDULE = [
    (2026, 1, 29, 14, 0),   # January 29, 2026 @ 2:00 PM ET
    (2026, 3, 18, 14, 0),   # March 18, 2026 @ 2:00 PM ET
    (2026, 5, 6, 14, 0),    # May 6, 2026 @ 2:00 PM ET
    (2026, 6, 17, 14, 0),   # June 17, 2026 @ 2:00 PM ET
    (2026, 7, 29, 14, 0),   # July 29, 2026 @ 2:00 PM ET
    (2026, 9, 16, 14, 0),   # September 16, 2026 @ 2:00 PM ET
    (2026, 11, 4, 14, 0),   # November 4, 2026 @ 2:00 PM ET
    (2026, 12, 16, 14, 0),  # December 16, 2026 @ 2:00 PM ET
]


def get_fomc_timing() -> dict:
    """
    Get precise FOMC timing relative to current time.

    Returns:
        {
            "is_fomc_week": bool,
            "is_fomc_today": bool,
            "hours_until_fomc": float or None (negative if already happened),
            "stage": str,  # "normal", "fomc_pre_24h", "fomc_pre_2h", "fomc_during", "fomc_post_2h"
            "next_fomc_date": str,
            "note": str
        }
    """
    now = datetime.now(ET)

    # Find next/current FOMC
    next_fomc = None
    hours_until = None

    for year, month, day, hour, minute in FOMC_2026_SCHEDULE:
        fomc_dt = datetime(year, month, day, hour, minute, tzinfo=ET)
        hours_diff = (fomc_dt - now).total_seconds() / 3600

        # Check if this is the relevant FOMC (upcoming or just passed)
        if -2 < hours_diff < 168:  # Within 1 week before or 2 hours after
            next_fomc = fomc_dt
            hours_until = hours_diff
            break

    if next_fomc is None:
        # No FOMC in next week
        return {
            "is_fomc_week": False,
            "is_fomc_today": False,
            "hours_until_fomc": None,
            "stage": "normal",
            "next_fomc_date": None,
            "note": "No FOMC meetings in the next 7 days"
        }

    # Classify stage based on timing
    is_fomc_today = next_fomc.date() == now.date()
    is_fomc_week = abs(hours_until) < 168  # Within 1 week

    if hours_until < -2:
        # More than 2 hours after FOMC
        stage = "normal"
        note = f"FOMC already passed at {next_fomc.strftime('%I:%M %p')}"
    elif hours_until < 0:
        # Within 2 hours after FOMC (BEST TRADING TIME)
        stage = "fomc_post_2h"
        hours_since = abs(hours_until)
        note = f"Post-FOMC ({hours_since:.1f}h since announcement) - HIGH OPPORTUNITY"
    elif hours_until < 0.5:
        # Less than 30 minutes before (DON'T TRADE)
        stage = "fomc_during"
        note = f"FOMC announcement in {hours_until*60:.0f} minutes - AVOID TRADING"
    elif hours_until < 2:
        # 30min - 2 hours before (FINAL POSITIONING)
        stage = "fomc_pre_immediate"
        note = f"FOMC in {hours_until:.1f}h - Close/reduce positions, liquidity sweeps likely"
    elif hours_until < 24:
        # 2-24 hours before (CAUTIOUS TRADING)
        stage = "fomc_pre_24h"
        note = f"FOMC in {hours_until:.1f}h - Trade cautiously, expect positioning"
    else:
        # More than 24 hours before
        stage = "normal"
        note = f"FOMC {next_fomc.strftime('%B %d')} ({hours_until/24:.1f} days away)"

    return {
        "is_fomc_week": is_fomc_week,
        "is_fomc_today": is_fomc_today,
        "hours_until_fomc": round(hours_until, 2),
        "stage": stage,
        "next_fomc_date": next_fomc.isoformat(),
        "note": note
    }


def get_fomc_score_adjustment(setup_type: str, stage: str) -> dict:
    """
    Get setup-specific score adjustment based on FOMC timing stage.

    Args:
        setup_type: Detected setup type (e.g., "FVG_entry", "liquidity_sweep")
        stage: FOMC timing stage from get_fomc_timing()

    Returns:
        {
            "adjustment": int,  # Points to add/subtract
            "reason": str,
            "recommended_action": str
        }
    """
    # Stage-specific setup adjustments
    adjustments = {
        "normal": {
            "default": (0, "Normal market conditions", "Trade all setups normally")
        },
        "fomc_pre_24h": {
            "liquidity_sweep": (+10, "Pre-FOMC liquidity sweep likely", "TAKE - Expect sweep before event"),
            "FVG_entry": (-5, "Pre-FOMC uncertainty", "CAUTION - May get choppy"),
            "order_block": (-5, "Pre-FOMC volatility", "CAUTION - Structure may break"),
            "power_of_three": (+8, "Manipulation phase before event", "TAKE - Classic pre-event setup"),
            "default": (-10, "Pre-FOMC uncertainty", "AVOID - Too risky before event")
        },
        "fomc_pre_immediate": {
            "liquidity_sweep": (+15, "Final sweep before announcement", "TAKE - But exit before 1:50 PM"),
            "default": (-20, "Too close to FOMC", "AVOID - Don't be in positions during announcement")
        },
        "fomc_during": {
            "default": (-50, "FOMC announcement happening", "DO NOT TRADE - Wait for dust to settle")
        },
        "fomc_post_2h": {
            "FVG_entry": (+20, "Post-FOMC gap fill opportunity", "TAKE - Prime setup after volatility"),
            "liquidity_sweep": (+18, "Post-event reversal", "TAKE - Sweep and reverse common"),
            "order_block": (+15, "New institutional zones from event", "TAKE - Fresh levels created"),
            "power_of_three": (+12, "Post-event trend establishment", "TAKE - Continuation likely"),
            "default": (+10, "Post-FOMC clarity", "GOOD - Market direction clearer now")
        }
    }

    stage_adjustments = adjustments.get(stage, adjustments["normal"])

    # Get setup-specific adjustment or default
    if setup_type in stage_adjustments:
        adjustment, reason, action = stage_adjustments[setup_type]
    else:
        adjustment, reason, action = stage_adjustments["default"]

    return {
        "adjustment": adjustment,
        "reason": reason,
        "recommended_action": action
    }


if __name__ == "__main__":
    """Test FOMC timing detection."""
    timing = get_fomc_timing()
    print(f"\n{'='*60}")
    print("FOMC TIMING DETECTION")
    print(f"{'='*60}")
    print(f"Current time: {datetime.now(ET).strftime('%Y-%m-%d %I:%M %p ET')}")
    print(f"\nFOMC Status:")
    print(f"  Is FOMC week: {timing['is_fomc_week']}")
    print(f"  Is FOMC today: {timing['is_fomc_today']}")
    print(f"  Hours until FOMC: {timing['hours_until_fomc']}")
    print(f"  Stage: {timing['stage']}")
    print(f"  Note: {timing['note']}")

    if timing['stage'] != "normal":
        print(f"\n{'='*60}")
        print("SETUP-SPECIFIC ADJUSTMENTS")
        print(f"{'='*60}")

        test_setups = [
            "liquidity_sweep",
            "FVG_entry",
            "order_block",
            "power_of_three",
            "ema9_touch_short"
        ]

        for setup in test_setups:
            adj = get_fomc_score_adjustment(setup, timing['stage'])
            sign = "+" if adj['adjustment'] >= 0 else ""
            print(f"\n{setup}:")
            print(f"  Adjustment: {sign}{adj['adjustment']} pts")
            print(f"  Reason: {adj['reason']}")
            print(f"  Action: {adj['recommended_action']}")
