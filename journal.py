#!/usr/bin/env python3
"""
Trade journal — persists every analysis and trade to disk as JSON.

Directory layout:
    journal/
        analyses/   YYYY-MM-DD_HHMMSS_SPY.json
        trades/     YYYY-MM-DD_HHMMSS_buy_SPY.json
"""

import json
import os
from datetime import datetime
from pathlib import Path

JOURNAL_DIR = Path(__file__).parent / "journal"
ANALYSES_DIR = JOURNAL_DIR / "analyses"
TRADES_DIR = JOURNAL_DIR / "trades"


def _ensure_dirs():
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _write(directory: Path, filename: str, data: dict):
    _ensure_dirs()
    path = directory / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  📓 Saved → {path}")
    return str(path)


def log_analysis(analysis: dict) -> str:
    """Write a full analysis dict to journal/analyses/."""
    sym = analysis.get("symbol", "UNK")
    tf = analysis.get("timeframe", "")
    filename = f"{_timestamp()}_{sym}_{tf}.json"
    return _write(ANALYSES_DIR, filename, analysis)


def log_trade(trade: dict, action: str = "order") -> str:
    """
    Write a trade event to journal/trades/.

    action: "buy", "sell", "close", "cancel", etc.
    """
    sym = trade.get("symbol", "UNK")
    side = trade.get("side", action)
    filename = f"{_timestamp()}_{side}_{sym}.json"
    entry = {
        "logged_at": datetime.now().isoformat(),
        "action": action,
        **trade,
    }
    return _write(TRADES_DIR, filename, entry)


def list_entries(kind: str = "all", symbol: str = None, limit: int = 20):
    """
    List recent journal entries.

    Args:
        kind:   "analyses", "trades", or "all"
        symbol: filter by symbol (optional)
        limit:  max entries to show
    """
    _ensure_dirs()
    dirs = []
    if kind in ("analyses", "all"):
        dirs.append(("ANALYSIS", ANALYSES_DIR))
    if kind in ("trades", "all"):
        dirs.append(("TRADE", TRADES_DIR))

    entries = []
    for label, d in dirs:
        for f in sorted(d.glob("*.json"), reverse=True):
            if symbol and symbol.upper() not in f.name.upper():
                continue
            with open(f) as fh:
                data = json.load(fh)
            entries.append((label, f.name, data))

    entries = entries[:limit]

    if not entries:
        print("\n  Journal is empty.")
        return []

    print(f"\n  ── Journal ({len(entries)} entries) ──")
    for label, name, data in entries:
        if label == "ANALYSIS":
            rec = data.get("recommendation", "—")
            conf = data.get("confidence", "—")
            setup = data.get("detected_setup", "—")
            print(f"  [{label}]  {name}")
            print(f"           rec={rec}  confidence={conf}  setup={setup}")
        else:
            side = data.get("side", data.get("action", "—"))
            sym = data.get("symbol", "—")
            qty = data.get("qty", "—")
            status = data.get("status", "—")
            print(f"  [{label}]   {name}")
            print(f"           {side} {qty} {sym}  status={status}")

    return entries
