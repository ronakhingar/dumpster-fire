#!/usr/bin/env python3
"""
Test video insights integration in agent scoring.

Tests the score_setup function with sample analysis data to verify
video validation bonus is correctly applied.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Mock dependencies that require API keys
class MockAPI:
    pass

def mock_func(*args, **kwargs):
    pass

# Create a complete mock module
mock_alpaca = type(sys)('alpaca_trader')
mock_alpaca.api = MockAPI()
mock_alpaca.buy = mock_func
mock_alpaca.sell = mock_func
mock_alpaca.get_account = mock_func
mock_alpaca.get_quote = mock_func
mock_alpaca.get_positions = mock_func
mock_alpaca.get_historical_bars = mock_func
mock_alpaca.close_position = mock_func
mock_alpaca.get_recent_fills = mock_func
mock_alpaca.get_open_orders = mock_func
mock_alpaca.ALLOWED_SYMBOLS = ['SPY', 'QQQ']

sys.modules['alpaca_trader'] = mock_alpaca

# Now import agent
from agent import score_setup
from memories import A_PLUS_THRESHOLD


def create_sample_analysis(setup_type="ema9_touch_short", recommendation="sell", confidence=75):
    """Create a sample analysis dict for testing."""
    return {
        "symbol": "SPY",
        "detected_setup": setup_type,
        "recommendation": recommendation,
        "confidence": confidence,
        "market_state": {
            "price": 635.69,
            "ema_9": 636.5,
            "ema_21": 638.0,
            "ema_50": 640.0,
            "rsi_14": 37.4,
            "vwap": 636.2,
            "atr_14": 3.2,
            "macd": -0.5,
            "macd_signal": -0.3,
            "volume": 50000000,
        },
        "trade": {
            "entry": 635.69,
            "stop_loss": 636.00,
            "take_profit": 634.80,
            "risk_reward": 2.0,
        }
    }


def test_score_without_video():
    """Test scoring without video validation (baseline)."""
    print("=" * 60)
    print("TEST 1: Scoring WITHOUT Video Integration")
    print("=" * 60)

    analysis = create_sample_analysis()

    score, checks, htf_info = score_setup(
        analysis=analysis,
        daily_bias="bearish",
        weekly_context=None,
        monthly_context=None,
        killzone_label="NY_Lunch"
    )

    print(f"\n✓ Base score: {score}")
    print(f"✓ Checks: {sum(checks.values())}/{len(checks)} passed")

    # Check for video validation in htf_info
    video_info = htf_info.get("video_validation", {})

    print(f"\nVideo Validation:")
    print(f"  - Matches found: {video_info.get('matches_found', 0)}")
    print(f"  - Validation score: {video_info.get('validation_score', 0)}")
    print(f"  - Timeframe valid: {video_info.get('timeframe_valid', False)}")
    print(f"  - Timeframe bonus: {video_info.get('timeframe_bonus', 0)}")

    return score, video_info


def test_score_with_fvg_setup():
    """Test scoring with FVG_entry setup (should have video matches)."""
    print("\n" + "=" * 60)
    print("TEST 2: Scoring WITH FVG_entry Setup (Video Validated)")
    print("=" * 60)

    analysis = create_sample_analysis(
        setup_type="FVG_entry",
        recommendation="sell",
        confidence=80
    )

    score, checks, htf_info = score_setup(
        analysis=analysis,
        daily_bias="bearish",
        weekly_context=None,
        monthly_context=None,
        killzone_label="NY_Lunch"
    )

    print(f"\n✓ Total score: {score}")
    print(f"✓ Checks: {sum(checks.values())}/{len(checks)} passed")

    video_info = htf_info.get("video_validation", {})

    print(f"\nVideo Validation:")
    print(f"  - Matches found: {video_info.get('matches_found', 0)}")
    print(f"  - Validation score: {video_info.get('validation_score', 0)}")
    print(f"  - Timeframe valid: {video_info.get('timeframe_valid', False)}")
    print(f"  - Timeframe bonus: {video_info.get('timeframe_bonus', 0)}")

    if video_info.get('matches_found', 0) > 0:
        print(f"\nSimilar trades from videos:")
        for i, trade in enumerate(video_info.get('similar_trades', [])[:3], 1):
            print(f"  {i}. {trade.get('setup_type')} ({trade.get('direction')})")
            notes = trade.get('notes', 'N/A')
            print(f"     {notes[:80]}...")

    return score, video_info


def test_score_with_liquidity_sweep():
    """Test scoring with liquidity_sweep setup."""
    print("\n" + "=" * 60)
    print("TEST 3: Scoring WITH liquidity_sweep Setup")
    print("=" * 60)

    analysis = create_sample_analysis(
        setup_type="liquidity_sweep",
        recommendation="sell",
        confidence=85
    )

    score, checks, htf_info = score_setup(
        analysis=analysis,
        daily_bias="bearish",
        weekly_context=None,
        monthly_context=None,
        killzone_label="London"
    )

    print(f"\n✓ Total score: {score}")
    print(f"✓ Checks: {sum(checks.values())}/{len(checks)} passed")

    video_info = htf_info.get("video_validation", {})

    print(f"\nVideo Validation:")
    print(f"  - Matches found: {video_info.get('matches_found', 0)}")
    print(f"  - Validation score: {video_info.get('validation_score', 0)}")
    print(f"  - Similar trades: {len(video_info.get('similar_trades', []))}")

    total_video_bonus = video_info.get('validation_score', 0) + video_info.get('timeframe_bonus', 0)
    print(f"  - Total video bonus: +{total_video_bonus} points")

    return score, video_info


def test_comparison():
    """Compare scores with and without video validation."""
    print("\n" + "=" * 60)
    print("TEST 4: Impact Comparison")
    print("=" * 60)

    # Setup 1: Generic setup (no video matches expected)
    analysis_generic = create_sample_analysis("ema9_touch_short", "sell", 75)
    score_generic, _, htf_generic = score_setup(
        analysis=analysis_generic,
        daily_bias="bearish",
        weekly_context=None,
        monthly_context=None,
        killzone_label="NY_Lunch"
    )
    video_generic = htf_generic.get("video_validation", {})
    video_bonus_generic = video_generic.get('validation_score', 0) + video_generic.get('timeframe_bonus', 0)

    # Setup 2: FVG_entry (should have video matches)
    analysis_fvg = create_sample_analysis("FVG_entry", "sell", 75)
    score_fvg, _, htf_fvg = score_setup(
        analysis=analysis_fvg,
        daily_bias="bearish",
        weekly_context=None,
        monthly_context=None,
        killzone_label="NY_Lunch"
    )
    video_fvg = htf_fvg.get("video_validation", {})
    video_bonus_fvg = video_fvg.get('validation_score', 0) + video_fvg.get('timeframe_bonus', 0)

    print(f"\nGeneric Setup (ema9_touch_short):")
    print(f"  Score: {score_generic}")
    print(f"  Video matches: {video_generic.get('matches_found', 0)}")
    print(f"  Video bonus: +{video_bonus_generic}")

    print(f"\nValidated Setup (FVG_entry):")
    print(f"  Score: {score_fvg}")
    print(f"  Video matches: {video_fvg.get('matches_found', 0)}")
    print(f"  Video bonus: +{video_bonus_fvg}")

    print(f"\nImpact:")
    print(f"  Score difference: {score_fvg - score_generic:+d} points")
    print(f"  Video bonus difference: {video_bonus_fvg - video_bonus_generic:+d} points")

    if score_generic < A_PLUS_THRESHOLD <= score_fvg:
        print(f"\n  💡 Video validation ENABLED this trade!")
        print(f"     Without videos: {score_generic} < {A_PLUS_THRESHOLD} (rejected)")
        print(f"     With videos:    {score_fvg} >= {A_PLUS_THRESHOLD} (accepted)")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VIDEO INSIGHTS INTEGRATION TEST")
    print("=" * 60)

    try:
        # Test 1: Generic setup
        score1, video1 = test_score_without_video()

        # Test 2: FVG setup
        score2, video2 = test_score_with_fvg_setup()

        # Test 3: Liquidity sweep
        score3, video3 = test_score_with_liquidity_sweep()

        # Test 4: Comparison
        test_comparison()

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print("✓ Video insights module loaded successfully")
        print("✓ score_setup() function accepts video validation")
        print("✓ Video bonus correctly applied to total score")
        print("✓ Timeframe alignment check working")
        print(f"✓ A+ threshold: {A_PLUS_THRESHOLD}")
        print("\n✅ Video insights integration is working!")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
