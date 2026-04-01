#!/usr/bin/env python3
"""
Weekly Review & Learning System

Analyzes completed trades from the past week, calculates performance metrics,
and adjusts A+ scoring criteria weights based on what's actually working.

Process:
  1. Analyze all trades from last 30 days
  2. Correlate criteria with win/loss outcomes
  3. Adjust weights using exponential moving average
  4. Save learned weights for next week
  5. Generate performance report

Run automatically every Saturday or manually:
  python3 daily_review.py
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from src.alpaca_trader import api, get_recent_fills, ALLOWED_SYMBOLS
from src.memories import SCORE_CRITERIA, WEEKLY_LIQUIDITY_BONUS, MONTHLY_LIQUIDITY_BONUS
from src.weekly_context import generate_weekly_context, save_weekly_context

ET = ZoneInfo("America/New_York")
JOURNAL_DIR = Path(__file__).parent / "journal"
WEIGHTS_FILE = Path(__file__).parent / "learned_weights.json"
REVIEWS_DIR = Path(__file__).parent / "journal" / "reviews"
LEARNING_HISTORY_FILE = Path(__file__).parent / "journal" / "learning_history.jsonl"

# Learning parameters
LEARNING_RATE = 0.15  # How fast to adjust weights (0.1-0.3 recommended)
MIN_TRADES_TO_LEARN = 3  # Minimum trades before adjusting weights
MIN_WEIGHT = 2  # Minimum weight value
MAX_WEIGHT = 30  # Maximum weight value
CONFIDENCE_THRESHOLD = 0.6  # Minimum win rate to increase weight (60%)


# ─── Load Learned Weights ─────────────────────────────────────────────────────

def load_learned_weights() -> dict:
    """
    Load learned weights from disk, or return defaults if none exist.

    Returns dict with:
      - criteria_weights: {
            "global": {criterion: weight},  # Fallback weights
            "Asia": {criterion: weight},
            "London": {criterion: weight},
            "NY_AM": {criterion: weight},
            "NY_Lunch": {criterion: weight},
            "NY_PM": {criterion: weight}
        }
      - weekly_liquidity_bonus: {proximity: bonus}
      - monthly_liquidity_bonus: {proximity: bonus}
      - meta: learning stats
    """
    if not WEIGHTS_FILE.exists():
        # Initialize with same weights for all killzones
        default_weights = dict(SCORE_CRITERIA)
        return {
            "criteria_weights": {
                "global": default_weights.copy(),
                "Asia": default_weights.copy(),
                "London": default_weights.copy(),
                "NY_AM": default_weights.copy(),
                "NY_Lunch": default_weights.copy(),
                "NY_PM": default_weights.copy(),
            },
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
        weights = json.load(f)

        # Backward compatibility: migrate old flat structure to killzone structure
        if "criteria_weights" in weights and isinstance(weights["criteria_weights"], dict):
            if "global" not in weights["criteria_weights"]:
                # Old format detected, migrate to new format
                old_weights = weights["criteria_weights"]
                weights["criteria_weights"] = {
                    "global": old_weights.copy(),
                    "Asia": old_weights.copy(),
                    "London": old_weights.copy(),
                    "NY_AM": old_weights.copy(),
                    "NY_Lunch": old_weights.copy(),
                    "NY_PM": old_weights.copy(),
                }
                print("  🔄 Migrated weights to killzone-specific structure")

        return weights


def save_learned_weights(weights: dict):
    """Persist learned weights to disk."""
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=2)
    print(f"  💾 Saved learned weights to {WEIGHTS_FILE}")


def log_weight_changes_by_killzone(killzone_analysis: dict, old_weights: dict,
                                   new_weights: dict, num_trades: int):
    """
    Append killzone-specific weight change details to learning history JSONL file.

    Tracks what changed, when, and why for each weight adjustment per killzone.
    """
    LEARNING_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(ET).isoformat()
    killzone_changes = {}

    for killzone, analysis in killzone_analysis.items():
        changes = []
        for criterion, stats in analysis.items():
            old_w = old_weights["criteria_weights"][killzone][criterion]
            new_w = new_weights[killzone][criterion]

            if old_w != new_w:
                change = new_w - old_w

                # Build reasoning statement
                win_rate_present = stats["win_rate_when_present"]
                win_rate_absent = stats["win_rate_when_absent"]
                correlation = stats["correlation"]
                present_wins = stats["present_wins"]
                present_losses = stats["present_losses"]
                absent_wins = stats["absent_wins"]
                absent_losses = stats["absent_losses"]

                # Determine reasoning
                if change > 0:
                    reason = (f"Increased in {killzone} because win rate was {win_rate_present:.0%} when present "
                             f"({present_wins}W/{present_losses}L) vs {win_rate_absent:.0%} when absent "
                             f"({absent_wins}W/{absent_losses}L). Correlation: {correlation:+.3f}")
                elif change < 0:
                    reason = (f"Decreased in {killzone} because win rate was {win_rate_present:.0%} when present "
                             f"({present_wins}W/{present_losses}L) vs {win_rate_absent:.0%} when absent "
                             f"({absent_wins}W/{absent_losses}L). Correlation: {correlation:+.3f}")
                else:
                    continue

                change_entry = {
                    "criterion": criterion,
                    "killzone": killzone,
                    "old_weight": old_w,
                    "new_weight": new_w,
                    "change": change,
                    "win_rate_when_present": win_rate_present,
                    "win_rate_when_absent": win_rate_absent,
                    "correlation": correlation,
                    "present_record": f"{present_wins}W-{present_losses}L",
                    "absent_record": f"{absent_wins}W-{absent_losses}L",
                    "reason": reason,
                }
                changes.append(change_entry)

        if changes:
            killzone_changes[killzone] = changes

    if killzone_changes:
        total_changes = sum(len(changes) for changes in killzone_changes.values())
        log_entry = {
            "timestamp": timestamp,
            "date": datetime.now(ET).strftime("%Y-%m-%d"),
            "version": old_weights["meta"]["version"] + 1,
            "total_trades_analyzed": num_trades,
            "killzone_changes": killzone_changes,
        }

        # Append to JSONL file
        with open(LEARNING_HISTORY_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        print(f"  📝 Logged {total_changes} weight changes across {len(killzone_changes)} killzones")


def log_weight_changes(analysis: dict, old_weights: dict, new_weights: dict,
                       num_trades: int):
    """
    Append weight change details to learning history JSONL file.

    Tracks what changed, when, and why for each weight adjustment.
    Each line is a JSON object with timestamp and detailed reasoning.

    NOTE: This is the legacy function for flat weight structure.
    """
    LEARNING_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(ET).isoformat()

    changes = []
    for criterion, stats in analysis.items():
        old_w = old_weights["criteria_weights"][criterion]
        new_w = new_weights[criterion]

        if old_w != new_w:
            change = new_w - old_w

            # Build reasoning statement
            win_rate_present = stats["win_rate_when_present"]
            win_rate_absent = stats["win_rate_when_absent"]
            correlation = stats["correlation"]
            present_wins = stats["present_wins"]
            present_losses = stats["present_losses"]
            absent_wins = stats["absent_wins"]
            absent_losses = stats["absent_losses"]

            total_present = present_wins + present_losses
            total_absent = absent_wins + absent_losses

            # Determine reasoning
            if change > 0:
                reason = (f"Increased because win rate was {win_rate_present:.0%} when present "
                         f"({present_wins}W/{present_losses}L) vs {win_rate_absent:.0%} when absent "
                         f"({absent_wins}W/{absent_losses}L) over {num_trades} trades. "
                         f"Correlation: {correlation:+.3f}")
            elif change < 0:
                reason = (f"Decreased because win rate was {win_rate_present:.0%} when present "
                         f"({present_wins}W/{present_losses}L) vs {win_rate_absent:.0%} when absent "
                         f"({absent_wins}W/{absent_losses}L) over {num_trades} trades. "
                         f"Correlation: {correlation:+.3f}")
            else:
                continue  # No change, skip

            change_entry = {
                "criterion": criterion,
                "old_weight": old_w,
                "new_weight": new_w,
                "change": change,
                "win_rate_when_present": win_rate_present,
                "win_rate_when_absent": win_rate_absent,
                "correlation": correlation,
                "present_record": f"{present_wins}W-{present_losses}L",
                "absent_record": f"{absent_wins}W-{absent_losses}L",
                "trades_analyzed": num_trades,
                "reason": reason,
            }
            changes.append(change_entry)

    if changes:
        log_entry = {
            "timestamp": timestamp,
            "date": datetime.now(ET).strftime("%Y-%m-%d"),
            "version": old_weights["meta"]["version"] + 1,
            "total_trades_analyzed": num_trades,
            "changes": changes,
        }

        # Append to JSONL file
        with open(LEARNING_HISTORY_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        print(f"  📝 Logged {len(changes)} weight changes to learning history")


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
            "killzone": decision.get("killzone", "unknown"),
            "timestamp": close_data.get("logged_at"),
        }
        trades.append(trade)

    return trades


# ─── Performance Analysis ─────────────────────────────────────────────────────

def analyze_criteria_by_killzone(trades: list[dict]) -> dict:
    """
    Analyze criteria performance separately for each killzone.

    Returns dict with:
      {
        "Asia": {criterion: analysis_stats},
        "London": {criterion: analysis_stats},
        ...
      }
    """
    killzone_labels = ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]
    killzone_analysis = {}

    for killzone in killzone_labels:
        kz_trades = [t for t in trades if t.get("killzone") == killzone]
        if kz_trades:
            analysis = analyze_criteria_performance(kz_trades)
            if analysis:
                killzone_analysis[killzone] = analysis

    return killzone_analysis


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

def adjust_weights_by_killzone(killzone_analysis: dict, current_weights: dict) -> dict:
    """
    Apply learning rate to adjust weights for each killzone separately.

    Args:
        killzone_analysis: {killzone: {criterion: stats}}
        current_weights: Current weight structure with killzone-specific weights

    Returns:
        New killzone-specific weights: {killzone: {criterion: weight}}
    """
    new_weights = {}

    for killzone in ["global", "Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]:
        if killzone == "global":
            # Global weights are average of all killzone weights
            continue

        if killzone in killzone_analysis:
            # Adjust based on this killzone's performance
            analysis = killzone_analysis[killzone]
            current_kz_weights = current_weights["criteria_weights"][killzone]
            new_weights[killzone] = {}

            for criterion in SCORE_CRITERIA.keys():
                if criterion in analysis:
                    stats = analysis[criterion]
                    current = current_kz_weights[criterion]
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
                    new_weights[killzone][criterion] = round(new_weight)
                else:
                    # No data for this criterion in this killzone, keep current
                    new_weights[killzone][criterion] = current_kz_weights[criterion]
        else:
            # No trades in this killzone, keep current weights
            new_weights[killzone] = dict(current_weights["criteria_weights"][killzone])

    # Calculate global weights as average across all killzones
    new_weights["global"] = {}
    for criterion in SCORE_CRITERIA.keys():
        avg_weight = sum(new_weights[kz][criterion] for kz in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]) / 5
        new_weights["global"][criterion] = round(avg_weight)

    return new_weights


def adjust_weights(analysis: dict, current_weights: dict) -> dict:
    """
    Apply learning rate to gradually adjust weights based on performance.
    Uses exponential moving average to smooth changes.

    new_weight = current_weight + (learning_rate × suggested_adjustment)

    NOTE: This is the legacy function for flat weight structure.
    Use adjust_weights_by_killzone() for killzone-specific learning.
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

## Detailed Change Log

"""

    detailed_changes = []
    for criterion in sorted(analysis.keys()):
        stats = analysis[criterion]
        old_w = old_weights["criteria_weights"][criterion]
        new_w = new_weights[criterion]

        if old_w != new_w:
            change = new_w - old_w
            win_rate_present = stats["win_rate_when_present"]
            win_rate_absent = stats["win_rate_when_absent"]
            correlation = stats["correlation"]
            present_wins = stats["present_wins"]
            present_losses = stats["present_losses"]
            absent_wins = stats["absent_wins"]
            absent_losses = stats["absent_losses"]

            direction = "Increased" if change > 0 else "Decreased"
            detailed_changes.append(
                f"### {criterion}: {old_w} → {new_w} ({change:+d})\n\n"
                f"**{direction}** because:\n"
                f"- Win rate when present: **{win_rate_present:.0%}** "
                f"({present_wins}W/{present_losses}L)\n"
                f"- Win rate when absent: **{win_rate_absent:.0%}** "
                f"({absent_wins}W/{absent_losses}L)\n"
                f"- Correlation: **{correlation:+.3f}** "
                f"({'positive' if correlation > 0 else 'negative'})\n"
                f"- Trades analyzed: {len([t for t in trades if t['outcome'] in ('win', 'loss')])}\n"
            )

    if detailed_changes:
        report += "\n".join(detailed_changes)
    else:
        report += "No weight changes this review.\n"

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


def generate_review_report_by_killzone(trades: list[dict], killzone_analysis: dict,
                                        old_weights: dict, new_weights: dict,
                                        weekly_context: dict | None = None) -> str:
    """Generate markdown report of weekly review with killzone-specific analysis."""
    today = datetime.now(ET).strftime("%Y-%m-%d")

    completed = [t for t in trades if t["outcome"] in ("win", "loss")]
    wins = [t for t in completed if t["outcome"] == "win"]
    losses = [t for t in completed if t["outcome"] == "loss"]

    win_rate = len(wins) / len(completed) if completed else 0
    total_pnl = sum(t.get("pnl", 0) for t in completed)

    report = f"""# Weekly Review - {today}

## Performance Summary

- **Trades Completed:** {len(completed)}
- **Wins:** {len(wins)}
- **Losses:** {len(losses)}
- **Win Rate:** {win_rate:.1%}
- **Total P&L:** ${total_pnl:.2f}

## Weekly Market Context

"""

    # Add weekly context if available
    if weekly_context:
        fomc = weekly_context.get("fomc", {})
        spy = weekly_context.get("spy", {})
        qqq = weekly_context.get("qqq", {})
        vix = weekly_context.get("vix", {})
        regime = weekly_context.get("regime", {})

        report += f"""### FOMC Calendar
- **{fomc.get('note', 'N/A')}**
- Impact: {fomc.get('impact', 'none')}

### Market Trend Analysis

**SPY:**
- Price: ${spy.get('price', 'N/A')} | Trend: {spy.get('trend', 'N/A')}
- MA-50: ${spy.get('ma_50', 'N/A')} ({spy.get('distance_from_50', 0):+.2f}%)
- MA-200: ${spy.get('ma_200', 'N/A')} ({spy.get('distance_from_200', 0):+.2f}%)
- Momentum: {spy.get('momentum', 'N/A')}

**QQQ:**
- Price: ${qqq.get('price', 'N/A')} | Trend: {qqq.get('trend', 'N/A')}
- MA-50: ${qqq.get('ma_50', 'N/A')} ({qqq.get('distance_from_50', 0):+.2f}%)
- MA-200: ${qqq.get('ma_200', 'N/A')} ({qqq.get('distance_from_200', 0):+.2f}%)
- Momentum: {qqq.get('momentum', 'N/A')}

### Fear Gauge
- **VIX:** {vix.get('vix', 'N/A')} ({vix.get('classification', 'N/A')})
- {vix.get('note', 'N/A')}

### Market Regime
- **{regime.get('regime', 'N/A')}**
- {regime.get('description', 'N/A')}
- Confidence: {regime.get('confidence', 0):.0%}

**Scoring Modifiers for this week:**
"""
        modifiers = regime.get('scoring_modifiers', {})
        for key, value in modifiers.items():
            report += f"- {key}: {value}\n"

        report += "\n"

    else:
        report += "Weekly context analysis not available.\n\n"

    report += f"""## Killzone Breakdown

"""

    # Killzone performance table
    for killzone in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]:
        kz_trades = [t for t in trades if t.get("killzone") == killzone]
        if kz_trades:
            kz_completed = [t for t in kz_trades if t["outcome"] in ("win", "loss")]
            kz_wins = [t for t in kz_completed if t["outcome"] == "win"]
            kz_losses = [t for t in kz_completed if t["outcome"] == "loss"]
            kz_win_rate = len(kz_wins) / len(kz_completed) if kz_completed else 0
            kz_pnl = sum(t.get("pnl", 0) for t in kz_completed)

            report += f"""### {killzone}
- Trades: {len(kz_completed)} ({len(kz_wins)}W/{len(kz_losses)}L)
- Win Rate: {kz_win_rate:.1%}
- P&L: ${kz_pnl:.2f}

"""

    report += f"""## Weight Changes by Killzone

"""

    # Show weight changes for each killzone
    for killzone in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]:
        if killzone in killzone_analysis:
            analysis = killzone_analysis[killzone]
            changes = []

            for criterion in sorted(analysis.keys()):
                old_w = old_weights["criteria_weights"][killzone][criterion]
                new_w = new_weights[killzone][criterion]
                if old_w != new_w:
                    change = new_w - old_w
                    changes.append(f"  - **{criterion}**: {old_w} → {new_w} ({change:+d})")

            if changes:
                report += f"### {killzone}\n\n"
                report += "\n".join(changes)
                report += "\n\n"

    if not any(killzone in killzone_analysis for killzone in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]):
        report += "No weight changes this review.\n\n"

    # Detailed change log
    report += f"""## Detailed Change Log by Killzone

"""

    for killzone in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]:
        if killzone in killzone_analysis:
            analysis = killzone_analysis[killzone]
            killzone_changes = []

            for criterion in sorted(analysis.keys()):
                stats = analysis[criterion]
                old_w = old_weights["criteria_weights"][killzone][criterion]
                new_w = new_weights[killzone][criterion]

                if old_w != new_w:
                    change = new_w - old_w
                    win_rate_present = stats["win_rate_when_present"]
                    win_rate_absent = stats["win_rate_when_absent"]
                    correlation = stats["correlation"]
                    present_wins = stats["present_wins"]
                    present_losses = stats["present_losses"]
                    absent_wins = stats["absent_wins"]
                    absent_losses = stats["absent_losses"]

                    direction = "Increased" if change > 0 else "Decreased"
                    killzone_changes.append(
                        f"#### {criterion}: {old_w} → {new_w} ({change:+d})\n\n"
                        f"**{direction}** in {killzone} because:\n"
                        f"- Win rate when present: **{win_rate_present:.0%}** "
                        f"({present_wins}W/{present_losses}L)\n"
                        f"- Win rate when absent: **{win_rate_absent:.0%}** "
                        f"({absent_wins}W/{absent_losses}L)\n"
                        f"- Correlation: **{correlation:+.3f}** "
                        f"({'positive' if correlation > 0 else 'negative'})\n"
                    )

            if killzone_changes:
                report += f"### {killzone}\n\n"
                report += "\n".join(killzone_changes)
                report += "\n"

    if not any(killzone in killzone_analysis for killzone in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]):
        report += "No weight changes this review.\n\n"

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
        killzone = trade.get("killzone", "unknown")
        report += (f"- {outcome_emoji} {trade['symbol']} {trade.get('detected_setup', 'unknown')} "
                  f"({killzone}) P&L: ${pnl:.2f}\n")

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
    """Execute the full weekly review and learning process."""
    print(f"\n{'='*72}")
    print(f"  WEEKLY REVIEW & LEARNING")
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

    # Generate weekly market context (FOMC, trends, VIX)
    print(f"\n")
    try:
        weekly_context = generate_weekly_context()
        save_weekly_context(weekly_context)
    except Exception as e:
        print(f"  ⚠ Weekly context analysis failed: {e}")
        weekly_context = None

    # Collect trade data from last 30 days (to have enough data)
    trades = get_closed_trades_from_journal(days_back=30)

    if not trades:
        print(f"  ℹ No completed trades to analyze yet.")
        return

    # Analyze criteria performance by killzone
    print(f"\n  🔍 Analyzing criteria performance by killzone...")
    killzone_analysis = analyze_criteria_by_killzone(trades)

    if not killzone_analysis:
        print(f"  ℹ Not enough completed trades to adjust weights yet.")
        print(f"     Need at least {MIN_TRADES_TO_LEARN} completed trades per killzone.")
        return

    # Show killzone trade distribution
    print(f"\n  📊 Trade distribution by killzone:")
    for killzone in ["Asia", "London", "NY_AM", "NY_Lunch", "NY_PM"]:
        kz_trades = [t for t in trades if t.get("killzone") == killzone]
        if kz_trades:
            wins = len([t for t in kz_trades if t["outcome"] == "win"])
            losses = len([t for t in kz_trades if t["outcome"] == "loss"])
            print(f"     {killzone:10} {len(kz_trades):2} trades ({wins}W/{losses}L)")

    # Adjust weights by killzone
    print(f"\n  ⚙️  Adjusting weights based on killzone-specific performance...")
    new_criteria_weights = adjust_weights_by_killzone(killzone_analysis, current_weights)

    # Log weight changes with detailed reasoning
    log_weight_changes_by_killzone(killzone_analysis, current_weights, new_criteria_weights, len(trades))

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
    report = generate_review_report_by_killzone(trades, killzone_analysis, current_weights, new_criteria_weights, weekly_context)
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

    parser = argparse.ArgumentParser(description="Weekly review and learning system")
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
