#!/usr/bin/env python3
"""
View Learning History

Display the evolution of learned weights over time with detailed reasoning.

Usage:
  python3 view_learning_history.py               # Show all changes
  python3 view_learning_history.py --recent 5    # Show last 5 days
  python3 view_learning_history.py --criterion liquidity_sweep  # Track one criterion
"""

import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LEARNING_HISTORY_FILE = Path(__file__).parent / "journal" / "learning_history.jsonl"


def load_learning_history():
    """Load all learning history entries from JSONL file."""
    if not LEARNING_HISTORY_FILE.exists():
        return []

    entries = []
    with open(LEARNING_HISTORY_FILE, "r") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    return entries


def show_all_changes(recent_days=None):
    """Display all weight changes chronologically."""
    entries = load_learning_history()

    if not entries:
        print("No learning history found yet.")
        print(f"History will be created after first daily review.")
        return

    if recent_days:
        entries = entries[-recent_days:]

    print(f"\n{'='*80}")
    print(f"  LEARNING HISTORY")
    print(f"  {len(entries)} review(s) recorded")
    print(f"{'='*80}\n")

    for entry in entries:
        date = entry["date"]
        version = entry["version"]
        num_changes = len(entry["changes"])
        num_trades = entry["total_trades_analyzed"]

        print(f"📅 {date} (Version {version}) — {num_changes} weight change(s), {num_trades} trades analyzed\n")

        if entry["changes"]:
            for change in entry["changes"]:
                criterion = change["criterion"]
                old_w = change["old_weight"]
                new_w = change["new_weight"]
                delta = change["change"]
                reason = change["reason"]

                direction = "↑" if delta > 0 else "↓"
                print(f"  {direction} {criterion}: {old_w} → {new_w} ({delta:+d})")
                print(f"     {reason}")
                print()
        else:
            print("  No changes this review.\n")

        print("-" * 80 + "\n")


def track_criterion(criterion_name):
    """Track the evolution of a specific criterion over time."""
    entries = load_learning_history()

    if not entries:
        print("No learning history found yet.")
        return

    print(f"\n{'='*80}")
    print(f"  TRACKING: {criterion_name}")
    print(f"{'='*80}\n")

    changes_found = []
    for entry in entries:
        for change in entry["changes"]:
            if change["criterion"] == criterion_name:
                changes_found.append({
                    "date": entry["date"],
                    "version": entry["version"],
                    **change
                })

    if not changes_found:
        print(f"No changes recorded for '{criterion_name}' yet.")
        return

    print(f"Weight Evolution:\n")

    for i, change in enumerate(changes_found):
        date = change["date"]
        old_w = change["old_weight"]
        new_w = change["new_weight"]
        delta = change["change"]
        correlation = change["correlation"]
        present_record = change["present_record"]
        absent_record = change["absent_record"]

        direction = "↑" if delta > 0 else "↓"
        print(f"{i+1}. {date}: {old_w} → {new_w} ({direction}{abs(delta)})")
        print(f"   Present: {present_record}, Absent: {absent_record}")
        print(f"   Correlation: {correlation:+.3f}")
        print()


def show_summary():
    """Show a summary of all weight changes across all criteria."""
    entries = load_learning_history()

    if not entries:
        print("No learning history found yet.")
        return

    # Aggregate changes by criterion
    criterion_changes = {}

    for entry in entries:
        for change in entry["changes"]:
            criterion = change["criterion"]
            if criterion not in criterion_changes:
                criterion_changes[criterion] = {
                    "changes": [],
                    "first_weight": change["old_weight"],
                    "last_weight": change["new_weight"],
                }
            else:
                criterion_changes[criterion]["last_weight"] = change["new_weight"]

            criterion_changes[criterion]["changes"].append(change)

    print(f"\n{'='*80}")
    print(f"  LEARNING SUMMARY")
    print(f"  {len(entries)} review(s) over {len(criterion_changes)} criteria")
    print(f"{'='*80}\n")

    for criterion in sorted(criterion_changes.keys()):
        data = criterion_changes[criterion]
        first = data["first_weight"]
        last = data["last_weight"]
        total_change = last - first
        num_changes = len(data["changes"])

        direction = "↑" if total_change > 0 else "↓" if total_change < 0 else "→"
        print(f"{direction} {criterion}: {first} → {last} ({total_change:+d}) over {num_changes} adjustment(s)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="View learning history")
    parser.add_argument("--recent", type=int, metavar="N",
                       help="Show only the last N reviews")
    parser.add_argument("--criterion", type=str, metavar="NAME",
                       help="Track a specific criterion over time")
    parser.add_argument("--summary", action="store_true",
                       help="Show summary of all changes")

    args = parser.parse_args()

    if args.criterion:
        track_criterion(args.criterion)
    elif args.summary:
        show_summary()
    else:
        show_all_changes(recent_days=args.recent)
