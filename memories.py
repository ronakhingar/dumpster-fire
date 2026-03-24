"""
Trading knowledge base — distilled from TTT Mastermind sessions,
A+ Trade Rating Guide, Liquidity playbooks, and TA notes.

This file is the single source of truth the agent uses for:
  - A+ setup definitions and scoring
  - Guardrails and risk rules
  - Killzone / macro timing windows
  - Liquidity concepts translated into detectable bar patterns

Sources read:
  1. The Traveling Trader - A+ Trade Rating Guide (ICT '22, Unicorn, iFVG models)
  2. Liquidity Magnet Guide (sweep → trap → reversal model)
  3. Liquidity Reversal Playbook (EMA/VWAP confirmation after sweep)
  4. Liquidity Trap Flowchart (6-phase execution flow)
  5. Technical_Analysis.rtf (EMA 21 entries, SMA S/R, RSI overbought/oversold)
  6. ICT Killzone Pine Script (session windows: Asia, London, NY AM/PM)
  7. TTT How to Research a Stock / How to Read a 10-K (fundamental context)
  8. Mastermind 9 & 10 session chats (MSS, FVG, OB, SMT, macro timing)
"""

# ─── Killzone Windows (ET) ───────────────────────────────────────────────────

KILLZONES = {
    "asia":     {"start": "20:00", "end": "00:00", "label": "Asia"},
    "london":   {"start": "02:00", "end": "05:00", "label": "London"},
    "ny_am":    {"start": "09:30", "end": "11:00", "label": "NY AM"},
    "ny_lunch": {"start": "12:00", "end": "13:00", "label": "NY Lunch"},
    "ny_pm":    {"start": "13:30", "end": "16:00", "label": "NY PM"},
}

# Macro windows (20-min high-probability algo bursts)
MACRO_WINDOWS = [
    ("09:50", "10:10"),
    ("10:50", "11:10"),
    ("13:50", "14:10"),
    ("15:15", "15:45"),
]

# ─── A+ Setup Scoring System ─────────────────────────────────────────────────
# Each criterion adds points. Minimum 80/100 to qualify as A+.

SCORE_CRITERIA = {
    "liquidity_sweep":       20,  # Price wicked past key H/L then reversed
    "market_structure_shift": 20,  # Full body close through prior structure
    "fvg_present":           15,  # Fair Value Gap formed after MSS
    "displacement":          10,  # Large-body candle on the MSS leg
    "killzone_timing":       10,  # Trade occurs during a killzone
    "premium_discount":      10,  # Entry in discount (long) or premium (short)
    "ema_confirmation":       5,  # 9 EMA reclaim / crossover supports direction
    "vwap_confluence":        5,  # VWAP aligns with trade direction
    "rsi_not_extreme":        5,  # RSI not already overbought/oversold in entry direction
}

A_PLUS_THRESHOLD = 80

# ─── Guardrails ──────────────────────────────────────────────────────────────

GUARDRAILS = {
    "max_trades_per_day":       2,
    "max_position_pct":         0.05,   # 5% of equity per trade
    "min_risk_reward":          2.0,
    "daily_loss_limit_pct":     0.02,   # 2% max daily drawdown
    "stop_atr_multiplier":      1.5,    # SL = 1.5 × ATR from entry
    "require_liquidity_sweep":  True,
    "require_mss":              True,
    "require_killzone":         True,   # Only trade during killzones
    "require_displacement":     True,
    "cooldown_after_loss_min":  30,     # Wait 30 min after a losing trade
}

# ─── Pattern Detection Thresholds ────────────────────────────────────────────

DETECTION = {
    "sweep_wick_pct":       0.002,  # Wick must extend ≥0.2% past prior H/L
    "displacement_body_mult": 2.0,  # Body must be ≥2× avg body of last 10 bars
    "fvg_min_gap_pct":      0.001,  # FVG gap must be ≥0.1% of price
    "rejection_wick_ratio":  2.0,   # Wick ≥2× body = rejection candle
    "mss_lookback":          5,     # Look back N bars for structure high/low
}

# ─── Concept Translations (ICT → detectable bar patterns) ────────────────────

SETUP_MODELS = {
    "ict_22": {
        "name": "ICT 2022 Model",
        "flow": [
            "1. Liquidity sweep of key H/L (PDH/PDL, session H/L, equal H/L)",
            "2. Market Structure Shift with displacement (full body close)",
            "3. Retrace into FVG created during the MSS leg",
            "4. FVG must be in discount for longs, premium for shorts",
            "5. Target opposing liquidity (next key H/L)",
        ],
        "min_rr": 2.0,
    },
    "liquidity_trap": {
        "name": "Liquidity Trap Reversal",
        "flow": [
            "1. Price sweeps equal highs/lows or session extremes",
            "2. Rejection wick forms (large wick, small body)",
            "3. 9 EMA flattens or curls opposite to sweep direction",
            "4. VWAP reclaim confirms reversal",
            "5. Enter on first pullback after confirmation",
        ],
        "min_rr": 2.0,
        "targets": ["T1: VWAP retest", "T2: Opposing liquidity", "T3: Full unwind"],
    },
    "ema_pullback": {
        "name": "EMA Pullback (from TA notes)",
        "flow": [
            "1. Stock in clear uptrend (price > EMA 21 > EMA 50)",
            "2. Candle touches or approaches EMA 21",
            "3. RSI not overbought (< 65)",
            "4. Entry at EMA 21 touch, SL below EMA 21",
        ],
        "min_rr": 2.0,
    },
}

# ─── Hard Rules (from the playbooks) ─────────────────────────────────────────

HARD_RULES = [
    "No sweep = No trade",
    "No confirmation = No entry",
    "No displacement = No trade",
    "Minimum 2:1 risk-reward or skip",
    "Stop loss behind sweep extension or structure invalidation",
    "Exit fully if sweep zone breaks again and holds",
    "One model, one ticker until mastery",
    "Skip choppy / unclear bias days",
    "Never long in premium, never short in discount",
]

# ─── Psychology Reminders ─────────────────────────────────────────────────────

PSYCHOLOGY = [
    "Patience after MSS — price may retrace deeper before moving your way",
    "Knowing when NOT to trade is as important as knowing when to trade",
    "Overtrading is the #1 killer — stick to A+ setups only",
    "News is just a reason to seek liquidity, not a separate system",
    "If daily bias is unclear, sit out — 'go golfing'",
    "Stick to one model until mastery before adding complexity",
]
