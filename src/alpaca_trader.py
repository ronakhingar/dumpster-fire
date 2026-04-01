#!/usr/bin/env python3
"""
Alpaca paper trading functions for QQQ and SPY.

Usage:
    from alpaca_trader import *

    get_account()
    get_quote("SPY")
    get_bars("QQQ", timeframe="1Day", limit=10)
    get_historical_bars("SPY", "15Min", start="2026-03-10", end="2026-03-20")
    buy("SPY", qty=5)
    buy("QQQ", qty=2, order_type="limit", limit_price=580.00)
    sell("SPY", qty=5)
    get_positions()
    get_open_orders()
    cancel_order("<order_id>")
    cancel_all_orders()
    close_position("SPY")
    get_recent_fills(limit=10)
"""

import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from src.journal import log_trade

load_dotenv()

ALLOWED_SYMBOLS = {"QQQ", "SPY"}

api = tradeapi.REST(
    key_id=os.getenv("ALPACA_API_KEY"),
    secret_key=os.getenv("ALPACA_SECRET_KEY"),
    base_url="https://paper-api.alpaca.markets",
    api_version="v2",
)


def _validate_symbol(symbol):
    s = symbol.upper()
    if s not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' not allowed. Choose from: {sorted(ALLOWED_SYMBOLS)}")
    return s


def _fmt(value):
    return f"${float(value):,.2f}"


# ─── Account ────────────────────────────────────────────────────────────────

def get_account():
    """Return account summary (equity, cash, buying power, etc.)."""
    a = api.get_account()
    info = {
        "status": a.status,
        "equity": float(a.equity),
        "cash": float(a.cash),
        "buying_power": float(a.buying_power),
        "portfolio_value": float(a.portfolio_value),
        "daytrade_count": int(a.daytrade_count),
    }
    print(f"\n  Account  status={info['status']}  equity={_fmt(info['equity'])}  "
          f"cash={_fmt(info['cash'])}  buying_power={_fmt(info['buying_power'])}")
    return info


# ─── Market Data ─────────────────────────────────────────────────────────────

def get_quote(symbol):
    """Latest quote (bid/ask) and last bar for a symbol."""
    sym = _validate_symbol(symbol)

    quote_raw = api.get_latest_quote(sym, feed="iex")._raw
    bar = api.get_latest_bar(sym, feed="iex")

    result = {
        "symbol": sym,
        "bid": quote_raw["bp"],
        "ask": quote_raw["ap"],
        "bid_size": quote_raw["bs"],
        "ask_size": quote_raw["as"],
        "quote_time": quote_raw["t"],
        "last_bar": {"open": bar.o, "high": bar.h, "low": bar.l, "close": bar.c, "volume": int(bar.v)},
    }
    print(f"\n  {sym}  bid={_fmt(result['bid'])}  ask={_fmt(result['ask'])}  "
          f"last_close={_fmt(bar.c)}  vol={int(bar.v):,}")
    return result


def get_bars(symbol, timeframe="1Day", limit=10):
    """
    Recent bars/candles.

    Args:
        symbol:    QQQ or SPY
        timeframe: 1Min, 5Min, 15Min, 1Hour, 1Day
        limit:     number of bars (default 10)
    """
    sym = _validate_symbol(symbol)
    end = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    bars_raw = api.get_bars(sym, timeframe, start=start, end=end, limit=limit, feed="iex")
    bars = []
    for b in bars_raw:
        bars.append({
            "time": str(b.t),
            "open": b.o, "high": b.h, "low": b.l, "close": b.c,
            "volume": int(b.v),
        })

    print(f"\n  {sym} {timeframe} bars (last {len(bars)}):")
    print(f"  {'Time':<28}{'Open':>10}{'High':>10}{'Low':>10}{'Close':>10}{'Volume':>14}")
    print(f"  {'─'*82}")
    for b in bars:
        print(f"  {b['time']:<28}{_fmt(b['open']):>10}{_fmt(b['high']):>10}"
              f"{_fmt(b['low']):>10}{_fmt(b['close']):>10}{b['volume']:>14,}")
    return bars


def get_historical_bars(symbol, timeframe="1Day", start=None, end=None):
    """
    Historical bars for a date range.

    Args:
        symbol:    QQQ or SPY
        timeframe: 1Min, 5Min, 15Min, 1Hour, 1Day
        start:     start date string, e.g. "2026-03-01"
        end:       end date string, e.g. "2026-03-20"
    """
    sym = _validate_symbol(symbol)
    if not start:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now().strftime("%Y-%m-%d")

    bars_raw = api.get_bars(sym, timeframe, start=start, end=end, feed="iex")
    bars = []
    for b in bars_raw:
        bars.append({
            "time": str(b.t),
            "open": b.o, "high": b.h, "low": b.l, "close": b.c,
            "volume": int(b.v),
        })

    print(f"\n  {sym} {timeframe} bars  {start} → {end}  ({len(bars)} bars):")
    print(f"  {'Time':<28}{'Open':>10}{'High':>10}{'Low':>10}{'Close':>10}{'Volume':>14}")
    print(f"  {'─'*82}")
    for b in bars:
        print(f"  {b['time']:<28}{_fmt(b['open']):>10}{_fmt(b['high']):>10}"
              f"{_fmt(b['low']):>10}{_fmt(b['close']):>10}{b['volume']:>14,}")
    return bars


# ─── Orders ──────────────────────────────────────────────────────────────────

def buy(symbol, qty, order_type="market", limit_price=None, time_in_force="day",
        stop_loss=None, take_profit=None):
    """
    Place a buy order with optional bracket (stop loss + take profit).

    Args:
        symbol:        QQQ or SPY
        qty:           number of shares
        order_type:    "market" or "limit"
        limit_price:   required if order_type="limit"
        time_in_force: "day" or "gtc"
        stop_loss:     stop loss price (broker-side protection)
        take_profit:   take profit price (broker-side exit)
    """
    return _place_order(symbol, qty, "buy", order_type, limit_price, time_in_force,
                        stop_loss, take_profit)


def sell(symbol, qty, order_type="market", limit_price=None, time_in_force="day",
         stop_loss=None, take_profit=None):
    """
    Place a sell order with optional bracket (stop loss + take profit).

    Args:
        symbol:        QQQ or SPY
        qty:           number of shares
        order_type:    "market" or "limit"
        limit_price:   required if order_type="limit"
        time_in_force: "day" or "gtc"
        stop_loss:     stop loss price (broker-side protection)
        take_profit:   take profit price (broker-side exit)
    """
    return _place_order(symbol, qty, "sell", order_type, limit_price, time_in_force,
                        stop_loss, take_profit)


def _place_order(symbol, qty, side, order_type, limit_price, time_in_force,
                 stop_loss=None, take_profit=None):
    sym = _validate_symbol(symbol)
    if order_type == "limit" and limit_price is None:
        raise ValueError("limit_price is required for limit orders")

    kwargs = dict(
        symbol=sym,
        qty=str(qty),
        side=side,
        type=order_type,
        time_in_force=time_in_force,
    )
    if limit_price is not None:
        kwargs["limit_price"] = str(limit_price)

    # Add bracket order support (broker-side stop loss + take profit)
    if stop_loss is not None or take_profit is not None:
        kwargs["order_class"] = "bracket"
        if stop_loss is not None:
            kwargs["stop_loss"] = {"stop_price": str(stop_loss)}
        if take_profit is not None:
            kwargs["take_profit"] = {"limit_price": str(take_profit)}

    order = api.submit_order(**kwargs)
    result = {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "type": order.type,
        "limit_price": order.limit_price,
        "time_in_force": order.time_in_force,
        "status": order.status,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "has_bracket": stop_loss is not None or take_profit is not None,
    }
    lp = f" @ {_fmt(limit_price)}" if limit_price else ""
    bracket_info = ""
    if stop_loss or take_profit:
        bracket_info = f"  [BRACKET: stop={_fmt(stop_loss) if stop_loss else '—'} target={_fmt(take_profit) if take_profit else '—'}]"
    print(f"\n  ✓ {side.upper()} {qty} {sym} {order_type}{lp}  "
          f"tif={time_in_force}  status={order.status}  id={order.id}{bracket_info}")
    log_trade(result, action=side)
    return result


# ─── Positions ───────────────────────────────────────────────────────────────

def get_positions():
    """Return all open QQQ/SPY positions."""
    positions = api.list_positions()
    relevant = [p for p in positions if p.symbol in ALLOWED_SYMBOLS]

    results = []
    for p in relevant:
        results.append({
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
        })

    if not results:
        print("\n  No open positions in QQQ/SPY.")
    else:
        print(f"\n  {'Symbol':<8}{'Qty':>8}{'Entry':>12}{'Current':>12}{'P&L':>14}{'P&L %':>10}")
        print(f"  {'─'*64}")
        for r in results:
            pnl_sign = "+" if r["unrealized_pl"] >= 0 else ""
            print(f"  {r['symbol']:<8}{r['qty']:>8.0f}{_fmt(r['avg_entry']):>12}"
                  f"{_fmt(r['current_price']):>12}{pnl_sign}{_fmt(r['unrealized_pl']):>13}"
                  f"{r['unrealized_plpc']:>+9.2%}")
    return results


def close_position(symbol):
    """Close entire position for a symbol."""
    sym = _validate_symbol(symbol)
    try:
        pos = api.get_position(sym)
    except Exception:
        print(f"\n  No open position in {sym}.")
        return None

    api.close_position(sym)
    pnl = float(pos.unrealized_pl)
    print(f"\n  ✓ Closed {pos.qty} shares of {sym}  P&L: {'+' if pnl >= 0 else ''}{_fmt(pnl)}")
    result = {"symbol": sym, "qty_closed": float(pos.qty), "pnl": pnl, "side": "close"}
    log_trade(result, action="close")
    return result


# ─── Open Orders / Cancel ────────────────────────────────────────────────────

def get_open_orders():
    """Return all open orders for QQQ/SPY."""
    orders = api.list_orders(status="open")
    relevant = [o for o in orders if o.symbol in ALLOWED_SYMBOLS]

    results = []
    for o in relevant:
        results.append({
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "type": o.type,
            "qty": o.qty,
            "limit_price": o.limit_price,
            "time_in_force": o.time_in_force,
            "status": o.status,
            "created_at": str(o.created_at),
        })

    if not results:
        print("\n  No open orders for QQQ/SPY.")
    else:
        print(f"\n  {'Symbol':<8}{'Side':<6}{'Type':<8}{'Qty':>6}{'Limit':>12}{'TIF':<6}{'Status':<12}{'ID'}")
        print(f"  {'─'*90}")
        for r in results:
            lp = _fmt(r["limit_price"]) if r["limit_price"] else "—"
            print(f"  {r['symbol']:<8}{r['side']:<6}{r['type']:<8}{r['qty']:>6}"
                  f"{lp:>12}  {r['time_in_force']:<4}  {r['status']:<10}  {r['id']}")
    return results


def cancel_order(order_id):
    """Cancel a specific order by ID."""
    api.cancel_order(order_id)
    print(f"\n  ✓ Cancelled order {order_id}")
    log_trade({"order_id": order_id, "symbol": "UNK"}, action="cancel")


def cancel_all_orders():
    """Cancel all open orders."""
    api.cancel_all_orders()
    print("\n  ✓ All open orders cancelled.")


# ─── Recent Fills ────────────────────────────────────────────────────────────

def get_recent_fills(limit=10):
    """Return recently filled orders for QQQ/SPY."""
    orders = api.list_orders(status="closed", limit=limit)
    relevant = [o for o in orders if o.symbol in ALLOWED_SYMBOLS]

    results = []
    for o in relevant:
        results.append({
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "qty": o.filled_qty,
            "filled_avg_price": o.filled_avg_price,
            "status": o.status,
            "filled_at": str(o.filled_at) if o.filled_at else None,
        })

    if not results:
        print("\n  No recent fills for QQQ/SPY.")
    else:
        print(f"\n  {'Symbol':<8}{'Side':<6}{'Qty':>6}{'Fill Price':>14}{'Status':<12}{'Filled At'}")
        print(f"  {'─'*70}")
        for r in results:
            fp = _fmt(r["filled_avg_price"]) if r["filled_avg_price"] else "—"
            print(f"  {r['symbol']:<8}{r['side']:<6}{r['qty']:>6}{fp:>14}  {r['status']:<10}  {r['filled_at'] or '—'}")
    return results


# ─── Quick test on direct run ────────────────────────────────────────────────

if __name__ == "__main__":
    print("Verifying Alpaca connection and capabilities...\n")
    get_account()
    get_quote("SPY")
    get_quote("QQQ")
    get_bars("SPY", "1Day", limit=5)
    get_positions()
    get_open_orders()
    get_recent_fills()
    print("\n  All functions operational.")
