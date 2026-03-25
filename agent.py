#!/usr/bin/env python3
"""
Autonomous trading agent for SPY/QQQ on Alpaca paper.

Multi-timeframe approach:
  - Monthly (1Month) bars for macro liquidity map
  - Weekly  (1Week)  bars for liquidity map (PWH/PWL, equal H/L, swing levels, FVGs)
  - Daily   (1Day)   bars for directional bias
  - Intraday cascade for entries:
      15Min → structure/context
       5Min → setup confirmation
       1Min → precise entry timing
  - Real-time quotes for execution pricing

Orchestrates the full loop:
  1. Pre-flight checks (market open, killzone, daily limits)
  2. Monthly + Weekly liquidity maps — identify where the big pools sit
  3. Daily bias analysis — determine if we're bullish, bearish, or flat
  4. Cascading intraday scan (15Min→5Min→2Min) for entry setups
  5. Real-time quote to confirm price hasn't gapped away
  6. Score setup against A+ criteria + HTF liquidity proximity bonus
  7. Enforce guardrails (position sizing, R:R, loss limits, cooldown)
  8. Execute qualifying trades via alpaca_trader.py
  9. Manage open positions (stop/target exits using live price)
  10. Journal everything

Run modes:
  python3 agent.py                     # single scan + act cycle
  python3 agent.py --loop              # continuous loop (2-min scans)
  python3 agent.py --loop --interval 5 # custom interval
  python3 agent.py --dry-run           # analyze only, no execution
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
from indicator_engine import (
    compute_atr, compute_ema, compute_vwap, compute_rsi,
    detect_weekly_liquidity, detect_monthly_liquidity,
)
from journal import log_trade, log_analysis, log_decision
from memories import (
    KILLZONES,
    MACRO_WINDOWS,
    SCORE_CRITERIA,
    WEEKLY_LIQUIDITY_BONUS,
    WEEKLY_LEVEL_TYPE_BONUS,
    MONTHLY_LIQUIDITY_BONUS,
    MONTHLY_LEVEL_TYPE_BONUS,
    HTF_BONUS_CAP,
    A_PLUS_THRESHOLD,
    GUARDRAILS,
    DETECTION,
    HARD_RULES,
)

# Load learned weights if they exist
def _load_scoring_weights():
    """Load learned weights or fall back to defaults."""
    weights_file = Path(__file__).parent / "learned_weights.json"
    if weights_file.exists():
        try:
            with open(weights_file, "r") as f:
                learned = json.load(f)
                print(f"  🎓 Loaded learned weights (v{learned['meta']['version']}, "
                      f"updated {learned['meta']['last_updated'][:10]})")
                return (learned["criteria_weights"],
                        learned["weekly_liquidity_bonus"],
                        learned["monthly_liquidity_bonus"])
        except Exception as e:
            print(f"  ⚠ Could not load learned weights: {e}. Using defaults.")
    return SCORE_CRITERIA, WEEKLY_LIQUIDITY_BONUS, MONTHLY_LIQUIDITY_BONUS

# Initialize scoring weights (learned or default)
ACTIVE_SCORE_CRITERIA, ACTIVE_WEEKLY_BONUS, ACTIVE_MONTHLY_BONUS = _load_scoring_weights()

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

def score_setup(
    analysis: dict,
    daily_bias: str | None = None,
    weekly_context: dict | None = None,
    monthly_context: dict | None = None,
) -> tuple[int, dict[str, bool], dict]:
    """
    Score an analysis result against the A+ criteria from memories.py,
    plus weekly + monthly liquidity proximity bonus (capped at HTF_BONUS_CAP).

    Returns (total_score, {criterion: met_bool}, htf_bonus_info).
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

    base_score = sum(ACTIVE_SCORE_CRITERIA[k] for k, met in checks.items() if met)

    # ── HTF liquidity proximity bonus (weekly + monthly, capped) ──────
    # Use active (learned) bonus tables
    def _best_htf_bonus(context, prox_table, type_table):
        if not context or not context.get("levels"):
            return 0, None
        best_bonus = 0
        best_level = None
        for lvl in context["levels"]:
            proximity = lvl.get("proximity", "FAR")
            prox_bonus = prox_table.get(proximity, 0)
            type_bonus = type_table.get(lvl["type"], 0)

            is_target = False
            if side == "buy" and lvl["price"] > price:
                is_target = True
            elif side == "sell" and lvl["price"] < price:
                is_target = True
            elif lvl["price"] <= price * 1.001 and lvl["price"] >= price * 0.999:
                is_target = True
            if not is_target:
                continue

            total_lvl_bonus = prox_bonus + type_bonus
            if total_lvl_bonus > best_bonus:
                best_bonus = total_lvl_bonus
                best_level = lvl
        return best_bonus, best_level

    w_bonus, w_level = _best_htf_bonus(weekly_context, ACTIVE_WEEKLY_BONUS, WEEKLY_LEVEL_TYPE_BONUS)
    m_bonus, m_level = _best_htf_bonus(monthly_context, ACTIVE_MONTHLY_BONUS, MONTHLY_LEVEL_TYPE_BONUS)

    combined_htf = min(w_bonus + m_bonus, HTF_BONUS_CAP)

    htf_info = {
        "weekly_bonus": w_bonus,
        "monthly_bonus": m_bonus,
        "combined_bonus": combined_htf,
        "weekly_level": None,
        "monthly_level": None,
        "reason_weekly": "No aligned weekly levels nearby",
        "reason_monthly": "No aligned monthly levels nearby",
    }
    if w_level:
        htf_info["weekly_level"] = w_level
        htf_info["reason_weekly"] = (
            f"{w_level['label']} @ ${w_level['price']:,.2f} "
            f"({w_level['proximity']}, {w_level['distance_pct']}% away) → +{w_bonus}pts"
        )
    if m_level:
        htf_info["monthly_level"] = m_level
        htf_info["reason_monthly"] = (
            f"{m_level['label']} @ ${m_level['price']:,.2f} "
            f"({m_level['proximity']}, {m_level['distance_pct']}% away) → +{m_bonus}pts"
        )

    total = base_score + combined_htf
    return total, checks, htf_info


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
    Cascading intraday analysis across three timeframes:
      15Min → intraday structure/context
      5Min  → setup confirmation
      1Min  → precise entry timing

    Uses the shortest timeframe that shows a valid, aligned setup.
    If no setup on any timeframe, returns the 15Min analysis (or None
    if counter-trend).
    """
    # ── 15Min: Intraday context ───────────────────────────────────────
    print(f"\n  ⏱ INTRADAY for {symbol}  [daily bias: {daily_bias}]")
    print(f"     Scanning 15Min → 5Min → 1Min (best setup wins)")

    tf_15 = analyze(symbol, timeframe="15Min", lookback_days=5)
    rec_15 = tf_15["recommendation"]

    if daily_bias == "bullish" and rec_15 == "sell":
        print(f"     ⏭ 15Min says SELL but daily bias is BULLISH — skipping counter-trend")
        return None
    if daily_bias == "bearish" and rec_15 == "buy":
        print(f"     ⏭ 15Min says BUY but daily bias is BEARISH — skipping counter-trend")
        return None

    # ── 5Min: Setup confirmation ──────────────────────────────────────
    tf_5 = analyze(symbol, timeframe="5Min", lookback_days=2)
    rec_5 = tf_5["recommendation"]

    is_counter_5 = (
        (daily_bias == "bullish" and rec_5 == "sell") or
        (daily_bias == "bearish" and rec_5 == "buy")
    )

    # ── 1Min: Precise entry ───────────────────────────────────────────
    tf_1 = analyze(symbol, timeframe="1Min", lookback_days=1)
    rec_1 = tf_1["recommendation"]

    is_counter_1 = (
        (daily_bias == "bullish" and rec_1 == "sell") or
        (daily_bias == "bearish" and rec_1 == "buy")
    )

    # ── Pick the best aligned setup (prefer shortest timeframe) ───────
    best = None
    best_tf = None

    if rec_1 in ("buy", "sell") and not is_counter_1:
        best = tf_1
        best_tf = "1Min"
    elif rec_5 in ("buy", "sell") and not is_counter_5:
        best = tf_5
        best_tf = "5Min"
    elif rec_15 in ("buy", "sell"):
        best = tf_15
        best_tf = "15Min"

    print(f"\n     15Min: setup={tf_15.get('detected_setup','none'):<22} rec={rec_15:<10} conf={tf_15.get('confidence',0)}")
    print(f"      5Min: setup={tf_5.get('detected_setup','none'):<22} rec={rec_5:<10} conf={tf_5.get('confidence',0)}")
    print(f"      1Min: setup={tf_1.get('detected_setup','none'):<22} rec={rec_1:<10} conf={tf_1.get('confidence',0)}")

    if best:
        print(f"     ➤ Using {best_tf} — {best.get('detected_setup','none')} ({best['recommendation']})")
    else:
        print(f"     ➤ No aligned setup on any intraday timeframe")
        return tf_15

    return best


def get_weekly_context(symbol: str, current_price: float) -> dict:
    """
    Fetch weekly bars and build the liquidity map: PWH/PWL, equal H/L,
    swing levels, weekly FVGs, and proximity to current price.
    """
    print(f"\n  📅 WEEKLY LIQUIDITY MAP for {symbol}")
    weekly_bars = get_historical_bars(symbol, "1Week", start=None, end=None)

    if len(weekly_bars) < 4:
        print(f"     ⚠ Only {len(weekly_bars)} weekly bars — insufficient for liquidity map")
        return {"levels": [], "nearest_above": None, "nearest_below": None}

    ctx = detect_weekly_liquidity(weekly_bars, current_price)

    print(f"     PWH: ${ctx['pwh']:,.2f}   PWL: ${ctx['pwl']:,.2f}")
    print(f"     This Week: H=${ctx['current_week_high']:,.2f}  L=${ctx['current_week_low']:,.2f}")
    print(f"     Key Levels ({len(ctx['levels'])}):")

    for lvl in ctx["levels"]:
        arrow = "▲" if lvl["price"] > current_price else "▼"
        prox = lvl.get("proximity", "")
        dist = lvl.get("distance_pct", 0)
        print(f"       {arrow} ${lvl['price']:>10,.2f}  {prox:<12} ({dist:.2f}%)  {lvl['label']}")

    if ctx["nearest_above"]:
        na = ctx["nearest_above"]
        print(f"     ➤ Nearest ABOVE: ${na['price']:,.2f} — {na['label']}")
    if ctx["nearest_below"]:
        nb = ctx["nearest_below"]
        print(f"     ➤ Nearest BELOW: ${nb['price']:,.2f} — {nb['label']}")

    return ctx


def get_monthly_context(symbol: str, current_price: float) -> dict:
    """
    Fetch monthly bars and build the monthly liquidity map: PMH/PML,
    quarterly levels, swing levels, equal H/L, monthly FVGs.
    """
    print(f"\n  📅 MONTHLY LIQUIDITY MAP for {symbol}")
    monthly_bars = get_historical_bars(symbol, "1Month",
                                        start=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                                        end=None)

    if len(monthly_bars) < 3:
        print(f"     ⚠ Only {len(monthly_bars)} monthly bars — insufficient for liquidity map")
        return {"levels": [], "nearest_above": None, "nearest_below": None}

    ctx = detect_monthly_liquidity(monthly_bars, current_price)

    print(f"     PMH: ${ctx['pmh']:,.2f}   PML: ${ctx['pml']:,.2f}")
    print(f"     This Month: H=${ctx['current_month_high']:,.2f}  L=${ctx['current_month_low']:,.2f}")
    print(f"     Key Levels ({len(ctx['levels'])}):")

    for lvl in ctx["levels"]:
        arrow = "▲" if lvl["price"] > current_price else "▼"
        prox = lvl.get("proximity", "")
        dist = lvl.get("distance_pct", 0)
        print(f"       {arrow} ${lvl['price']:>10,.2f}  {prox:<12} ({dist:.2f}%)  {lvl['label']}")

    if ctx["nearest_above"]:
        na = ctx["nearest_above"]
        print(f"     ➤ Nearest ABOVE: ${na['price']:,.2f} — {na['label']}")
    if ctx["nearest_below"]:
        nb = ctx["nearest_below"]
        print(f"     ➤ Nearest BELOW: ${nb['price']:,.2f} — {nb['label']}")

    return ctx


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
    """
    Check open positions and close any that hit stop or target.

    NOTE: As of bracket order implementation, new trades have broker-side stops
    that execute automatically. This function acts as a backup for:
      - Manually opened positions (not from agent)
      - Legacy positions from before bracket orders
      - Emergency exit if bracket orders fail
    """
    positions = get_positions()
    if not positions:
        return

    # Check for existing bracket orders (stop loss / take profit)
    from alpaca_trader import get_open_orders
    open_orders = get_open_orders()
    symbols_with_brackets = {o["symbol"] for o in open_orders if o["type"] in ("stop", "limit")}

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

        # Check if broker-side bracket orders exist
        has_bracket = sym in symbols_with_brackets

        if hit_stop:
            if has_bracket:
                print(f"\n  🛑 STOP HIT on {sym}: live={current:.2f} stop={stop_price:.2f} "
                      f"[broker-side stop order will handle exit]")
            else:
                print(f"\n  🛑 STOP HIT on {sym}: live={current:.2f} stop={stop_price:.2f} "
                      f"[no bracket - manually closing]")
                if not dry_run:
                    result = close_position(sym)
                    if result:
                        _record_trade(result.get("pnl", 0.0))
        elif hit_target:
            if has_bracket:
                print(f"\n  🎯 TARGET HIT on {sym}: live={current:.2f} target={target_price:.2f} "
                      f"[broker-side take-profit order will handle exit]")
            else:
                print(f"\n  🎯 TARGET HIT on {sym}: live={current:.2f} target={target_price:.2f} "
                      f"[no bracket - manually closing]")
                if not dry_run:
                    result = close_position(sym)
                    if result:
                        _record_trade(result.get("pnl", 0.0))
        else:
            direction = "LONG" if is_long else "SHORT"
            bracket_status = "[BROKER-SIDE STOPS ACTIVE]" if has_bracket else "[manual stops]"
            print(f"  📊 {sym} {direction}: entry={entry:.2f} live={current:.2f} "
                  f"stop={stop_price:.2f} target={target_price:.2f} P&L={pnl_pct:+.2%} {bracket_status}")


# ─── Decision logging ─────────────────────────────────────────────────────────

def _log_sym_decision(
    symbol: str,
    outcome: str,
    reason: str,
    detected_setup: str = "none",
    recommendation: str = "no_trade",
    daily_bias: str = "unknown",
    scores: dict | None = None,
    criteria: dict | None = None,
    market_state: dict | None = None,
    trade_levels: dict | None = None,
    htf_info: dict | None = None,
):
    """Build and log a full decision record."""
    is_kz, kz_label = in_killzone()
    decision = {
        "symbol": symbol,
        "outcome": outcome,
        "reason": reason,
        "detected_setup": detected_setup,
        "recommendation": recommendation,
        "daily_bias": daily_bias,
        "killzone": kz_label,
        "in_macro_window": in_macro_window(),
        "scores": scores or {"base": 0, "weekly_bonus": 0, "monthly_bonus": 0, "htf_total": 0, "final": 0},
        "criteria": criteria or {},
        "market_state": market_state or {},
        "trade_levels": trade_levels or {},
        "htf_context": {
            "weekly": htf_info.get("reason_weekly") if htf_info else None,
            "monthly": htf_info.get("reason_monthly") if htf_info else None,
        } if htf_info else {},
    }
    log_decision(decision)


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

        # ── Step 1: HTF liquidity maps (weekly + monthly) ─────────────
        weekly_ctx = None
        monthly_ctx = None
        try:
            live_snap = get_live_price(sym)
            stats.tick_quote()
            snap_price = ((live_snap["bid"] + live_snap["ask"]) / 2) if live_snap else None
        except Exception:
            snap_price = None

        if snap_price:
            try:
                weekly_ctx = get_weekly_context(sym, snap_price)
                stats.tick_api()
                stats.tick_indicators(3)
            except Exception as e:
                print(f"  ⚠ Weekly analysis failed for {sym}: {e}")

            try:
                monthly_ctx = get_monthly_context(sym, snap_price)
                stats.tick_api()
                stats.tick_indicators(3)
            except Exception as e:
                print(f"  ⚠ Monthly analysis failed for {sym}: {e}")

        # ── Step 2: Daily bias ────────────────────────────────────────
        try:
            bias_data = get_daily_bias(sym)
            daily_bias = bias_data["bias"]
            stats.tick_analysis()
        except Exception as e:
            print(f"  ⚠ Daily analysis failed for {sym}: {e}")
            continue

        if daily_bias == "neutral":
            print(f"  ⏭ Daily bias is NEUTRAL for {sym} — no clear direction, sitting out")
            _log_sym_decision(sym, "neutral_bias",
                "Daily bias is neutral — no clear direction, sitting out",
                daily_bias="neutral",
                market_state=bias_data.get("daily_analysis", {}).get("market_state"))
            results.append(bias_data.get("daily_analysis", {}))
            continue

        # ── Step 3: Intraday entry scan ───────────────────────────────
        try:
            intraday = get_intraday_analysis(sym, daily_bias)
            stats.tick_analysis()
        except Exception as e:
            print(f"  ⚠ Intraday analysis failed for {sym}: {e}")
            continue

        if intraday is None:
            _log_sym_decision(sym, "counter_trend",
                f"Intraday setup opposes daily bias ({daily_bias})",
                daily_bias=daily_bias,
                market_state=bias_data.get("daily_analysis", {}).get("market_state"))
            results.append(bias_data.get("daily_analysis", {}))
            continue

        results.append(intraday)

        if not can_trade:
            print(f"  ⏸ Skipping trade evaluation — pre-flight failed")
            failed_checks = [n for n, (ok, _) in preflight if not ok]
            _log_sym_decision(sym, "preflight_blocked",
                f"Pre-flight failed: {', '.join(failed_checks)}",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=intraday.get("recommendation", "no_trade"),
                daily_bias=daily_bias,
                market_state=intraday.get("market_state"))
            continue

        if intraday["recommendation"] not in ("buy", "sell"):
            print(f"  ⏭ No actionable intraday setup — rec: {intraday['recommendation']}")
            _log_sym_decision(sym, "no_setup",
                f"No actionable setup detected — recommendation: {intraday['recommendation']}",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=intraday["recommendation"],
                daily_bias=daily_bias,
                market_state=intraday.get("market_state"))
            continue

        stats.setups_detected += 1

        # ── Step 4: A+ Scoring + HTF Liquidity Bonus ─────────────────
        score, checks, htf_info = score_setup(intraday, daily_bias, weekly_ctx, monthly_ctx)
        base_score = sum(ACTIVE_SCORE_CRITERIA[k] for k, met in checks.items() if met)
        wb = htf_info.get("weekly_bonus", 0)
        mb = htf_info.get("monthly_bonus", 0)
        htf_total = htf_info.get("combined_bonus", 0)

        print(f"\n  A+ SCORE: {score}  (base: {base_score} + weekly: +{wb} + monthly: +{mb} = +{htf_total} HTF)")
        print(f"  Threshold: {A_PLUS_THRESHOLD}  |  HTF cap: {HTF_BONUS_CAP}")
        for criterion, met in checks.items():
            pts = ACTIVE_SCORE_CRITERIA[criterion]
            mark = "✓" if met else "✗"
            print(f"    {mark} {criterion}: {pts}pts")
        if wb > 0:
            print(f"    ✓ weekly_liquidity: +{wb}pts — {htf_info['reason_weekly']}")
        else:
            print(f"    ✗ weekly_liquidity: +0pts — {htf_info['reason_weekly']}")
        if mb > 0:
            print(f"    ✓ monthly_liquidity: +{mb}pts — {htf_info['reason_monthly']}")
        else:
            print(f"    ✗ monthly_liquidity: +0pts — {htf_info['reason_monthly']}")

        if score < A_PLUS_THRESHOLD:
            print(f"  ⏭ Score {score} < {A_PLUS_THRESHOLD} — not A+ quality, skipping")
            _log_sym_decision(sym, "score_too_low",
                f"A+ score {score} < threshold {A_PLUS_THRESHOLD}",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=intraday["recommendation"],
                daily_bias=daily_bias,
                scores={"base": base_score, "weekly_bonus": wb,
                        "monthly_bonus": mb, "htf_total": htf_total, "final": score},
                criteria=checks,
                market_state=intraday.get("market_state"),
                trade_levels=intraday.get("trade"),
                htf_info=htf_info)
            continue

        # ── Step 5: Live quote confirmation ───────────────────────────
        side = intraday["recommendation"]
        trade = intraday["trade"]

        if trade["risk_reward"] and trade["risk_reward"] < GUARDRAILS["min_risk_reward"]:
            print(f"  ⏭ R:R {trade['risk_reward']} < {GUARDRAILS['min_risk_reward']} — skipping")
            _log_sym_decision(sym, "rr_too_low",
                f"R:R {trade['risk_reward']} < minimum {GUARDRAILS['min_risk_reward']}",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=side, daily_bias=daily_bias,
                scores={"base": base_score, "weekly_bonus": wb,
                        "monthly_bonus": mb, "htf_total": htf_total, "final": score},
                criteria=checks,
                market_state=intraday.get("market_state"),
                trade_levels=trade, htf_info=htf_info)
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
                _log_sym_decision(sym, "slippage_skip",
                    f"Live price ${live_mid:,.2f} moved {slippage_pct:.2%} from entry ${entry_price:,.2f}",
                    detected_setup=intraday.get("detected_setup", "none"),
                    recommendation=side, daily_bias=daily_bias,
                    scores={"base": base_score, "weekly_bonus": wb,
                            "monthly_bonus": mb, "htf_total": htf_total, "final": score},
                    criteria=checks,
                    market_state=intraday.get("market_state"),
                    trade_levels=trade, htf_info=htf_info)
                continue
            exec_price = round(live_mid, 2)
            print(f"  💹 Live quote: bid=${live['bid']:,.2f}  ask=${live['ask']:,.2f}  "
                  f"mid=${live_mid:,.2f}  (entry was ${entry_price:,.2f})")
        else:
            exec_price = trade["entry"]

        # ── Step 6: Size the position ─────────────────────────────────
        atr = intraday["market_state"].get("atr_14")
        qty = compute_position_size(equity, exec_price, atr)

        print(f"\n  🎯 TRADE SIGNAL: {side.upper()} {qty} {sym}")
        print(f"     Daily Bias:  {daily_bias.upper()}")
        print(f"     Entry (15m): ${trade['entry']:,.2f}")
        print(f"     Exec Price:  ${exec_price:,.2f}")
        print(f"     Stop:        ${trade['stop_loss']:,.2f}")
        print(f"     Target:      ${trade['take_profit']:,.2f}")
        print(f"     R:R:         {trade['risk_reward']}")
        print(f"     A+ Score:    {score} (base {base_score} + HTF +{htf_total})")
        if htf_info.get("weekly_level"):
            wl = htf_info["weekly_level"]
            print(f"     Weekly Lvl:  {wl['label']} @ ${wl['price']:,.2f}")
        if htf_info.get("monthly_level"):
            ml = htf_info["monthly_level"]
            print(f"     Monthly Lvl: {ml['label']} @ ${ml['price']:,.2f}")

        decision_scores = {"base": base_score, "weekly_bonus": wb,
                           "monthly_bonus": mb, "htf_total": htf_total, "final": score}

        if dry_run:
            print(f"  📋 DRY RUN — trade logged but NOT executed")
            log_trade({
                "symbol": sym, "side": side, "qty": qty, "type": "dry_run",
                "daily_bias": daily_bias, "entry": trade["entry"],
                "exec_price": exec_price, "stop_loss": trade["stop_loss"],
                "take_profit": trade["take_profit"],
                "a_plus_score": score, "base_score": base_score,
                "weekly_bonus": wb, "monthly_bonus": mb,
                "htf_bonus_total": htf_total,
                "weekly_level": htf_info.get("reason_weekly"),
                "monthly_level": htf_info.get("reason_monthly"),
            }, action=f"dry_{side}")
            _log_sym_decision(sym, "trade_signal",
                f"DRY RUN — {side.upper()} {qty} @ ${exec_price:,.2f} (would have executed)",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=side, daily_bias=daily_bias,
                scores=decision_scores, criteria=checks,
                market_state=intraday.get("market_state"),
                trade_levels={"entry": exec_price, "stop_loss": trade["stop_loss"],
                              "take_profit": trade["take_profit"], "risk_reward": trade["risk_reward"],
                              "qty": qty},
                htf_info=htf_info)
            continue

        # ── Step 7: Execute with broker-side bracket orders ──────────
        try:
            if side == "buy":
                order = buy(sym, qty=qty, order_type="limit",
                            limit_price=exec_price,
                            stop_loss=trade["stop_loss"],
                            take_profit=trade["take_profit"])
            else:
                order = sell(sym, qty=qty, order_type="limit",
                             limit_price=exec_price,
                             stop_loss=trade["stop_loss"],
                             take_profit=trade["take_profit"])

            _record_trade()
            stats.trades_executed += 1
            stats.tick_api()
            print(f"  ✓ Order placed: {order['id']} [BRACKET ORDER - broker-side stops active]")
            _log_sym_decision(sym, "order_placed",
                f"{side.upper()} {qty} @ ${exec_price:,.2f} — order {order['id']}",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=side, daily_bias=daily_bias,
                scores=decision_scores, criteria=checks,
                market_state=intraday.get("market_state"),
                trade_levels={"entry": exec_price, "stop_loss": trade["stop_loss"],
                              "take_profit": trade["take_profit"], "risk_reward": trade["risk_reward"],
                              "qty": qty, "order_id": order["id"]},
                htf_info=htf_info)

        except Exception as e:
            print(f"  ✗ Order failed: {e}")
            _log_sym_decision(sym, "order_failed",
                f"Order failed: {e}",
                detected_setup=intraday.get("detected_setup", "none"),
                recommendation=side, daily_bias=daily_bias,
                scores=decision_scores, criteria=checks,
                market_state=intraday.get("market_state"),
                trade_levels=trade, htf_info=htf_info)

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

def run_loop(dry_run: bool = False, interval_min: int = 2):
    """Run scan_and_act in a loop, scanning every interval_min during killzones."""
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
    parser.add_argument("--interval", type=int, default=2,
                        help="Minutes between scans during killzones (default: 2)")
    args = parser.parse_args()

    if args.loop:
        run_loop(dry_run=args.dry_run, interval_min=args.interval)
    else:
        scan_and_act(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
