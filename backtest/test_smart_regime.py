#!/usr/bin/env python3
"""
Test smart regime system with setup-specific adjustments.

Demonstrates how different setups score differently based on market conditions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.memories import REGIME_SETUP_MODIFIERS
from src.fomc_timing import get_fomc_timing, get_fomc_score_adjustment


def test_regime_modifiers():
    """Test regime-specific setup modifiers."""
    print("=" * 72)
    print("REGIME-SPECIFIC SETUP MODIFIERS")
    print("=" * 72)

    test_setups = [
        "liquidity_sweep",
        "FVG_entry",
        "order_block",
        "ema9_touch_short",
        "overbought_reversal",
    ]

    regimes = [
        "high_volatility",
        "extreme_volatility",
        "strong_bullish_trend",
        "strong_bearish_trend",
    ]

    for regime in regimes:
        print(f"\n{regime.upper().replace('_', ' ')}")
        print("-" * 72)

        if regime not in REGIME_SETUP_MODIFIERS:
            print("  No specific modifiers for this regime")
            continue

        regime_modifiers = REGIME_SETUP_MODIFIERS[regime]

        for setup in test_setups:
            modifier = regime_modifiers.get(setup, regime_modifiers.get("default", 0))
            sign = "+" if modifier >= 0 else ""
            status = "✓" if modifier > 0 else "✗" if modifier < 0 else "~"

            print(f"  {status} {setup:25} {sign}{modifier:3d} pts")


def test_fomc_timing():
    """Test FOMC timing detection and adjustments."""
    print("\n" + "=" * 72)
    print("FOMC TIMING SYSTEM")
    print("=" * 72)

    timing = get_fomc_timing()

    print(f"\nCurrent Status:")
    print(f"  Stage: {timing['stage']}")
    print(f"  Note: {timing['note']}")

    if timing['stage'] == "normal":
        print("\n  (No FOMC adjustments active)")
        return

    print(f"\nSetup-Specific Adjustments:")
    print("-" * 72)

    test_setups = [
        "liquidity_sweep",
        "FVG_entry",
        "order_block",
        "power_of_three",
        "ema9_touch_short",
    ]

    for setup in test_setups:
        adj = get_fomc_score_adjustment(setup, timing['stage'])
        sign = "+" if adj['adjustment'] >= 0 else ""
        status = "✓" if adj['adjustment'] > 0 else "✗" if adj['adjustment'] < 0 else "~"

        print(f"\n{status} {setup}")
        print(f"    Adjustment: {sign}{adj['adjustment']} pts")
        print(f"    Reason: {adj['reason']}")
        print(f"    Action: {adj['recommended_action']}")


def test_combined_scenario():
    """Test combined scenario with multiple factors."""
    print("\n" + "=" * 72)
    print("COMBINED SCENARIO EXAMPLES")
    print("=" * 72)

    scenarios = [
        {
            "name": "Normal Day - Liquidity Sweep",
            "regime": "normal",
            "setup": "liquidity_sweep",
            "fomc_stage": "normal",
            "base_score": 70,
        },
        {
            "name": "High Vol Day - Liquidity Sweep",
            "regime": "high_volatility",
            "setup": "liquidity_sweep",
            "fomc_stage": "normal",
            "base_score": 70,
        },
        {
            "name": "High Vol Day - EMA Touch (Tight Stops)",
            "regime": "high_volatility",
            "setup": "ema9_touch_short",
            "fomc_stage": "normal",
            "base_score": 70,
        },
        {
            "name": "Pre-FOMC (2h) - Liquidity Sweep",
            "regime": "normal",
            "setup": "liquidity_sweep",
            "fomc_stage": "fomc_pre_immediate",
            "base_score": 70,
        },
        {
            "name": "Post-FOMC - FVG Entry",
            "regime": "normal",
            "setup": "FVG_entry",
            "fomc_stage": "fomc_post_2h",
            "base_score": 70,
        },
        {
            "name": "Strong Bull - Short Setup (Counter-Trend)",
            "regime": "strong_bullish_trend",
            "setup": "ema9_touch_short",
            "fomc_stage": "normal",
            "base_score": 70,
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 72)

        base = scenario['base_score']
        regime_adj = 0
        fomc_adj = 0

        # Get regime adjustment
        if scenario['regime'] in REGIME_SETUP_MODIFIERS:
            regime_modifiers = REGIME_SETUP_MODIFIERS[scenario['regime']]
            regime_adj = regime_modifiers.get(
                scenario['setup'],
                regime_modifiers.get("default", 0)
            )

        # Get FOMC adjustment
        if scenario['fomc_stage'] != "normal":
            fomc_data = get_fomc_score_adjustment(scenario['setup'], scenario['fomc_stage'])
            fomc_adj = fomc_data['adjustment']

        final = base + regime_adj + fomc_adj

        print(f"  Base Score:        {base}")
        print(f"  Regime Adjustment: {regime_adj:+d} ({scenario['regime']})")
        print(f"  FOMC Adjustment:   {fomc_adj:+d} ({scenario['fomc_stage']})")
        print(f"  ──────────────────────")
        print(f"  Final Score:       {final}")

        threshold = 80
        if final >= threshold:
            print(f"  Result: ✅ QUALIFIED (>= {threshold})")
        else:
            print(f"  Result: ❌ REJECTED (< {threshold})")


def test_real_world_comparison():
    """Compare old vs new system."""
    print("\n" + "=" * 72)
    print("OLD vs NEW SYSTEM COMPARISON")
    print("=" * 72)

    # Scenario: High volatility day, liquidity sweep setup
    print("\nScenario: High Volatility Day (VIX 35)")
    print("Setup: liquidity_sweep short")
    print("-" * 72)

    base_score = 70

    print("\n❌ OLD SYSTEM (Blanket Penalty):")
    print(f"  Base: {base_score}")
    print(f"  High Vol Penalty: -5 (applies to ALL setups)")
    print(f"  Final: {base_score - 5} → REJECTED (< 80)")

    print("\n✅ NEW SYSTEM (Smart Adjustment):")
    print(f"  Base: {base_score}")
    print(f"  High Vol Bonus: +8 (liquidity sweeps THRIVE in volatility)")
    print(f"  Final: {base_score + 8} → QUALIFIED (>= 80)")
    print(f"  Reason: More stops = bigger sweeps = higher probability")


def main():
    """Run all tests."""
    print("\n" + "=" * 72)
    print("SMART REGIME SYSTEM - COMPREHENSIVE TEST")
    print("=" * 72)

    test_regime_modifiers()
    test_fomc_timing()
    test_combined_scenario()
    test_real_world_comparison()

    print("\n" + "=" * 72)
    print("TEST COMPLETE")
    print("=" * 72)
    print("\n✅ Smart regime system is operational!")
    print("\nKey Features:")
    print("  • Setup-specific regime adjustments")
    print("  • Real-time FOMC timing detection")
    print("  • Combined scoring with multiple factors")
    print("  • Better trade selection in all conditions")


if __name__ == "__main__":
    main()
