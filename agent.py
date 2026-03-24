#!/usr/bin/env python3
"""
Autonomous trading agent for SPY/QQQ on Alpaca paper.

Orchestrates the full loop:
  1. Pre-flight checks (market open, killzone, daily limits)
  2. Analyze both symbols via analyze.py
  3. Score each setup against A+ criteria from memories.py
  4. Enforce guardrails (position sizing, R:R, loss limits, cooldown)
  5. Execute qualifying trades via alpaca_trader.py
  6. Manage open positions (trailing stop, take-profit exits)
  7. Journal everything

Run modes:
  python agent.py              # single scan + act cycle
  python agent.py --loop       # continuous loop during market hours
  python agent.py --dry-run    # analyze only, no execution
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca_trader import (
    api,
    buy,
    sell,
    get_account,
    get_positions,
    close_position,
    get_recent_fills,
    ALLOWED_SYMBOLS,
)
from analyze import analyze
from indicator_engine import compute_atr, compute_ema, compute_vwap, compute_rsi
from journal import log_trade, log_analysis
from memories import (
    KILLZONES,
    MACRO_WINDOWS,
    SCORE_CRITERIA,
    A_PLUS_THRESHOLD,
    GUARDRAILS,
    DETECTION,
    HARD_RULES,
)

ET = ZoneInfo("America/New_York")
STATE_FILE = Path(__file__).parent / "journal" / "agent_state.json"

# ─── Time helpers ─────────────────────────────────────────────────────────────

def _now_et() -> datetime:
    return datetime.now(ET)


def _time_str() -> str:
    return _now_et().strftime("%H:%M")


def _today_str() -> str:
    return _now_et().strftime("%Y-%m-%d")


def _in_window(start: str, end: str) -> bool:
    """True if current ET time is between start and end (HH:MM strings)."""
    now = _now_et().strftime("%H:%M")
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def in_killzone() -> tuple[bool, str | None]:
    """Return (True, label) if inside any killzone, else (False, None)."""
    for kz in KILLZONES.values():
        if _in_window(kz["start"], kz["end"]):
            return True, kz["label"]
    return False, None


def in_macro_window() -> bool:
    for start, end in MACRO_WINDOWS:
        if _in_window(start, end):
            return True
    return False


def market_is_open() -> bool:
    try:
        clock = api.get_clock()
        return clock.is_open
    except Exception as e:
        print(f"  ⚠ Could not check market clock: {e}")
        return False

# ─── Persistent state (survives restarts) ─────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _get_daily_state() -> dict:
    state = _load_state()
    today = _today_str()
    if state.get("date") != today:
        state = {"date": today, "trades_taken": 0, "daily_pnl": 0.0, "last_loss_time": None}
        _save_state(state)
    return state


def _record_trade(pnl: float = 0.0):
    state = _get_daily_state()
    state["trades_taken"] = state.get("trades_taken", 0) + 1
    state["daily_pnl"] = state.get("daily_pnl", 0.0) + pnl
    if pnl < 0:
        state["last_loss_time"] = _now_et().isoformat()
    _save_state(state)


# ─── Guardrail checks ────────────────────────────────────────────────────────

def _check_daily_trade_limit() -> tuple[bool, str]:
    state = _get_daily_state()
    limit = GUARDRAILS["max_trades_per_day"]
    taken = state.get("trades_taken", 0)
    if taken >= limit:
        return False, f"Daily trade limit reached ({taken}/{limit})"
    return True, f"Trades today: {taken}/{limit}"


def _check_daily_loss_limit(equity: float) -> tuple[bool, str]:
    state = _get_daily_state()
    max_loss = equity * GUARDRAILS["daily_loss_limit_pct"]
    daily_pnl = state.get("daily_pnl", 0.0)
    if daily_pnl <= -max_loss:
        return False, f"Daily loss limit hit: ${daily_pnl:,.2f} (max -${max_loss:,.2f})"
    return True, f"Daily P&L: ${daily_pnl:,.2f} (limit -${max_loss:,.2f})"


def _check_cooldown() -> tuple[bool, str]:
    state = _get_daily_state()
    last_loss = state.get("last_loss_time")
    if not last_loss:
        return True, "No recent loss — no cooldown"
    try:
        loss_time = datetime.fromisoformat(last_loss)
        cooldown_min = GUARDRAILS["cooldown_after_loss_min"]
        resume_at = loss_time + timedelta(minutes=cooldown_min)
        if _now_et() < resume_at:
            remaining = (resume_at - _now_et()).total_seconds() / 60
            return False, f"Cooling down — {remaining:.0f} min left after last loss"
    except (ValueError, TypeError):
        pass
    return True, "Cooldown clear"


def _check_killzone() -> tuple[bool, str]:
    if not GUARDRAILS["require_killzone"]:
        return True, "Killzone check disabled"
    is_kz, label = in_killzone()
    if not is_kz:
        return False, f"Not in any killzone (current ET: {_time_str()})"
    macro = " [MACRO WINDOW]" if in_macro_window() else ""
    return True, f"In {label} killzone{macro}"


# ─── A+ Scoring ──────────────────────────────────────────────────────────────

def score_setup(analysis: dict, bars: list[dict] | None = None) -> tuple[int, dict[str, bool]]:
    """
    Score an analysis result against the A+ criteria from memories.py.
    Returns (total_score, {criterion: met_bool}).
    """
    ms = analysis["market_state"]
    setup = analysis["detected_setup"]
    side = analysis["recommendation"]
    price = ms["price"]

    checks: dict[str, bool] = {}

    checks["liquidity_sweep"] = setup in (
        "oversold_reversal", "overbought_reversal",
        "ema_pullback_long", "ema_bounce_short",
    )

    checks["market_structure_shift"] = analysis["confidence"] >= 55 and setup != "none"

    checks["fvg_present"] = (
        ms.get("atr_14") is not None
        and ms["atr_14"] > price * DETECTION["fvg_min_gap_pct"]
    )

    checks["displacement"] = (
        ms.get("atr_14") is not None
        and ms["atr_14"] > price * 0.005
    )

    checks["killzone_timing"] = in_killzone()[0]

    if side == "buy":
        checks["premium_discount"] = (
            ms.get("vwap") is not None and price < ms["vwap"]
        )
    elif side == "sell":
        checks["premium_discount"] = (
            ms.get("vwap") is not None and price > ms["vwap"]
        )
    else:
        checks["premium_discount"] = False

    checks["ema_confirmation"] = (
        ms.get("ema_9") is not None
        and ms.get("ema_21") is not None
        and (
            (side == "buy" and ms["ema_9"] > ms["ema_21"])
            or (side == "sell" and ms["ema_9"] < ms["ema_21"])
        )
    )

    checks["vwap_confluence"] = checks["premium_discount"]

    rsi = ms.get("rsi_14")
    if rsi is not None:
        if side == "buy":
            checks["rsi_not_extreme"] = rsi < 70
        elif side == "sell":
            checks["rsi_not_extreme"] = rsi > 30
        else:
            checks["rsi_not_extreme"] = 30 < rsi < 70
    else:
        checks["rsi_not_extreme"] = False

    total = sum(SCORE_CRITERIA[k] for k, met in checks.items() if met)
    return total, checks


# ─── Position sizing ─────────────────────────────────────────────────────────

def compute_position_size(equity: float, price: float, atr: float | None) -> int:
    """Shares to buy, respecting max_position_pct and ATR-based risk."""
    max_dollar = equity * GUARDRAILS["max_position_pct"]
    max_shares_by_equity = int(max_dollar / price) if price > 0 else 0

    if atr and atr > 0:
        risk_per_share = atr * GUARDRAILS["stop_atr_multiplier"]
        risk_budget = equity * GUARDRAILS["daily_loss_limit_pct"] * 0.5
        max_shares_by_risk = int(risk_budget / risk_per_share) if risk_per_share > 0 else 0
        return max(1, min(max_shares_by_equity, max_shares_by_risk))

    return max(1, max_shares_by_equity)


# ─── Position management ─────────────────────────────────────────────────────

def manage_positions(dry_run: bool = False):
    """Check open positions and close any that hit stop or target."""
    positions = get_positions()
    if not positions:
        return

    for pos in positions:
        sym = pos["symbol"]
        entry = pos["avg_entry"]
        current = pos["current_price"]
        qty = pos["qty"]
        pnl_pct = pos["unrealized_plpc"]

        from alpaca_trader import get_historical_bars
        bars = get_historical_bars(sym, "1Day", start=None, end=None)
        atr_series = compute_atr(bars, 14)
        atr = None
        for v in reversed(atr_series):
            if v is not None:
                atr = v
                break

        if atr is None:
            print(f"  ⚠ Cannot compute ATR for {sym} — skipping position management")
            continue

        stop_dist = atr * GUARDRAILS["stop_atr_multiplier"]

        is_long = qty > 0
        if is_long:
            stop_price = entry - stop_dist
            target_price = entry + stop_dist * GUARDRAILS["min_risk_reward"]
        else:
            stop_price = entry + stop_dist
            target_price = entry - stop_dist * GUARDRAILS["min_risk_reward"]

        hit_stop = (is_long and current <= stop_price) or (not is_long and current >= stop_price)
        hit_target = (is_long and current >= target_price) or (not is_long and current <= target_price)

        if hit_stop:
            print(f"\n  🛑 STOP HIT on {sym}: current={current:.2f} stop={stop_price:.2f}")
            if not dry_run:
                result = close_position(sym)
                if result:
                    _record_trade(result.get("pnl", 0.0))
        elif hit_target:
            print(f"\n  🎯 TARGET HIT on {sym}: current={current:.2f} target={target_price:.2f}")
            if not dry_run:
                result = close_position(sym)
                if result:
                    _record_trade(result.get("pnl", 0.0))
        else:
            direction = "LONG" if is_long else "SHORT"
            print(f"  📊 {sym} {direction}: entry={entry:.2f} current={current:.2f} "
                  f"stop={stop_price:.2f} target={target_price:.2f} P&L={pnl_pct:+.2%}")


# ─── Core scan-and-act cycle ─────────────────────────────────────────────────

def scan_and_act(dry_run: bool = False) -> list[dict]:
    """
    One full cycle: analyze both symbols, score, enforce guardrails, and
    optionally execute trades.

    Returns list of analysis results (always — even in dry-run mode).
    """
    print(f"\n{'━'*72}")
    print(f"  AGENT CYCLE  |  {_now_et().strftime('%Y-%m-%d %H:%M:%S ET')}")
    if dry_run:
        print(f"  MODE: DRY RUN (no trades will be placed)")
    print(f"{'━'*72}")

    # ── Pre-flight ────────────────────────────────────────────────────────
    acct = get_account()
    equity = acct["equity"]

    preflight = [
        ("Killzone", _check_killzone()),
        ("Trade Limit", _check_daily_trade_limit()),
        ("Loss Limit", _check_daily_loss_limit(equity)),
        ("Cooldown", _check_cooldown()),
    ]

    print(f"\n  PRE-FLIGHT CHECKS:")
    can_trade = True
    for name, (ok, msg) in preflight:
        status = "✓" if ok else "✗"
        print(f"    {status} {name}: {msg}")
        if not ok:
            can_trade = False

    # ── Manage existing positions ─────────────────────────────────────────
    manage_positions(dry_run=dry_run)

    # ── Analyze symbols ───────────────────────────────────────────────────
    results = []
    for sym in sorted(ALLOWED_SYMBOLS):
        print(f"\n{'─'*72}")
        print(f"  ANALYZING {sym}")
        print(f"{'─'*72}")

        try:
            result = analyze(sym, timeframe="1Day")
            results.append(result)
        except Exception as e:
            print(f"  ⚠ Analysis failed for {sym}: {e}")
            continue

        if not can_trade:
            print(f"  ⏸ Skipping trade evaluation — pre-flight failed")
            continue

        if result["recommendation"] not in ("buy", "sell"):
            print(f"  ⏭ No actionable setup for {sym} — recommendation: {result['recommendation']}")
            continue

        # ── A+ Scoring ────────────────────────────────────────────────
        score, checks = score_setup(result)
        print(f"\n  A+ SCORE: {score}/100  (threshold: {A_PLUS_THRESHOLD})")
        for criterion, met in checks.items():
            pts = SCORE_CRITERIA[criterion]
            mark = "✓" if met else "✗"
            print(f"    {mark} {criterion}: {pts}pts")

        if score < A_PLUS_THRESHOLD:
            print(f"  ⏭ Score {score} < {A_PLUS_THRESHOLD} — not A+ quality, skipping")
            continue

        # ── Hard rule check ───────────────────────────────────────────
        side = result["recommendation"]
        trade = result["trade"]

        if trade["risk_reward"] and trade["risk_reward"] < GUARDRAILS["min_risk_reward"]:
            print(f"  ⏭ R:R {trade['risk_reward']} < {GUARDRAILS['min_risk_reward']} — skipping")
            continue

        # ── Size the position ─────────────────────────────────────────
        atr = result["market_state"].get("atr_14")
        price = result["market_state"]["price"]
        qty = compute_position_size(equity, price, atr)

        print(f"\n  🎯 TRADE SIGNAL: {side.upper()} {qty} {sym}")
        print(f"     Entry:  ${trade['entry']:,.2f}")
        print(f"     Stop:   ${trade['stop_loss']:,.2f}")
        print(f"     Target: ${trade['take_profit']:,.2f}")
        print(f"     R:R:    {trade['risk_reward']}")
        print(f"     A+ Score: {score}/100")

        if dry_run:
            print(f"  📋 DRY RUN — trade logged but NOT executed")
            log_trade({
                "symbol": sym, "side": side, "qty": qty, "type": "dry_run",
                "entry": trade["entry"], "stop_loss": trade["stop_loss"],
                "take_profit": trade["take_profit"], "a_plus_score": score,
            }, action=f"dry_{side}")
            continue

        # ── Execute ───────────────────────────────────────────────────
        try:
            if side == "buy":
                order = buy(sym, qty=qty, order_type="limit",
                            limit_price=trade["entry"])
            else:
                order = sell(sym, qty=qty, order_type="limit",
                             limit_price=trade["entry"])

            _record_trade()
            print(f"  ✓ Order placed: {order['id']}")

        except Exception as e:
            print(f"  ✗ Order failed: {e}")

    # ── Summary ───────────────────────────────────────────────────────────
    state = _get_daily_state()
    print(f"\n{'━'*72}")
    print(f"  CYCLE COMPLETE  |  {_now_et().strftime('%H:%M:%S ET')}")
    print(f"  Trades today: {state.get('trades_taken', 0)}/{GUARDRAILS['max_trades_per_day']}")
    print(f"  Daily P&L:    ${state.get('daily_pnl', 0):.2f}")
    print(f"{'━'*72}\n")

    return results


# ─── Loop mode ────────────────────────────────────────────────────────────────

def run_loop(dry_run: bool = False, interval_min: int = 15):
    """Run scan_and_act in a loop during market hours."""
    print(f"\n  🔄 Agent starting in loop mode (interval: {interval_min}min)")
    print(f"     Dry run: {dry_run}")
    print(f"     Symbols: {sorted(ALLOWED_SYMBOLS)}")
    print(f"     Killzones enforced: {GUARDRAILS['require_killzone']}")
    print(f"     A+ threshold: {A_PLUS_THRESHOLD}/100")
    print(f"     Max trades/day: {GUARDRAILS['max_trades_per_day']}")
    print(f"     Max position: {GUARDRAILS['max_position_pct']:.0%} of equity")
    print(f"     Daily loss limit: {GUARDRAILS['daily_loss_limit_pct']:.0%} of equity")

    while True:
        if not market_is_open():
            print(f"\n  💤 Market closed — sleeping 60s before recheck...")
            time.sleep(60)
            continue

        scan_and_act(dry_run=dry_run)

        print(f"  ⏳ Next scan in {interval_min} minutes...")
        time.sleep(interval_min * 60)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Autonomous trading agent")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously during market hours")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze only — do not place any trades")
    parser.add_argument("--interval", type=int, default=15,
                        help="Minutes between scans in loop mode (default: 15)")
    args = parser.parse_args()

    if args.loop:
        run_loop(dry_run=args.dry_run, interval_min=args.interval)
    else:
        scan_and_act(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
