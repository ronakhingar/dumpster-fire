#!/usr/bin/env python3
"""
Backtest the trading agent on historical data.

Usage:
    python3 backtest.py 2024-03-20           # Single day
    python3 backtest.py 2024-03-20 SPY       # Single day, specific symbol
    python3 backtest.py 2024-03-01 2024-03-31  # Date range (coming soon)

Replays historical bars and simulates agent decisions in real-time.
No look-ahead bias - only uses data available at each moment.
"""

from __future__ import annotations

import sys
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca_trader import get_historical_bars
from memories import KILLZONES
from backtest_engine import analyze_with_bars

ET = ZoneInfo("America/New_York")

# Backtest configuration
POSITION_SIZE_PCT = 0.05  # 5% of capital per trade
STARTING_CAPITAL = 100000  # $100k
MAX_TRADES_PER_DAY = 5
MAX_LOSSES_PER_DAY = 2
DAILY_LOSS_LIMIT_PCT = 0.02  # 2% daily loss limit
MIN_SCORE = 80  # A+ setups only


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def is_killzone(dt: datetime) -> tuple[bool, str]:
    """Check if time is within a killzone."""
    t = dt.time()

    for kz_name, kz_data in KILLZONES.items():
        start_time = time.fromisoformat(kz_data['start'])
        end_time = time.fromisoformat(kz_data['end'])

        if start_time <= t < end_time:
            return True, kz_data['label']

    return False, ""


def calculate_position_size(capital: float, entry_price: float, stop_price: float) -> int:
    """Calculate position size based on risk (1.5% max risk per trade)."""
    risk_per_trade = capital * 0.015  # 1.5% of capital
    risk_per_share = abs(entry_price - stop_price)

    if risk_per_share == 0:
        return 0

    shares = int(risk_per_trade / risk_per_share)

    # Cap at 5% of capital worth of shares
    max_shares = int((capital * POSITION_SIZE_PCT) / entry_price)

    return min(shares, max_shares)


def format_time(timestamp_str: str) -> str:
    """Format timestamp for display."""
    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    dt_et = dt.astimezone(ET)
    return dt_et.strftime("%H:%M")


def format_currency(value: float) -> str:
    """Format currency value."""
    return f"${value:,.2f}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Trade Simulation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def simulate_trade_on_bars(position: dict, bars: list[dict]) -> tuple[dict | None, str, float]:
    """
    Check if stop or target was hit on given bars.

    Returns:
        (updated_position, exit_reason, exit_price)
        - If still open: (position, "", 0)
        - If closed: (None, "stop_hit" or "target_hit", exit_price)
    """
    direction = position['direction']
    stop = position['stop']
    target = position['target']

    for bar in bars:
        # For long positions
        if direction == 'long':
            # Check stop first (conservative - assume stop hit if touched)
            if bar['low'] <= stop:
                return None, "stop_hit", stop

            # Check target
            if bar['high'] >= target:
                return None, "target_hit", target

        # For short positions
        else:  # direction == 'short'
            # Check stop first
            if bar['high'] >= stop:
                return None, "stop_hit", stop

            # Check target
            if bar['low'] <= target:
                return None, "target_hit", target

    # Still open
    return position, "", 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main Backtest Logic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def backtest_single_day(date_str: str, symbol: str = "SPY", timeframe: str = "5Min", verbose: bool = True):
    """
    Backtest a single day using historical bars.

    Args:
        date_str: Date in YYYY-MM-DD format
        symbol: SPY or QQQ
        timeframe: 5Min recommended for speed
    """
    if verbose:
        print(f"\n{'='*80}")
        print(f"  BACKTESTING {symbol} on {date_str}")
        print(f"  Timeframe: {timeframe} | Starting Capital: {format_currency(STARTING_CAPITAL)}")
        print(f"{'='*80}\n")

    # Load all bars for the day (instant)
    if verbose:
        print(f"  📊 Loading historical bars for {date_str}...")
    bars = get_historical_bars(symbol, timeframe, start=date_str, end=date_str)

    if not bars:
        if verbose:
            print(f"  ❌ No bars available for {date_str}")
        return None

    if verbose:
        print(f"  ✅ Loaded {len(bars)} bars\n")

    # State tracking
    capital = STARTING_CAPITAL
    position = None
    trades_today = 0
    losses_today = 0
    pnl_today = 0
    daily_loss_limit = capital * DAILY_LOSS_LIMIT_PCT

    completed_trades = []

    # Replay through each bar
    for i, bar in enumerate(bars):
        bar_time_str = format_time(bar['time'])
        bar_dt = datetime.fromisoformat(bar['time'].replace('Z', '+00:00')).astimezone(ET)

        # ━━━ CHECK EXISTING POSITION ━━━
        if position:
            # Store position data before simulating
            entry_price = position['entry_price']
            shares = position['shares']
            direction = position['direction']
            stop = position['stop']
            entry_time = position['entry_time']
            setup_type = position.get('setup_type', 'unknown')

            # Simulate stop/target check on this bar
            position, exit_reason, exit_price = simulate_trade_on_bars(position, [bar])

            if exit_reason:  # Trade closed
                # Calculate P&L
                if direction == 'long':
                    pnl = (exit_price - entry_price) * shares
                else:  # short
                    pnl = (entry_price - exit_price) * shares

                pnl_today += pnl
                capital += pnl

                # Calculate R
                risk = abs(entry_price - stop)
                reward = abs(exit_price - entry_price)
                r_multiple = reward / risk if risk > 0 else 0

                # Record trade
                trade_record = {
                    'entry_time': entry_time,
                    'exit_time': bar_time_str,
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': shares,
                    'pnl': pnl,
                    'r_multiple': r_multiple,
                    'exit_reason': exit_reason,
                    'setup_type': setup_type
                }
                completed_trades.append(trade_record)

                # Track losses
                if pnl < 0:
                    losses_today += 1

                # Display
                if verbose:
                    emoji = "✅" if exit_reason == "target_hit" else "❌"
                    print(f"  {emoji} {bar_time_str}: EXIT {direction.upper()} @ {format_currency(exit_price)}")
                    print(f"     Reason: {exit_reason.replace('_', ' ').title()}")
                    print(f"     P&L: {format_currency(pnl)} ({r_multiple:.2f}R)")
                    print(f"     Capital: {format_currency(capital)}\n")

        # ━━━ CHECK FOR NEW ENTRIES ━━━
        if not position and trades_today < MAX_TRADES_PER_DAY and losses_today < MAX_LOSSES_PER_DAY:
            # Check if in killzone
            in_kz, kz_name = is_killzone(bar_dt)

            if not in_kz:
                continue

            # Check daily loss limit
            if pnl_today < -daily_loss_limit:
                print(f"  🛑 {bar_time_str}: Daily loss limit hit ({format_currency(pnl_today)}), no more trades\n")
                break

            # ━━━ RUN ANALYSIS (NO LOOK-AHEAD!) ━━━
            # Only pass bars up to current index
            historical_bars = bars[0:i+1]

            # Need at least 50 bars for indicators
            if len(historical_bars) < 50:
                continue

            # Run real analysis on historical data
            analysis = analyze_with_bars(historical_bars, symbol)

            setup = analysis.get('setup')
            side = analysis.get('side')
            score = analysis.get('score', 0)
            entry_price = analysis.get('entry')
            stop = analysis.get('stop')
            target = analysis.get('target')

            # Check if we have a valid A+ setup (score >= MIN_SCORE)
            if setup and side and score >= MIN_SCORE and entry_price and stop and target:
                # Map side to direction
                direction = 'long' if side == 'buy' else 'short'

                # Calculate position size
                shares = calculate_position_size(capital, entry_price, stop)

                if shares > 0:
                    position = {
                        'entry_time': bar_time_str,
                        'entry_price': entry_price,
                        'stop': stop,
                        'target': target,
                        'direction': direction,
                        'shares': shares,
                        'setup_type': f'{kz_name}_{setup}',
                        'score': score
                    }

                    trades_today += 1

                    if verbose:
                        print(f"  📍 {bar_time_str}: ENTER {direction.upper()} @ {format_currency(entry_price)}")
                        print(f"     Setup: {setup} | Killzone: {kz_name} | Score: {score}")
                        print(f"     Stop: {format_currency(stop)} | Target: {format_currency(target)}")
                        print(f"     Shares: {shares} | Risk: {format_currency(abs(entry_price - stop) * shares)}")
                        print(f"     Indicators: RSI={analysis['indicators'].get('rsi', 0):.1f}, "
                              f"Trend={analysis.get('trend', 'unknown')}\n")

    # ━━━ BACKTEST SUMMARY ━━━
    if verbose:
        print(f"\n{'='*80}")
        print(f"  BACKTEST SUMMARY - {date_str}")
        print(f"{'='*80}\n")

        print(f"  Total Trades: {len(completed_trades)}")
        print(f"  Starting Capital: {format_currency(STARTING_CAPITAL)}")
        print(f"  Ending Capital: {format_currency(capital)}")
        print(f"  Total P&L: {format_currency(pnl_today)} ({(pnl_today/STARTING_CAPITAL)*100:+.2f}%)")

        if completed_trades:
            wins = [t for t in completed_trades if t['pnl'] > 0]
            losses = [t for t in completed_trades if t['pnl'] < 0]

            print(f"\n  Wins: {len(wins)} | Losses: {len(losses)}")
            print(f"  Win Rate: {(len(wins)/len(completed_trades))*100:.1f}%")

            if wins:
                avg_win = sum(t['pnl'] for t in wins) / len(wins)
                avg_win_r = sum(t['r_multiple'] for t in wins) / len(wins)
                print(f"  Avg Win: {format_currency(avg_win)} ({avg_win_r:.2f}R)")

            if losses:
                avg_loss = sum(t['pnl'] for t in losses) / len(losses)
                avg_loss_r = sum(t['r_multiple'] for t in losses) / len(losses)
                print(f"  Avg Loss: {format_currency(avg_loss)} ({avg_loss_r:.2f}R)")

            avg_r = sum(t['r_multiple'] for t in completed_trades) / len(completed_trades)
            print(f"  Avg R-Multiple: {avg_r:.2f}R")

            # Show trades
            print(f"\n  Trade Details:")
            print(f"  {'Time':<12}{'Dir':<6}{'Entry':<12}{'Exit':<12}{'P&L':<15}{'R':<8}{'Result'}")
            print(f"  {'-'*80}")
            for t in completed_trades:
                result_emoji = "✅" if t['pnl'] > 0 else "❌"
                print(f"  {t['entry_time']:<12}{t['direction']:<6}"
                      f"{format_currency(t['entry_price']):<12}"
                      f"{format_currency(t['exit_price']):<12}"
                      f"{format_currency(t['pnl']):<15}"
                      f"{t['r_multiple']:.2f}R    {result_emoji}")

        print(f"\n{'='*80}\n")
    else:
        # Silent mode - just show summary line
        if completed_trades:
            wins = len([t for t in completed_trades if t['pnl'] > 0])
            losses = len([t for t in completed_trades if t['pnl'] < 0])
            print(f"  {date_str}: {len(completed_trades)} trades ({wins}W/{losses}L) | "
                  f"P&L: {format_currency(pnl_today)}")
        else:
            print(f"  {date_str}: No trades")

    # Return results for multi-day backtesting
    return {
        'date': date_str,
        'trades': completed_trades,
        'starting_capital': STARTING_CAPITAL,
        'ending_capital': capital,
        'pnl': pnl_today
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def backtest_date_range(start_date: str, end_date: str, symbol: str = "SPY", timeframe: str = "5Min"):
    """
    Backtest across multiple trading days.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        symbol: SPY or QQQ
        timeframe: 5Min or 1Min recommended
    """
    from datetime import datetime, timedelta

    print(f"\n{'='*80}")
    print(f"  MULTI-DAY BACKTEST: {start_date} to {end_date}")
    print(f"  Symbol: {symbol} | Timeframe: {timeframe}")
    print(f"{'='*80}\n")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    all_trades = []
    daily_results = []
    total_capital = STARTING_CAPITAL

    current_dt = start_dt
    while current_dt <= end_dt:
        # Skip weekends
        if current_dt.weekday() >= 5:
            current_dt += timedelta(days=1)
            continue

        date_str = current_dt.strftime("%Y-%m-%d")
        print(f"\n{'─'*80}")
        print(f"  📅 Testing {date_str}")
        print(f"{'─'*80}")

        # Run backtest for this day (silent mode)
        result = backtest_single_day(date_str, symbol, timeframe, verbose=False)

        if result:
            all_trades.extend(result['trades'])
            daily_results.append(result)
            total_capital = result['ending_capital']

        current_dt += timedelta(days=1)

    # Aggregate statistics
    print(f"\n\n{'='*80}")
    print(f"  AGGREGATE BACKTEST RESULTS")
    print(f"{'='*80}\n")

    total_trades = len(all_trades)
    wins = [t for t in all_trades if t['pnl'] > 0]
    losses = [t for t in all_trades if t['pnl'] < 0]

    print(f"  Trading Days: {len(daily_results)}")
    print(f"  Total Trades: {total_trades}")
    print(f"  Starting Capital: {format_currency(STARTING_CAPITAL)}")
    print(f"  Ending Capital: {format_currency(total_capital)}")
    print(f"  Total P&L: {format_currency(total_capital - STARTING_CAPITAL)} "
          f"({((total_capital - STARTING_CAPITAL)/STARTING_CAPITAL)*100:+.2f}%)")

    if total_trades > 0:
        print(f"\n  Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"  Win Rate: {(len(wins)/total_trades)*100:.1f}%")

        if wins:
            avg_win = sum(t['pnl'] for t in wins) / len(wins)
            avg_win_r = sum(t['r_multiple'] for t in wins) / len(wins)
            print(f"  Avg Win: {format_currency(avg_win)} ({avg_win_r:.2f}R)")

        if losses:
            avg_loss = sum(t['pnl'] for t in losses) / len(losses)
            avg_loss_r = sum(t['r_multiple'] for t in losses) / len(losses)
            print(f"  Avg Loss: {format_currency(avg_loss)} ({avg_loss_r:.2f}R)")

        avg_r = sum(t['r_multiple'] for t in all_trades) / len(all_trades)
        print(f"  Avg R-Multiple: {avg_r:.2f}R")

        # Profit factor
        total_wins_dollar = sum(t['pnl'] for t in wins) if wins else 0
        total_losses_dollar = abs(sum(t['pnl'] for t in losses)) if losses else 1
        profit_factor = total_wins_dollar / total_losses_dollar if total_losses_dollar > 0 else 0
        print(f"  Profit Factor: {profit_factor:.2f}")

        # Setup type analysis
        setup_types = {}
        for t in all_trades:
            stype = t['setup_type']
            if stype not in setup_types:
                setup_types[stype] = {'wins': 0, 'losses': 0, 'total_r': 0}
            if t['pnl'] > 0:
                setup_types[stype]['wins'] += 1
            else:
                setup_types[stype]['losses'] += 1
            setup_types[stype]['total_r'] += t['r_multiple']

        if setup_types:
            print(f"\n  Setup Type Performance:")
            for stype, stats in sorted(setup_types.items(), key=lambda x: x[1]['total_r'], reverse=True):
                total = stats['wins'] + stats['losses']
                wr = (stats['wins'] / total * 100) if total > 0 else 0
                avg_r = stats['total_r'] / total if total > 0 else 0
                print(f"    {stype}: {stats['wins']}W/{stats['losses']}L ({wr:.0f}% WR, {avg_r:.2f}R avg)")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 backtest.py YYYY-MM-DD [SYMBOL] [TIMEFRAME]")
        print("  python3 backtest.py YYYY-MM-DD YYYY-MM-DD [SYMBOL] [TIMEFRAME]")
        print("\nExamples:")
        print("  python3 backtest.py 2024-03-20 SPY")
        print("  python3 backtest.py 2024-03-20 2024-03-31 SPY 5Min")
        sys.exit(1)

    # Check if date range or single date
    date_arg1 = sys.argv[1]

    # Try to parse second arg as date for range
    if len(sys.argv) >= 3:
        try:
            datetime.strptime(sys.argv[2], "%Y-%m-%d")
            # Second arg is a date, so this is a range
            date_arg2 = sys.argv[2]
            symbol = sys.argv[3] if len(sys.argv) > 3 else "SPY"
            timeframe = sys.argv[4] if len(sys.argv) > 4 else "5Min"
            backtest_date_range(date_arg1, date_arg2, symbol, timeframe)
        except ValueError:
            # Second arg is not a date, single day with symbol
            date = date_arg1
            symbol = sys.argv[2]
            timeframe = sys.argv[3] if len(sys.argv) > 3 else "5Min"
            backtest_single_day(date, symbol, timeframe)
    else:
        # Single date only
        backtest_single_day(date_arg1)
