# Broker-Side Stop Loss Implementation

## Summary

As of 2026-03-25, the agent now uses **Alpaca bracket orders** for all trades, providing broker-side stop-loss and take-profit protection. This means stops are enforced by Alpaca even when the agent is not running.

## What Changed

### Before (Mental Stops)
- Agent placed entry orders only
- Stop losses calculated in agent.py but NOT sent to broker
- Position management ran every cycle to manually close positions
- **Risk**: If agent crashed/stopped, positions had NO stop protection

### After (Broker-Side Stops)
- Agent places bracket orders (entry + stop + target) 
- Alpaca automatically closes positions when stop/target is hit
- **Protection**: Stops work 24/7 even if agent is offline

## Implementation Details

### 1. Modified `alpaca_trader.py`
Added bracket order support to `buy()` and `sell()` functions:

```python
buy("SPY", qty=10, order_type="limit", limit_price=650.00,
    stop_loss=648.00,      # ← broker-side stop
    take_profit=654.00)    # ← broker-side target
```

When `stop_loss` or `take_profit` are provided:
- `order_class="bracket"` is set
- Alpaca creates 3 orders: entry + stop + target
- Stop/target execute automatically on the broker side

### 2. Modified `agent.py`
- Updated trade execution (line ~1015) to pass stop/target prices
- Updated `manage_positions()` to recognize broker-side stops
- Position management now acts as backup only

### 3. Position Management Behavior

New positions with bracket orders:
- Alpaca handles stop/target automatically
- `manage_positions()` monitors but doesn't manually close
- Shows status: `[BROKER-SIDE STOPS ACTIVE]`

Legacy positions without brackets:
- `manage_positions()` closes manually as before
- Shows status: `[manual stops]`

## Trade Example

When agent places a QQQ short:

```
Entry:       $585.31
Stop Loss:   $587.77  ← broker-side order placed
Take Profit: $580.27  ← broker-side order placed
```

If price hits $587.77:
- Alpaca automatically closes position
- No agent intervention required
- Works even if agent is offline

## How to Verify

Check open orders after a trade:
```python
python3 -c "from alpaca_trader import get_open_orders; get_open_orders()"
```

You should see:
1. Main order (filled)
2. Stop order (pending)
3. Take profit order (pending)

## Guardrails Unchanged

The existing guardrails still apply:
- Max 2 trades/day
- 5% position size
- 2:1 minimum R:R
- 2% daily loss limit
- 30-min cooldown after loss
- Stop = 1.5× ATR from entry

## Closed Position

The QQQ short from 2026-03-24 (entry $585.32, stop $587.77) was manually closed at loss of -$22.83 before bracket implementation. Future trades will have broker-side protection from the start.

## Testing

To test in dry-run mode:
```bash
python3 agent.py --dry-run
```

To test live (paper trading):
```bash
python3 agent.py --loop --interval 2
```

Monitor positions and stops:
```bash
python3 alpaca_trader.py
```
