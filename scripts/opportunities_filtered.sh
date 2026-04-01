#!/bin/bash
# Filtered opportunities report with clean tickers only

echo "═══════════════════════════════════════════════════════════════"
echo "  ACTIONABLE TRADE OPPORTUNITIES"
echo "═══════════════════════════════════════════════════════════════"
echo

echo "📊 LONG-TERM VALUE PLAYS"
echo "─────────────────────────────────────────────────────────────"
cat trade_categories/long_term_ideas.jsonl | jq -r '
  select(.tickers | length > 0) |
  "
Tickers: " + (.tickers | join(", ")) + "
Date: " + (.timestamp[:10]) + "
Signal: " + .raw_text[:200] + "..."
' | head -50

echo
echo "📈 CONDITIONAL SETUPS (Monitor These)"
echo "─────────────────────────────────────────────────────────────"
cat trade_categories/conditional_setups.jsonl | jq -r '
  select(.tickers | length > 0) |
  "
Tickers: " + (.tickers | join(", ")) + "
Setup: " + .raw_text[:150] + "..."
' | head -40

echo
echo "💰 ACTIVE POSITIONS (Recent Activity)"
echo "─────────────────────────────────────────────────────────────"
cat trade_categories/active_trades.jsonl | jq -r '
  select(.tickers | length > 0) |
  "
Ticker: " + (.tickers | join(", ")) + "
Update: " + .raw_text[:100] + "..."
' | head -30

echo
echo "═══════════════════════════════════════════════════════════════"
