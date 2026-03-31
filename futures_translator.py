#!/usr/bin/env python3
"""
Futures signal translator.

Converts SPY/QQQ signals to E-mini futures (ES/NQ) signals.
Outputs futures-ready signals to journal for manual execution or API integration.
"""

from datetime import datetime
from pathlib import Path
import json


# Contract specifications
FUTURES_SPECS = {
    "ES": {
        "name": "E-mini S&P 500",
        "tracks": "SPY",
        "multiplier": 10.0,      # ES ≈ SPY × 10
        "tick_size": 0.25,       # Quarter points
        "tick_value": 12.50,     # $12.50 per tick
        "point_value": 50.0,     # $50 per point
        "typical_margin": 12000, # Per contract
        "symbol": "ES",
    },
    "NQ": {
        "name": "E-mini Nasdaq 100",
        "tracks": "QQQ",
        "multiplier": 40.0,      # NQ ≈ QQQ × 40
        "tick_size": 0.25,
        "tick_value": 5.0,       # $5 per tick
        "point_value": 20.0,     # $20 per point
        "typical_margin": 18000,
        "symbol": "NQ",
    },
    "MES": {
        "name": "Micro E-mini S&P 500",
        "tracks": "SPY",
        "multiplier": 10.0,
        "tick_size": 0.25,
        "tick_value": 1.25,      # 1/10th of ES
        "point_value": 5.0,      # 1/10th of ES
        "typical_margin": 1200,
        "symbol": "MES",
    },
    "MNQ": {
        "name": "Micro E-mini Nasdaq 100",
        "tracks": "QQQ",
        "multiplier": 40.0,
        "tick_size": 0.25,
        "tick_value": 0.5,       # 1/10th of NQ
        "point_value": 2.0,      # 1/10th of NQ
        "typical_margin": 1800,
        "symbol": "MNQ",
    }
}


def etf_to_futures_price(etf_price: float, etf_symbol: str) -> dict:
    """
    Convert ETF price to futures price.

    Args:
        etf_price: Price of ETF (e.g., SPY @ 635.69)
        etf_symbol: "SPY" or "QQQ"

    Returns:
        {
            "ES": 6356.75,
            "MES": 6356.75,
            "NQ": None,  # if QQQ
        }
    """
    result = {}

    for futures_symbol, spec in FUTURES_SPECS.items():
        if spec["tracks"] == etf_symbol:
            # ES = SPY × 10, round to tick size
            futures_price = etf_price * spec["multiplier"]
            # Round to nearest tick (0.25)
            futures_price = round(futures_price / spec["tick_size"]) * spec["tick_size"]
            result[futures_symbol] = futures_price

    return result


def calculate_futures_risk_reward(entry: float, stop: float, target: float,
                                  futures_symbol: str) -> dict:
    """
    Calculate risk/reward in dollars for futures contract.

    Args:
        entry: Futures entry price
        stop: Futures stop price
        target: Futures target price
        futures_symbol: "ES", "NQ", "MES", or "MNQ"

    Returns:
        {
            "risk_points": float,
            "risk_dollars": float,
            "reward_points": float,
            "reward_dollars": float,
            "risk_reward_ratio": float
        }
    """
    spec = FUTURES_SPECS[futures_symbol]

    risk_points = abs(entry - stop)
    reward_points = abs(target - entry)

    risk_dollars = risk_points * spec["point_value"]
    reward_dollars = reward_points * spec["point_value"]

    rr_ratio = reward_dollars / risk_dollars if risk_dollars > 0 else 0

    return {
        "risk_points": round(risk_points, 2),
        "risk_dollars": round(risk_dollars, 2),
        "reward_points": round(reward_points, 2),
        "reward_dollars": round(reward_dollars, 2),
        "risk_reward_ratio": round(rr_ratio, 2)
    }


def calculate_position_size(account_equity: float, risk_pct: float,
                            risk_per_contract: float) -> int:
    """
    Calculate number of contracts based on risk management.

    Args:
        account_equity: Total account value
        risk_pct: Risk percentage (e.g., 0.02 for 2%)
        risk_per_contract: Dollar risk per contract

    Returns:
        Number of contracts to trade
    """
    total_risk = account_equity * risk_pct
    contracts = int(total_risk / risk_per_contract)
    return max(1, contracts)  # Minimum 1 contract


def translate_signal(signal: dict, account_equity: float = 25000,
                     risk_pct: float = 0.02, use_micro: bool = True) -> dict:
    """
    Translate SPY/QQQ signal to futures signal.

    Args:
        signal: Agent signal dict with entry, stop, target, side, symbol
        account_equity: Account size for position sizing
        risk_pct: Risk per trade (default 2%)
        use_micro: Use micro contracts (MES/MNQ) vs full (ES/NQ)

    Returns:
        Futures signal dict ready for execution
    """
    etf_symbol = signal["symbol"]
    side = signal["side"]

    # Get futures symbol
    if etf_symbol == "SPY":
        futures_symbol = "MES" if use_micro else "ES"
    elif etf_symbol == "QQQ":
        futures_symbol = "MNQ" if use_micro else "NQ"
    else:
        raise ValueError(f"Unknown ETF symbol: {etf_symbol}")

    spec = FUTURES_SPECS[futures_symbol]

    # Convert prices
    entry_futures = etf_to_futures_price(signal["entry"], etf_symbol)[futures_symbol]
    stop_futures = etf_to_futures_price(signal["stop"], etf_symbol)[futures_symbol]
    target_futures = etf_to_futures_price(signal["target"], etf_symbol)[futures_symbol]

    # Calculate risk/reward
    rr = calculate_futures_risk_reward(entry_futures, stop_futures, target_futures,
                                       futures_symbol)

    # Position sizing
    contracts = calculate_position_size(account_equity, risk_pct, rr["risk_dollars"])

    # Total risk/reward
    total_risk = rr["risk_dollars"] * contracts
    total_reward = rr["reward_dollars"] * contracts

    return {
        "timestamp": datetime.now().isoformat(),
        "original_signal": {
            "symbol": etf_symbol,
            "side": side,
            "entry": signal["entry"],
            "stop": signal["stop"],
            "target": signal["target"],
            "score": signal.get("score", 0),
            "setup": signal.get("setup", "unknown"),
        },
        "futures_signal": {
            "symbol": futures_symbol,
            "contract_name": spec["name"],
            "side": side,
            "entry": entry_futures,
            "stop": stop_futures,
            "target": target_futures,
            "risk_per_contract": rr["risk_dollars"],
            "reward_per_contract": rr["reward_dollars"],
            "risk_reward_ratio": rr["risk_reward_ratio"],
            "recommended_contracts": contracts,
            "total_risk": round(total_risk, 2),
            "total_reward": round(total_reward, 2),
            "margin_required": spec["typical_margin"] * contracts,
        },
        "execution_notes": {
            "order_type": "LIMIT",
            "entry_instructions": f"SELL {contracts} {futures_symbol} @ {entry_futures} LIMIT" if side == "sell" else f"BUY {contracts} {futures_symbol} @ {entry_futures} LIMIT",
            "stop_loss_instructions": f"Stop @ {stop_futures} (risk ${total_risk:.2f})",
            "take_profit_instructions": f"Target @ {target_futures} (reward ${total_reward:.2f})",
            "bracket_order": f"Use OCO bracket: Stop @ {stop_futures}, Target @ {target_futures}",
        }
    }


def log_futures_signal(signal: dict, output_file: Path = None):
    """
    Log futures signal to JSONL file for tracking.

    Args:
        signal: Translated futures signal
        output_file: Path to output file (default: journal/futures_signals.jsonl)
    """
    if output_file is None:
        output_file = Path(__file__).parent / "journal" / "futures_signals.jsonl"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "a") as f:
        f.write(json.dumps(signal, default=str) + "\n")

    print(f"  📋 Futures signal logged to {output_file}")


def print_futures_signal(signal: dict):
    """Pretty-print futures signal for manual execution."""
    fs = signal["futures_signal"]
    ex = signal["execution_notes"]
    orig = signal["original_signal"]

    print("\n" + "="*72)
    print("  FUTURES SIGNAL")
    print("="*72)

    print(f"\n  📊 Original Signal:")
    print(f"     {orig['symbol']} {orig['side'].upper()}")
    print(f"     Score: {orig['score']}")
    print(f"     Setup: {orig['setup']}")

    print(f"\n  🎯 Futures Translation:")
    print(f"     Contract: {fs['symbol']} ({fs['contract_name']})")
    print(f"     Side: {fs['side'].upper()}")
    print(f"     Entry: {fs['entry']:.2f}")
    print(f"     Stop: {fs['stop']:.2f}")
    print(f"     Target: {fs['target']:.2f}")

    print(f"\n  💰 Risk/Reward:")
    print(f"     Per Contract: ${fs['risk_per_contract']:.2f} risk / ${fs['reward_per_contract']:.2f} reward")
    print(f"     R:R Ratio: {fs['risk_reward_ratio']:.2f}:1")
    print(f"     Contracts: {fs['recommended_contracts']}")
    print(f"     Total Risk: ${fs['total_risk']:.2f}")
    print(f"     Total Reward: ${fs['total_reward']:.2f}")
    print(f"     Margin Required: ${fs['margin_required']:,}")

    print(f"\n  📋 Execution Instructions:")
    print(f"     {ex['entry_instructions']}")
    print(f"     {ex['stop_loss_instructions']}")
    print(f"     {ex['take_profit_instructions']}")
    print(f"\n     {ex['bracket_order']}")

    print("\n" + "="*72 + "\n")


if __name__ == "__main__":
    """Test futures translation."""

    # Example SPY signal from agent
    test_signal = {
        "symbol": "SPY",
        "side": "sell",
        "entry": 635.69,
        "stop": 636.00,
        "target": 634.80,
        "score": 97,
        "setup": "FVG_entry",
    }

    print("="*72)
    print("FUTURES SIGNAL TRANSLATOR - TEST")
    print("="*72)

    # Translate to micro futures
    print("\n🔄 Translating to MICRO futures (MES)...")
    signal_micro = translate_signal(test_signal, account_equity=25000, use_micro=True)
    print_futures_signal(signal_micro)

    # Translate to full futures
    print("\n🔄 Translating to FULL futures (ES)...")
    signal_full = translate_signal(test_signal, account_equity=25000, use_micro=False)
    print_futures_signal(signal_full)

    # Log it
    log_futures_signal(signal_micro)

    print("✅ Translation complete!")
