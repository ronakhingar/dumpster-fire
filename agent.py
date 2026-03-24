#!/usr/bin/env python3
"""
Autonomous trading agent for SPY/QQQ on Alpaca paper.

Multi-timeframe approach:
  - Daily (1Day) bars for directional bias
  - Intraday (15Min) bars for entry signals
  - Real-time quotes for execution pricing

Orchestrates the full loop:
  1. Pre-flight checks (market open, killzone, daily limits)
  2. Daily bias analysis — determine if we're bullish, bearish, or flat
  3. Intraday scan on 15Min bars for entry setups
  4. Real-time quote to confirm price hasn't gapped away
  5. Score each setup against A+ criteria from memories.py
  6. Enforce guardrails (position sizing, R:R, loss limits, cooldown)
  7. Execute qualifying trades via alpaca_trader.py
  8. Manage open positions (stop/target exits using live price)
  9. Journal everything

Run modes:
  python3 agent.py              # single scan + act cycle
  python3 agent.py --loop       # continuous loop during killzones
  python3 agent.py --dry-run    # analyze only, no execution
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
    get_quote,
    get_positions,
    get_historical_bars,
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
CYCLE_LOG = Path(__file__).parent / "journal" / "cycle_stats.jsonl"

# ─── Cycle stats tracker ─────────────────────────────────────────────────────

class CycleStats:
    """Tracks API calls, indicators, and compute used per scan cycle."""

    def __init__(self):
        self.start_time = datetime.now(ET)
        self.alpaca_api_calls = 0
        self.bars_fetched = 0
        self.indicators_computed = 0
        self.live_quotes = 0
        self.symbols_analyzed = 0
        self.setups_detected = 0
        self.trades_executed = 0

    def tick_api(self, count=1):
        self.alpaca_api_calls += count

    def tick_bars(self, count):
        self.bars_fetched += count

    def tick_indicators(self, count=1):
        self.indicators_computed += count

    def tick_quote(self):
        self.live_quotes += 1
        self.alpaca_api_calls += 1

    def tick_analysis(self):
        self.symbols_analyzed += 1
        self.alpaca_api_calls += 1
        self.indicators_computed += 5

    def summary(self) -> dict:
        elapsed = (datetime.now(ET) - self.start_time).total_seconds()
        return {
            "timestamp": self.start_time.isoformat(),
            "elapsed_seconds": round(elapsed, 1),
            "llm_tokens_used": 0,
            "llm_model": "none (deterministic agent)",
            "alpaca_api_calls": self.alpaca_api_calls,
            "bars_fetched": self.bars_fetched,
            "indicators_computed": self.indicators_computed,
            "live_quotes_fetched": self.live_quotes,
            "symbols_analyzed": self.symbols_analyzed,
            "setups_detected": self.setups_detected,
            "trades_executed": self.trades_executed,
        }

    def log(self):
        """Append cycle stats to the JSONL log file."""
        CYCLE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CYCLE_LOG, "a") as f:
            f.write(json.dumps(self.summary(), default=str) + "\n")

    def print_summary(self):
        s = self.summary()
        print(f"\n  📊 CYCLE STATS")
        print(f"     LLM tokens:     {s['llm_tokens_used']} ({s['llm_model']})")
        print(f"     Alpaca API:     {s['alpaca_api_calls']} calls")
        print(f"     Bars fetched:   {s['bars_fetched']}")
        print(f"     Indicators:     {s['indicators_computed']} computations")
        print(f"     Live quotes:    {s['live_quotes_fetched']}")
        print(f"     Symbols:        {s['symbols_analyzed']} analyzed")
        print(f"     Setups found:   {s['setups_detected']}")
        print(f"     Trades:         {s['trades_executed']}")
        print(f"     Elapsed:        {s['elapsed_seconds']}s")

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


def next_killzone_wait() -> int | None:
    """Seconds until the next killzone opens, or None if in one now."""
    if in_killzone()[0]:
        return None
    now = _now_et()
    now_minutes = now.hour * 60 + now.minute
    best_wait = None
    for kz in KILLZONES.values():
        h, m = map(int, kz["start"].split(":"))
        kz_minutes = h * 60 + m
        diff = kz_minutes - now_minutes
        if diff <= 0:
            diff += 24 * 60
        wait_seconds = diff * 60
        if best_wait is None or wait_seconds < best_wait:
            best_wait = wait_seconds
    return best_wait

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

def score_setup(analysis: dict, daily_bias: str | None = None) -> tuple[int, dict[str, bool]]:
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


# ─── Multi-timeframe bias ────────────────────────────────────────────────────

def get_daily_bias(symbol: str) -> dict:
    """
    Analyze the daily chart to determine directional bias.
    Returns dict with bias ("bullish", "bearish", "neutral") and supporting data.
    """
    print(f"\n  📅 DAILY BIAS for {symbol}")
    daily = analyze(symbol, timeframe="1Day", lookback_days=90)
    ms = daily["market_state"]
    trend = daily.get("detected_setup", "none")

    price = ms["price"]
    ema9 = ms.get("ema_9")
    ema21 = ms.get("ema_21")
    ema50 = ms.get("ema_50")
    rsi = ms.get("rsi_14")

    if ema9 and ema21 and ema50:
        if price > ema9 > ema21 > ema50:
            bias = "bullish"
        elif price > ema21 > ema50:
            bias = "bullish"
        elif price < ema9 < ema21 < ema50:
            bias = "bearish"
        elif price < ema21 < ema50:
            bias = "bearish"
        else:
            bias = "neutral"
    else:
        bias = "neutral"

    result = {
        "bias": bias,
        "price": price,
        "ema_9": ema9,
        "ema_21": ema21,
        "ema_50": ema50,
        "rsi_14": rsi,
        "summary": ms.get("summary", ""),
        "daily_analysis": daily,
    }

    print(f"     Bias: {bias.upper()}")
    print(f"     Price: ${price:,.2f}  EMA9={ema9}  EMA21={ema21}  EMA50={ema50}")
    if rsi:
        print(f"     RSI: {rsi:.1f}")

    return result


def get_intraday_analysis(symbol: str, daily_bias: str) -> dict | None:
    """
    Run 15Min intraday analysis. Only look for setups that align with
    the daily bias (no counter-trend trades).
    """
    print(f"\n  ⏱ INTRADAY (15Min) for {symbol}  [daily bias: {daily_bias}]")
    intraday = analyze(symbol, timeframe="15Min", lookback_days=5)

    rec = intraday["recommendation"]

    if daily_bias == "bullish" and rec == "sell":
        print(f"     ⏭ Intraday says SELL but daily bias is BULLISH — skipping counter-trend")
        return None
    if daily_bias == "bearish" and rec == "buy":
        print(f"     ⏭ Intraday says BUY but daily bias is BEARISH — skipping counter-trend")
        return None

    return intraday


def get_live_price(symbol: str) -> dict | None:
    """Fetch real-time quote for final execution check."""
    try:
        quote = get_quote(symbol)
        return quote
    except Exception as e:
        print(f"  ⚠ Could not fetch live quote for {symbol}: {e}")
        return None


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
    """Check open positions using live price and close any that hit stop or target."""
    positions = get_positions()
    if not positions:
        return

    for pos in positions:
        sym = pos["symbol"]
        entry = pos["avg_entry"]
        qty = pos["qty"]
        pnl_pct = pos["unrealized_plpc"]

        live = get_live_price(sym)
        if live:
            bid = live.get("bid", 0)
            ask = live.get("ask", 0)
            current = (bid + ask) / 2 if bid and ask else pos["current_price"]
        else:
            current = pos["current_price"]

        bars = get_historical_bars(sym, "15Min")
        atr_series = compute_atr(bars, 14)
        atr = None
        for v in reversed(atr_series):
            if v is not None:
                atr = v
                break

        if atr is None:
            bars_daily = get_historical_bars(sym, "1Day")
            atr_series = compute_atr(bars_daily, 14)
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
            print(f"\n  🛑 STOP HIT on {sym}: live={current:.2f} stop={stop_price:.2f}")
            if not dry_run:
                result = close_position(sym)
                if result:
                    _record_trade(result.get("pnl", 0.0))
        elif hit_target:
            print(f"\n  🎯 TARGET HIT on {sym}: live={current:.2f} target={target_price:.2f}")
            if not dry_run:
                result = close_position(sym)
                if result:
                    _record_trade(result.get("pnl", 0.0))
        else:
            direction = "LONG" if is_long else "SHORT"
            print(f"  📊 {sym} {direction}: entry={entry:.2f} live={current:.2f} "
                  f"stop={stop_price:.2f} target={target_price:.2f} P&L={pnl_pct:+.2%}")


# ─── Core scan-and-act cycle ─────────────────────────────────────────────────

def scan_and_act(dry_run: bool = False) -> list[dict]:
    """
    One full cycle with multi-timeframe analysis:
      1. Daily bars → directional bias
      2. 15Min bars → entry setup (must align with daily bias)
      3. Live quote → execution price confirmation
      4. A+ scoring + guardrails → go/no-go
    """
    stats = CycleStats()

    print(f"\n{'━'*72}")
    print(f"  AGENT CYCLE  |  {_now_et().strftime('%Y-%m-%d %H:%M:%S ET')}")
    if dry_run:
        print(f"  MODE: DRY RUN (no trades will be placed)")
    print(f"{'━'*72}")

    # ── Pre-flight ────────────────────────────────────────────────────────
    acct = get_account()
    stats.tick_api()
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

    # ── Manage existing positions (uses live price) ───────────────────────
    manage_positions(dry_run=dry_run)
    stats.tick_api()

    # ── Multi-timeframe analysis ──────────────────────────────────────────
    results = []
    for sym in sorted(ALLOWED_SYMBOLS):
        print(f"\n{'─'*72}")
        print(f"  ANALYZING {sym}  (multi-timeframe)")
        print(f"{'─'*72}")

        # ── Step 1: Daily bias ────────────────────────────────────────
        try:
            bias_data = get_daily_bias(sym)
            daily_bias = bias_data["bias"]
            stats.tick_analysis()
        except Exception as e:
            print(f"  ⚠ Daily analysis failed for {sym}: {e}")
            continue

        if daily_bias == "neutral":
            print(f"  ⏭ Daily bias is NEUTRAL for {sym} — no clear direction, sitting out")
            results.append(bias_data.get("daily_analysis", {}))
            continue

        # ── Step 2: Intraday entry scan ───────────────────────────────
        try:
            intraday = get_intraday_analysis(sym, daily_bias)
            stats.tick_analysis()
        except Exception as e:
            print(f"  ⚠ Intraday analysis failed for {sym}: {e}")
            continue

        if intraday is None:
            results.append(bias_data.get("daily_analysis", {}))
            continue

        results.append(intraday)

        if not can_trade:
            print(f"  ⏸ Skipping trade evaluation — pre-flight failed")
            continue

        if intraday["recommendation"] not in ("buy", "sell"):
            print(f"  ⏭ No actionable intraday setup — rec: {intraday['recommendation']}")
            continue

        stats.setups_detected += 1

        # ── Step 3: A+ Scoring ────────────────────────────────────────
        score, checks = score_setup(intraday, daily_bias)
        print(f"\n  A+ SCORE: {score}/100  (threshold: {A_PLUS_THRESHOLD})")
        for criterion, met in checks.items():
            pts = SCORE_CRITERIA[criterion]
            mark = "✓" if met else "✗"
            print(f"    {mark} {criterion}: {pts}pts")

        if score < A_PLUS_THRESHOLD:
            print(f"  ⏭ Score {score} < {A_PLUS_THRESHOLD} — not A+ quality, skipping")
            continue

        # ── Step 4: Live quote confirmation ───────────────────────────
        side = intraday["recommendation"]
        trade = intraday["trade"]

        if trade["risk_reward"] and trade["risk_reward"] < GUARDRAILS["min_risk_reward"]:
            print(f"  ⏭ R:R {trade['risk_reward']} < {GUARDRAILS['min_risk_reward']} — skipping")
            continue

        live = get_live_price(sym)
        stats.tick_quote()
        if live:
            live_mid = (live["bid"] + live["ask"]) / 2
            entry_price = trade["entry"]
            slippage_pct = abs(live_mid - entry_price) / entry_price
            if slippage_pct > 0.005:
                print(f"  ⏭ Live price ${live_mid:,.2f} has moved >{slippage_pct:.1%} from "
                      f"entry ${entry_price:,.2f} — stale signal, skipping")
                continue
            exec_price = round(live_mid, 2)
            print(f"  💹 Live quote: bid=${live['bid']:,.2f}  ask=${live['ask']:,.2f}  "
                  f"mid=${live_mid:,.2f}  (entry was ${entry_price:,.2f})")
        else:
            exec_price = trade["entry"]

        # ── Step 5: Size the position ─────────────────────────────────
        atr = intraday["market_state"].get("atr_14")
        qty = compute_position_size(equity, exec_price, atr)

        print(f"\n  🎯 TRADE SIGNAL: {side.upper()} {qty} {sym}")
        print(f"     Daily Bias:  {daily_bias.upper()}")
        print(f"     Entry (15m): ${trade['entry']:,.2f}")
        print(f"     Exec Price:  ${exec_price:,.2f}")
        print(f"     Stop:        ${trade['stop_loss']:,.2f}")
        print(f"     Target:      ${trade['take_profit']:,.2f}")
        print(f"     R:R:         {trade['risk_reward']}")
        print(f"     A+ Score:    {score}/100")

        if dry_run:
            print(f"  📋 DRY RUN — trade logged but NOT executed")
            log_trade({
                "symbol": sym, "side": side, "qty": qty, "type": "dry_run",
                "daily_bias": daily_bias, "entry": trade["entry"],
                "exec_price": exec_price, "stop_loss": trade["stop_loss"],
                "take_profit": trade["take_profit"], "a_plus_score": score,
            }, action=f"dry_{side}")
            continue

        # ── Step 6: Execute ───────────────────────────────────────────
        try:
            if side == "buy":
                order = buy(sym, qty=qty, order_type="limit",
                            limit_price=exec_price)
            else:
                order = sell(sym, qty=qty, order_type="limit",
                             limit_price=exec_price)

            _record_trade()
            stats.trades_executed += 1
            stats.tick_api()
            print(f"  ✓ Order placed: {order['id']}")

        except Exception as e:
            print(f"  ✗ Order failed: {e}")

    # ── Summary + stats ───────────────────────────────────────────────────
    state = _get_daily_state()
    stats.print_summary()
    stats.log()

    print(f"\n{'━'*72}")
    print(f"  CYCLE COMPLETE  |  {_now_et().strftime('%H:%M:%S ET')}")
    print(f"  Trades today: {state.get('trades_taken', 0)}/{GUARDRAILS['max_trades_per_day']}")
    print(f"  Daily P&L:    ${state.get('daily_pnl', 0):.2f}")
    print(f"{'━'*72}\n")

    return results


# ─── Loop mode ────────────────────────────────────────────────────────────────

def run_loop(dry_run: bool = False, interval_min: int = 5):
    """Run scan_and_act in a loop, sleeping between killzones."""
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

        is_kz, kz_label = in_killzone()
        if is_kz:
            scan_and_act(dry_run=dry_run)
            print(f"  ⏳ Next scan in {interval_min} minutes...")
            time.sleep(interval_min * 60)
        else:
            wait = next_killzone_wait()
            if wait and wait < 8 * 3600:
                wait_min = wait // 60
                print(f"\n  ⏰ Outside killzone ({_time_str()} ET) — next opens in ~{wait_min} min, sleeping...")
                time.sleep(min(wait, 300))
            else:
                print(f"\n  💤 No killzone soon — sleeping 5 min...")
                time.sleep(300)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Autonomous trading agent")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously, auto-waking for killzones")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze only — do not place any trades")
    parser.add_argument("--interval", type=int, default=5,
                        help="Minutes between scans during killzones (default: 5)")
    args = parser.parse_args()

    if args.loop:
        run_loop(dry_run=args.dry_run, interval_min=args.interval)
    else:
        scan_and_act(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
