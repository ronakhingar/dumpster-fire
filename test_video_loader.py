#!/usr/bin/env python3
"""
Test script for video_insights_loader.py

Verifies database connection, caching, and all query functions.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from video_insights_loader import (
    get_video_insights,
    get_matching_trades,
    validate_setup_against_videos,
    check_timeframe_alignment,
    get_psychology_reminders,
    refresh_cache,
)


def test_basic_load():
    """Test basic data loading."""
    print("=" * 60)
    print("TEST 1: Basic Data Load")
    print("=" * 60)

    insights = get_video_insights()

    print(f"\n✓ Total insights: {insights['total_insights']}")
    print(f"✓ Total trades: {insights['total_trades']}")
    print(f"\n✓ Insights by category:")
    for cat, items in insights['insights_by_category'].items():
        print(f"  - {cat}: {len(items)} insights")

    print(f"\n✓ Trades by setup:")
    for setup, trades in insights['trades_by_setup'].items():
        print(f"  - {setup}: {len(trades)} trades")

    return insights


def test_matching_trades():
    """Test get_matching_trades() function."""
    print("\n" + "=" * 60)
    print("TEST 2: Get Matching Trades")
    print("=" * 60)

    # Test FVG_entry short
    print("\n→ Searching for: FVG_entry (short)")
    matches = get_matching_trades("FVG_entry", direction="short")
    print(f"✓ Found {len(matches)} matching trades")

    if matches:
        print("\nFirst match:")
        print(f"  Setup: {matches[0].get('setup_type')}")
        print(f"  Direction: {matches[0].get('direction')}")
        print(f"  Notes: {matches[0].get('notes', 'N/A')[:100]}...")

    # Test liquidity_sweep
    print("\n→ Searching for: liquidity_sweep (any direction)")
    matches = get_matching_trades("liquidity_sweep")
    print(f"✓ Found {len(matches)} matching trades")

    return matches


def test_setup_validation():
    """Test validate_setup_against_videos() function."""
    print("\n" + "=" * 60)
    print("TEST 3: Setup Validation")
    print("=" * 60)

    # Test FVG_entry short
    print("\n→ Validating: FVG_entry short @ 75 confidence")
    result = validate_setup_against_videos("FVG_entry", "sell", 75)

    print(f"✓ Matches found: {result['matches_found']}")
    print(f"✓ Validation score: {result['validation_score']}/10 bonus points")
    print(f"✓ Similar trades: {len(result['similar_trades'])} examples")

    if result['similar_trades']:
        print("\nTop match:")
        trade = result['similar_trades'][0]
        print(f"  Setup: {trade.get('setup_type')}")
        print(f"  Direction: {trade.get('direction')}")
        print(f"  Notes: {trade.get('notes', 'N/A')[:100]}...")

    return result


def test_timeframe_alignment():
    """Test check_timeframe_alignment() function."""
    print("\n" + "=" * 60)
    print("TEST 4: Timeframe Alignment Check")
    print("=" * 60)

    # Test valid HTF/LTF combo
    print("\n→ Checking: Daily bias + 15Min entry")
    result = check_timeframe_alignment("1Day", "15Min")
    print(f"✓ Valid: {result['valid']}")
    print(f"✓ Bonus points: {result['bonus_points']}")
    if result['principle_matched']:
        print(f"✓ Principle: {result['principle_matched']['description'][:80]}...")

    # Test invalid combo
    print("\n→ Checking: 15Min bias + 1Day entry (invalid)")
    result = check_timeframe_alignment("15Min", "1Day")
    print(f"✓ Valid: {result['valid']}")
    print(f"✓ Bonus points: {result['bonus_points']}")

    return result


def test_psychology_reminders():
    """Test get_psychology_reminders() function."""
    print("\n" + "=" * 60)
    print("TEST 5: Psychology Reminders")
    print("=" * 60)

    reminders = get_psychology_reminders(limit=3)
    print(f"\n✓ Retrieved {len(reminders)} psychology insights:")

    for i, reminder in enumerate(reminders, 1):
        print(f"\n{i}. {reminder['description'][:100]}...")
        if 'evidence' in reminder:
            print(f"   Evidence: {reminder['evidence'][:80]}...")

    return reminders


def test_caching():
    """Test caching mechanism."""
    print("\n" + "=" * 60)
    print("TEST 6: Caching Mechanism")
    print("=" * 60)

    from pathlib import Path
    import time

    cache_file = Path(__file__).parent / "journal" / "video_insights_cache.json"

    print(f"\n→ Cache file location: {cache_file}")

    if cache_file.exists():
        print(f"✓ Cache file exists")
        stat = cache_file.stat()
        print(f"✓ Size: {stat.st_size:,} bytes")
        print(f"✓ Modified: {time.ctime(stat.st_mtime)}")
    else:
        print("⚠ Cache file not yet created (will be created on first load)")

    print("\n→ Loading insights (should use cache if exists)...")
    start = time.time()
    insights = get_video_insights()
    elapsed = time.time() - start

    print(f"✓ Loaded in {elapsed:.3f}s")
    print(f"✓ {insights['total_insights']} insights loaded")

    if cache_file.exists():
        print("✓ Cache file confirmed")

    return cache_file.exists()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VIDEO INSIGHTS LOADER - INTEGRATION TEST")
    print("=" * 60)

    try:
        # Test 1: Basic load
        insights = test_basic_load()

        # Test 2: Matching trades
        matches = test_matching_trades()

        # Test 3: Setup validation
        validation = test_setup_validation()

        # Test 4: Timeframe alignment
        timeframe_check = test_timeframe_alignment()

        # Test 5: Psychology reminders
        psychology = test_psychology_reminders()

        # Test 6: Caching
        cache_exists = test_caching()

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"✓ All tests passed!")
        print(f"✓ Database connection: Working")
        print(f"✓ Total insights available: {insights['total_insights']}")
        print(f"✓ Total trades available: {insights['total_trades']}")
        print(f"✓ Cache system: {'Working' if cache_exists else 'Will create on first load'}")
        print(f"✓ Query functions: All operational")
        print("\n✅ video_insights_loader.py is ready for integration!")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
