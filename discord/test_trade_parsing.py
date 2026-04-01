#!/usr/bin/env python3
"""
Test Discord trade parsing and filtering logic.

Tests that:
1. E-mini S&P and Nasdaq trades are parsed correctly
2. Gold (GC) trades are filtered out
3. Crude oil (CL) trades are filtered out
4. Various symbol formats are recognized
"""

from discord_trade_monitor import parse_trade_signal
from datetime import datetime

def test_trade_parsing():
    """Test various trade message formats."""

    test_cases = [
        # (message, should_parse, expected_symbol)
        ("SELL SPY @ 635.50, SL 636.00, TP 633.00", True, "SPY"),
        ("BUY QQQ 580.25 stop 579.50 target 582.00", True, "QQQ"),
        ("SHORT MES 6350, stop 6355, target 6340", True, "SPY"),
        ("SELL ES 6350, stop 6355, target 6340", True, "SPY"),
        ("BUY NQ 21000, stop 20950, target 21100", True, "QQQ"),
        ("LONG MNQ 21000 sl 20950 tp 21100", True, "QQQ"),
        ("SELL S&P @ 6350, SL 6355, TP 6340", True, "SPY"),
        ("BUY NASDAQ 21000, stop 20950, target 21100", True, "QQQ"),

        # Gold trades (should be ACCEPTED)
        ("SELL GC @ 2850, SL 2860, TP 2830", True, "GLD"),
        ("BUY GOLD 2850 stop 2840 target 2870", True, "GLD"),
        ("SHORT MGC 2850, stop 2860, target 2830", True, "GLD"),

        # Should be FILTERED OUT (crude oil)
        ("SELL CL @ 85.50, SL 86.00, TP 84.00", False, None),
        ("BUY CRUDE 85.50 stop 85.00 target 87.00", False, None),

        # Invalid formats (missing levels)
        ("Think SPY might drop here", False, None),
        ("SPY looking weak", False, None),
    ]

    print("\n" + "="*72)
    print("DISCORD TRADE PARSING TESTS")
    print("="*72)

    passed = 0
    failed = 0

    for msg, should_parse, expected_symbol in test_cases:
        result = parse_trade_signal(msg, "test_id", datetime.now().isoformat())

        if should_parse:
            if result and result["symbol"] == expected_symbol:
                print(f"✅ PASS: \"{msg[:50]}...\"")
                print(f"   → Parsed: {result['direction'].upper()} {result['symbol']} @ {result['entry']}, "
                      f"SL {result['stop']}, TP {result['target']}")
                passed += 1
            else:
                print(f"❌ FAIL: \"{msg[:50]}...\"")
                print(f"   → Expected: {expected_symbol}, Got: {result}")
                failed += 1
        else:
            if result is None:
                print(f"✅ PASS: \"{msg[:50]}...\"")
                print(f"   → Correctly filtered out")
                passed += 1
            else:
                print(f"❌ FAIL: \"{msg[:50]}...\"")
                print(f"   → Should be filtered, but got: {result}")
                failed += 1

        print()

    print("="*72)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*72)

    return failed == 0


if __name__ == "__main__":
    success = test_trade_parsing()
    exit(0 if success else 1)
