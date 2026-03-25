#!/usr/bin/env python3
"""
Daily Review & Learning System

Analyzes completed trades, calculates performance metrics, and adjusts
A+ scoring criteria weights based on what's actually working.

Process:
  1. Wait for market close
  2. Analyze all trades from today
  3. Correlate criteria with win/loss outcomes
  4. Adjust weights using exponential moving average
  5. Save learned weights for tomorrow
  6. Generate performance report

Run automatically via cron or manually:
  python3 daily_review.py
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca_trader import api, get_recent_fills, ALLOWED_SYMBOLS
from memories import SCORE_CRITERIA, WEEKLY_LIQUIDITY_BONUS, MONTHLY_LIQUIDITY_BONUS

ET = ZoneInfo("America/New_York")
JOURNAL_DIR = Path(__file__).parent / "journal"
WEIGHTS_FILE = Path(__file__).parent / "learned_weights.json"
REVIEWS_DIR = Path(__file__).parent / "journal" / "reviews"

# Learning parameters
LEARNING_RATE = 0.15  # How fast to adjust weights (0.1-0.3 recommended)
MIN_TRADES_TO_LEARN = 3  # Minimum trades before adjusting weights
MIN_WEIGHT = 2  # Minimum weight value
MAX_WEIGHT = 30  # Maximum weight value
CONFIDENCE_THRESHOLD = 0.6  # Minimum win rate to increase weight


# ─── Load Learned Weights ─────────────────────────────────────────────────────

def load_learned_weights() -> dict:
    """
    Load learned weights from disk, or return defaults if none exist.

    Returns dict with:
      - criteria_weights: {criterion: weight}
      - weekly_liquidity_bonus: {proximity: bonus}
      - monthly_liquidity_bonus: {proximity: bonus}
      - meta: learning stats
    """
    if not WEIGHTS_FILE.exists():
        return {
            "criteria_weights": dict(SCORE_CRITERIA),
            "weekly_liquidity_bonus": dict(WEEKLY_LIQUIDITY_BONUS),
            "monthly_liquidity_bonus": dict(MONTHLY_LIQUIDITY_BONUS),
            "meta": {
                "version": 1,
                "last_updated": None,
                "total_trades_analyzed": 0,
                "days_learning": 0,
            }
        }

    with open(WEIGHTS_FILE, "r") as f:
        return json.load(f)


def save_learned_weights(weights: dict):
    """Persist learned weights to disk."""
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=2)
    print(f"  💾 Saved learned weights to {WEIGHTS_FILE}")


# ─── Collect Trade Data ───────────────────────────────────────────────────────

def get_today_trades() -> list[dict]:
    """
    Get all trades executed today by reading decision logs and matching
    with Alpaca fills.

    Returns list of dicts with:
      - symbol, side, qty, entry, exit, pnl, pnl_pct
      - detected_setup, scores, criteria (from decision log)
      - outcome: "win", "loss", "breakeven", "open"
    """
    today_str = datetime.now(ET).strftime("%Y-%m-%d")
    decisions_dir = JOURNAL_DIR / "decisions"

    # Get all "order_placed" decisions from today
    trade_decisions = []
    for f in sorted(decisions_dir.glob(f"{today_str}_*_order_placed_*.json")):
        with open(f, "r") as fh:
            decision = json.load(fh)
            trade_decisions.append(decision)

    if not trade_decisions:
        print(f"  ℹ No trades placed today ({today_str})")
        return []

    print(f"  📊 Found {len(trade_decisions)} trade decisions from today")

    # Get fills from Alpaca to determine outcomes
    try:
        recent_fills = get_recent_fills(limit=50)
    except Exception as e:
        print(f"  ⚠ Could not fetch recent fills: {e}")
        recent_fills = []

    # Match decisions with fills and calculate outcomes
    trades = []
    for decision in trade_decisions:
        order_id = decision.get("trade_levels", {}).get("order_id")
        symbol = decision["symbol"]
        side = decision["recommendation"]

        # Find matching fill
        fill = None
        for f in recent_fills:
            if f.get("id") == order_id and f.get("symbol") == symbol:
                fill = f
                break

        if not fill:
            # Trade might still be open
            trade = {
                "symbol": symbol,
                "side": side,
                "entry": decision["trade_levels"].get("entry"),
                "exit": None,
                "pnl": 0,
                "pnl_pct": 0,
                "outcome": "open",
                "detected_setup": decision.get("detected_setup"),
                "scores": decision.get("scores", {}),
                "criteria": decision.get("criteria", {}),
                "htf_context": decision.get("htf_context", {}),
            }
            trades.append(trade)
            continue

        # Calculate P&L (simplified - would need actual close data)
        # For now, mark as "pending" if still open
        trade = {
            "symbol": symbol,
            "side": side,
            "entry": decision["trade_levels"].get("entry"),
            "exit": None,  # Would need to fetch from closed positions
            "pnl": 0,
            "pnl_pct": 0,
            "outcome": "pending",
            "detected_setup": decision.get("detected_setup"),
            "scores": decision.get("scores", {}),
            "criteria": decision.get("criteria", {}),
            "htf_context": decision.get("htf_context", {}),
        }
        trades.append(trade)

    return trades


def get_closed_trades_from_journal(days_back: int = 30) -> list[dict]:
    """
    Get closed trades by parsing trade journal entries.
    Looks for close actions and matches them with original entry.
    """
    trades_dir = JOURNAL_DIR / "trades"
    decisions_dir = JOURNAL_DIR / "decisions"

    cutoff = datetime.now(ET) - timedelta(days=days_back)

    # Find all close actions
    closed_positions = []
    for f in sorted(trades_dir.glob("*_close_*.json"), reverse=True):
        try:
            timestamp_str = "_".join(f.stem.split("_")[:2])
            trade_time = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
            trade_time = trade_time.replace(tzinfo=ET)

            if trade_time < cutoff:
                continue

            with open(f, "r") as fh:
                close_data = json.load(fh)
                closed_positions.append(close_data)
        except Exception as e:
            continue

    print(f"  📊 Found {len(closed_positions)} closed positions in last {days_back} days")

    # Match closes with their original entries
    trades = []
    for close_data in closed_positions:
        symbol = close_data.get("symbol")
        pnl = close_data.get("pnl", 0)

        # Find the original order_placed decision
        # Search backwards from close time
        decision = None
        for f in sorted(decisions_dir.glob(f"*_order_placed_{symbol}.json"), reverse=True):
            with open(f, "r") as fh:
                d = json.load(fh)
                # Simple heuristic: closest order_placed before close
                decision = d
                break

        if not decision:
            continue

        outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

        trade = {
            "symbol": symbol,
            "pnl": pnl,
            "outcome": outcome,
            "detected_setup": decision.get("detected_setup"),
            "scores": decision.get("scores", {}),
            "criteria": decision.get("criteria", {}),
            "htf_context": decision.get("htf_context", {}),
            "timestamp": close_data.get("logged_at"),
        }
        trades.append(trade)

    return trades


# ─── Performance Analysis ─────────────────────────────────────────────────────

def analyze_criteria_performance(trades: list[dict]) -> dict:
    """
    Correlate each criterion with win/loss outcomes.

    Returns dict with:
      - criterion_name: {
          "present_wins": count,
          "present_losses": count,
          "absent_wins": count,
          "absent_losses": count,
          "win_rate_when_present": float,
          "win_rate_when_absent": float,
          "correlation": float (-1 to 1),
          "current_weight": int,
          "suggested_adjustment": float,
        }
    """
    completed_trades = [t for t in trades if t["outcome"] in ("win", "loss")]

    if len(completed_trades) < MIN_TRADES_TO_LEARN:
        print(f"  ℹ Only {len(completed_trades)} completed trades. Need {MIN_TRADES_TO_LEARN} to adjust weights.")
        return {}

    analysis = {}

    for criterion in SCORE_CRITERIA.keys():
        present_wins = 0
        present_losses = 0
        absent_wins = 0
        absent_losses = 0

        for trade in completed_trades:
            criteria = trade.get("criteria", {})
            is_present = criteria.get(criterion, False)
            is_win = trade["outcome"] == "win"

            if is_present:
                if is_win:
                    present_wins += 1
                else:
                    present_losses += 1
            else:
                if is_win:
                    absent_wins += 1
                else:
                    absent_losses += 1

        total_present = present_wins + present_losses
        total_absent = absent_wins + absent_losses

        win_rate_present = present_wins / total_present if total_present > 0 else 0
        win_rate_absent = absent_wins / total_absent if total_absent > 0 else 0

        # Correlation: positive if criterion improves win rate
        correlation = win_rate_present - win_rate_absent

        # Suggested adjustment based on correlation
        # If criterion correlates positively with wins, increase weight
        # If negative, decrease weight
        suggested_adjustment = correlation * 100  # Scale to weight range

        analysis[criterion] = {
            "present_wins": present_wins,
            "present_losses": present_losses,
            "absent_wins": absent_wins,
            "absent_losses": absent_losses,
            "win_rate_when_present": round(win_rate_present, 3),
            "win_rate_when_absent": round(win_rate_absent, 3),
            "correlation": round(correlation, 3),
            "current_weight": SCORE_CRITERIA[criterion],
            "suggested_adjustment": round(suggested_adjustment, 1),
        }

    return analysis


# ─── Weight Adjustment ────────────────────────────────────────────────────────

def adjust_weights(analysis: dict, current_weights: dict) -> dict:
    """
    Apply learning rate to gradually adjust weights based on performance.
    Uses exponential moving average to smooth changes.

    new_weight = current_weight + (learning_rate × suggested_adjustment)
    """
    new_weights = dict(current_weights["criteria_weights"])

    for criterion, stats in analysis.items():
        current = new_weights[criterion]
        correlation = stats["correlation"]
        win_rate_present = stats["win_rate_when_present"]

        # Only increase weight if criterion has good win rate when present
        if correlation > 0 and win_rate_present >= CONFIDENCE_THRESHOLD:
            adjustment = stats["suggested_adjustment"] * LEARNING_RATE
            new_weight = current + adjustment
        elif correlation < 0:
            # Decrease weight if negatively correlated
            adjustment = stats["suggested_adjustment"] * LEARNING_RATE
            new_weight = current + adjustment
        else:
            new_weight = current

        # Enforce bounds
        new_weight = max(MIN_WEIGHT, min(MAX_WEIGHT, new_weight))
        new_weights[criterion] = round(new_weight)

    return new_weights


# ─── Reporting ────────────────────────────────────────────────────────────────

def generate_review_report(trades: list[dict], analysis: dict,
                          old_weights: dict, new_weights: dict) -> str:
    """Generate markdown report of daily review."""
    today = datetime.now(ET).strftime("%Y-%m-%d")

    completed = [t for t in trades if t["outcome"] in ("win", "loss")]
    wins = [t for t in completed if t["outcome"] == "win"]
    losses = [t for t in completed if t["outcome"] == "loss"]

    win_rate = len(wins) / len(completed) if completed else 0
    total_pnl = sum(t.get("pnl", 0) for t in completed)

    report = f"""# Daily Review - {today}

## Performance Summary

- **Trades Completed:** {len(completed)}
- **Wins:** {len(wins)}
- **Losses:** {len(losses)}
- **Win Rate:** {win_rate:.1%}
- **Total P&L:** ${total_pnl:.2f}

## Criteria Performance Analysis

| Criterion | Win Rate (Present) | Win Rate (Absent) | Correlation | Current Weight | New Weight | Change |
|-----------|-------------------|-------------------|-------------|----------------|------------|--------|
"""

    for criterion in sorted(analysis.keys()):
        stats = analysis[criterion]
        old_w = old_weights["criteria_weights"][criterion]
        new_w = new_weights[criterion]
        change = new_w - old_w
        change_str = f"+{change}" if change > 0 else f"{change}" if change != 0 else "—"

        report += (f"| {criterion} | {stats['win_rate_when_present']:.1%} | "
                  f"{stats['win_rate_when_absent']:.1%} | {stats['correlation']:+.3f} | "
                  f"{old_w} | {new_w} | {change_str} |\n")

    report += f"""
## Weight Changes Summary

"""

    changes = []
    for criterion in sorted(analysis.keys()):
        old_w = old_weights["criteria_weights"][criterion]
        new_w = new_weights[criterion]
        if old_w != new_w:
            change = new_w - old_w
            changes.append(f"- **{criterion}**: {old_w} → {new_w} ({change:+d})")

    if changes:
        report += "\n".join(changes)
    else:
        report += "No weight changes (insufficient correlation or below confidence threshold)"

    report += f"""

## Learning Parameters

- Learning Rate: {LEARNING_RATE}
- Confidence Threshold: {CONFIDENCE_THRESHOLD}
- Min Trades to Learn: {MIN_TRADES_TO_LEARN}
- Weight Bounds: [{MIN_WEIGHT}, {MAX_WEIGHT}]

## Trades Analyzed

"""

    for trade in completed:
        outcome_emoji = "✓" if trade["outcome"] == "win" else "✗"
        pnl = trade.get("pnl", 0)
        report += (f"- {outcome_emoji} {trade['symbol']} {trade.get('detected_setup', 'unknown')} "
                  f"(P&L: ${pnl:.2f})\n")

    return report


def save_review_report(report: str):
    """Save review report to disk."""
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ET).strftime("%Y-%m-%d")
    report_file = REVIEWS_DIR / f"review_{today}.md"

    with open(report_file, "w") as f:
        f.write(report)

    print(f"  📄 Saved review report to {report_file}")


# ─── Main Review Process ──────────────────────────────────────────────────────

def run_daily_review():
    """Execute the full daily review and learning process."""
    print(f"\n{'='*72}")
    print(f"  DAILY REVIEW & LEARNING")
    print(f"  {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")
    print(f"{'='*72}\n")

    # Check if market is closed
    try:
        clock = api.get_clock()
        if clock.is_open:
            print(f"  ⚠ Market is still open. Review should run after close.")
            print(f"    Next close: {clock.next_close}")
            return
    except Exception as e:
        print(f"  ⚠ Could not check market status: {e}")

    # Load current learned weights
    current_weights = load_learned_weights()
    print(f"  📖 Loaded learned weights (v{current_weights['meta']['version']})")
    if current_weights['meta']['last_updated']:
        print(f"     Last updated: {current_weights['meta']['last_updated']}")

    # Collect trade data from last 30 days (to have enough data)
    trades = get_closed_trades_from_journal(days_back=30)

    if not trades:
        print(f"  ℹ No completed trades to analyze yet.")
        return

    # Analyze criteria performance
    print(f"\n  🔍 Analyzing criteria performance...")
    analysis = analyze_criteria_performance(trades)

    if not analysis:
        print(f"  ℹ Not enough completed trades to adjust weights yet.")
        print(f"     Need at least {MIN_TRADES_TO_LEARN} completed trades.")
        return

    # Adjust weights
    print(f"\n  ⚙️  Adjusting weights based on performance...")
    new_criteria_weights = adjust_weights(analysis, current_weights)

    # Update weights dict
    updated_weights = {
        "criteria_weights": new_criteria_weights,
        "weekly_liquidity_bonus": current_weights["weekly_liquidity_bonus"],
        "monthly_liquidity_bonus": current_weights["monthly_liquidity_bonus"],
        "meta": {
            "version": current_weights["meta"]["version"] + 1,
            "last_updated": datetime.now(ET).isoformat(),
            "total_trades_analyzed": current_weights["meta"]["total_trades_analyzed"] + len(trades),
            "days_learning": current_weights["meta"]["days_learning"] + 1,
        }
    }

    # Generate report
    print(f"\n  📊 Generating review report...")
    report = generate_review_report(trades, analysis, current_weights, new_criteria_weights)
    save_review_report(report)

    # Print report to console
    print(f"\n{report}")

    # Save updated weights
    save_learned_weights(updated_weights)

    print(f"\n{'='*72}")
    print(f"  REVIEW COMPLETE")
    print(f"  Weights updated for tomorrow's trading")
    print(f"{'='*72}\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Daily review and learning system")
    parser.add_argument("--reset", action="store_true",
                       help="Reset weights to defaults")
    args = parser.parse_args()

    if args.reset:
        if WEIGHTS_FILE.exists():
            WEIGHTS_FILE.unlink()
            print("✓ Reset learned weights to defaults")
        else:
            print("ℹ No learned weights file found")
    else:
        run_daily_review()
