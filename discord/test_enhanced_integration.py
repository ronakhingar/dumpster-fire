#!/usr/bin/env python3
"""
Integration test for enhanced Discord parsing.
Tests the complete flow: messages → parser → signals → futures agent
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from enhanced_trade_parser import EnhancedTradeParser

ET = ZoneInfo("America/New_York")


def test_single_message_trade():
    """Test classic single-message format (backward compatibility)."""
    print("\n" + "="*72)
    print("TEST 1: Single-Message Trade (Backward Compatible)")
    print("="*72)

    parser = EnhancedTradeParser()

    msg = {
        'id': '1',
        'author': {'nickname': 'trader1', 'name': 'trader1'},
        'content': 'SELL GC @ 2850, SL 2860, TP 2830',
        'timestamp': '2026-04-01T09:30:00-04:00'
    }

    signal = parser.process_message(msg)

    if signal:
        print("✅ PASS: Single-message trade detected")
        print(f"   Signal: {signal['direction'].upper()} {signal['symbol']} @ {signal['entry']}")
        print(f"   Stop: {signal['stop']}, Target: {signal['target']}")
        return True
    else:
        print("❌ FAIL: Single-message trade NOT detected")
        return False


def test_multi_message_sequence():
    """Test multi-message trade building."""
    print("\n" + "="*72)
    print("TEST 2: Multi-Message Sequence (NEW)")
    print("="*72)

    parser = EnhancedTradeParser()

    messages = [
        {
            'id': '1',
            'author': {'nickname': 'trader2', 'name': 'trader2'},
            'content': 'Looking at ES long setup',
            'timestamp': '2026-04-01T09:30:00-04:00'
        },
        {
            'id': '2',
            'author': {'nickname': 'trader2', 'name': 'trader2'},
            'content': 'Entered ES 6350',
            'timestamp': '2026-04-01T09:31:00-04:00'
        },
        {
            'id': '3',
            'author': {'nickname': 'trader2', 'name': 'trader2'},
            'content': 'Stop 6345, targets 6360 and 6370',
            'timestamp': '2026-04-01T09:32:00-04:00'
        }
    ]

    signal = None
    for msg in messages:
        result = parser.process_message(msg)
        if result:
            signal = result

    if signal:
        print("✅ PASS: Multi-message trade detected")
        print(f"   Signal: {signal['direction'].upper()} {signal['symbol']} @ {signal['entry']}")
        print(f"   Stop: {signal['stop']}, Target: {signal['target']}")
        print(f"   Linked from {len(signal['messages'])} messages")
        return True
    else:
        print("❌ FAIL: Multi-message trade NOT detected")
        return False


def test_position_update():
    """Test position update handling."""
    print("\n" + "="*72)
    print("TEST 3: Position Update (Breakeven Move)")
    print("="*72)

    parser = EnhancedTradeParser()

    # Initial trade
    messages = [
        {
            'id': '1',
            'author': {'nickname': 'trader3', 'name': 'trader3'},
            'content': 'ES long 6350, stop 6345, target 6360',
            'timestamp': '2026-04-01T09:30:00-04:00'
        },
        {
            'id': '2',
            'author': {'nickname': 'trader3', 'name': 'trader3'},
            'content': 'Moving stop to breakeven',
            'timestamp': '2026-04-01T09:35:00-04:00'
        }
    ]

    signal = None
    for msg in messages:
        result = parser.process_message(msg)
        if result:
            signal = result

    # Check if stop was updated
    trade_state = parser.get_active_trade('trader3', 'SPY')

    if trade_state and trade_state.stop == trade_state.entry:
        print("✅ PASS: Stop updated to breakeven")
        print(f"   Original stop: 6345")
        print(f"   Updated stop: {trade_state.stop} (= entry)")
        return True
    else:
        print("❌ FAIL: Stop NOT updated to breakeven")
        return False


def test_invalidation():
    """Test trade invalidation handling."""
    print("\n" + "="*72)
    print("TEST 4: Trade Invalidation")
    print("="*72)

    parser = EnhancedTradeParser()

    messages = [
        {
            'id': '1',
            'author': {'nickname': 'trader4', 'name': 'trader4'},
            'content': 'NQ short 21000, stop 21050, target 20900',
            'timestamp': '2026-04-01T09:30:00-04:00'
        },
        {
            'id': '2',
            'author': {'nickname': 'trader4', 'name': 'trader4'},
            'content': 'Setup broke, exiting',
            'timestamp': '2026-04-01T09:32:00-04:00'
        }
    ]

    signal = None
    for msg in messages:
        result = parser.process_message(msg)
        if result:
            signal = result

    trade_state = parser.get_active_trade('trader4', 'QQQ')

    if trade_state and trade_state.status == 'invalidated':
        print("✅ PASS: Trade invalidated correctly")
        print(f"   Status: {trade_state.status}")
        return True
    else:
        print("❌ FAIL: Trade NOT invalidated")
        return False


def test_symbol_variants():
    """Test different symbol formats."""
    print("\n" + "="*72)
    print("TEST 5: Symbol Variant Recognition")
    print("="*72)

    parser = EnhancedTradeParser()

    test_cases = [
        ("SELL ES @ 6350, SL 6355, TP 6340", "SPY"),
        ("BUY MES 6350, stop 6345, target 6360", "SPY"),  # Fixed: stop below entry for LONG
        ("SHORT S&P 6350, sl 6355, tp 6340", "SPY"),
        ("LONG NQ 21000, stop 20950, target 21100", "QQQ"),
        ("SELL MNQ 21000, sl 21050, tp 20900", "QQQ"),
        ("BUY GC @ 2850, SL 2840, TP 2870", "GLD"),
        ("SHORT GOLD 2850, stop 2860, target 2830", "GLD"),
    ]

    passed = 0
    for i, (content, expected_symbol) in enumerate(test_cases, 1):
        msg = {
            'id': f'{i}',
            'author': {'nickname': f'test{i}', 'name': f'test{i}'},
            'content': content,
            'timestamp': '2026-04-01T09:30:00-04:00'
        }

        signal = parser.process_message(msg)

        if signal and signal['symbol'] == expected_symbol:
            print(f"✅ Test {i}/{len(test_cases)}: {content[:30]}... → {expected_symbol}")
            passed += 1
        else:
            print(f"❌ Test {i}/{len(test_cases)}: {content[:30]}... → Expected {expected_symbol}, got {signal['symbol'] if signal else None}")

    if passed == len(test_cases):
        print(f"\n✅ PASS: All {len(test_cases)} symbol variants recognized")
        return True
    else:
        print(f"\n⚠️  PARTIAL: {passed}/{len(test_cases)} symbol variants recognized")
        return passed == len(test_cases)


def main():
    """Run all integration tests."""
    print("\n" + "="*72)
    print("ENHANCED DISCORD PARSER - INTEGRATION TESTS")
    print("="*72)

    tests = [
        test_single_message_trade,
        test_multi_message_sequence,
        test_position_update,
        test_invalidation,
        test_symbol_variants
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append(False)

    # Summary
    print("\n" + "="*72)
    print("TEST SUMMARY")
    print("="*72)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
