#!/bin/bash
# Quick manual scan of real opportunities

echo "=== LONG-TERM IDEAS (Real Tickers Only) ==="
echo
cat trade_categories/long_term_ideas.jsonl | \
  jq -r 'select(.raw_text | test("NVDA|GOOG|AMZN|META|MSFT|PLTR|HOOD|NVO|ASML|IGV|TLT")) | 
         "Ticker: " + ([.raw_text | scan("NVDA|GOOG|AMZN|META|MSFT|PLTR|HOOD|NVO|ASML|IGV|TLT")] | unique | join(", ")) + "\n" + 
         "Message: " + .raw_text[:150] + "...\n"'

echo
echo "=== CONDITIONAL SETUPS (SPY/QQQ at 200MA, etc.) ==="
echo
cat trade_categories/conditional_setups.jsonl | \
  jq -r 'select(.raw_text | test("200MA|200 MA|support|resistance")) | 
         "Setup: " + .raw_text[:150] + "...\n"' | head -20

echo
echo "=== ACTIVE TRADES (Recent Activity) ==="
echo
cat trade_categories/active_trades.jsonl | \
  jq -r '"Trade: " + .raw_text[:100] + "..."' | head -10
