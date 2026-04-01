#!/usr/bin/env python3
"""
IBKR futures order executor.

Integrates with agent to place futures orders via Interactive Brokers API.
"""

from datetime import datetime
from ib_insync import IB, Future, LimitOrder, MarketOrder
from pathlib import Path
import json


class IBKRExecutor:
    """IBKR futures order executor."""

    def __init__(self, host='127.0.0.1', port=7497, client_id=1, paper_trading=True):
        """
        Initialize IBKR connection.

        Args:
            host: TWS host (default localhost)
            port: TWS port (7497 for paper, 7496 for live)
            client_id: Unique client ID
            paper_trading: True for paper account, False for live
        """
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.paper_trading = paper_trading
        self.connected = False

    def connect(self):
        """Connect to IBKR TWS."""
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            mode = "PAPER" if self.paper_trading else "LIVE"
            print(f"  ✅ Connected to IBKR ({mode} trading)")
            return True
        except Exception as e:
            print(f"  ❌ IBKR connection failed: {e}")
            print(f"     Make sure TWS is running and API is enabled")
            return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            print("  🔌 Disconnected from IBKR")

    def get_mes_contract(self, expiry='202606'):
        """
        Get MES (Micro E-mini S&P 500) contract.

        Args:
            expiry: Contract expiry (YYYYMM format, e.g., '202606' for June 2026)

        Returns:
            Qualified Future contract
        """
        contract = Future('MES', expiry, 'CME')
        self.ib.qualifyContracts(contract)
        return contract

    def get_mnq_contract(self, expiry='202606'):
        """
        Get MNQ (Micro E-mini Nasdaq 100) contract.

        Args:
            expiry: Contract expiry (YYYYMM format)

        Returns:
            Qualified Future contract
        """
        contract = Future('MNQ', expiry, 'CME')
        self.ib.qualifyContracts(contract)
        return contract

    def get_mgc_contract(self, expiry='202606'):
        """
        Get MGC (Micro Gold) contract.

        Args:
            expiry: Contract expiry (YYYYMM format, e.g., '202606' for June 2026)

        Returns:
            Qualified Future contract
        """
        contract = Future('MGC', expiry, 'COMEX')
        self.ib.qualifyContracts(contract)
        return contract

    def place_bracket_order(self, signal: dict) -> dict:
        """
        Place bracket order (entry + stop + target) from agent signal.

        Args:
            signal: Futures signal dict from futures_translator.py

        Returns:
            {
                "success": bool,
                "order_ids": [entry_id, stop_id, target_id],
                "message": str
            }
        """
        if not self.connected:
            return {"success": False, "message": "Not connected to IBKR"}

        try:
            fs = signal['futures_signal']

            # Get contract
            if fs['symbol'] == 'MES':
                contract = self.get_mes_contract()
            elif fs['symbol'] == 'MNQ':
                contract = self.get_mnq_contract()
            elif fs['symbol'] == 'MGC':
                contract = self.get_mgc_contract()
            elif fs['symbol'] == 'ES':
                contract = Future('ES', '202606', 'CME')
                self.ib.qualifyContracts(contract)
            elif fs['symbol'] == 'NQ':
                contract = Future('NQ', '202606', 'CME')
                self.ib.qualifyContracts(contract)
            elif fs['symbol'] == 'GC':
                contract = Future('GC', '202606', 'COMEX')
                self.ib.qualifyContracts(contract)
            else:
                return {"success": False, "message": f"Unknown symbol: {fs['symbol']}"}

            # Create bracket order
            action = 'SELL' if fs['side'] == 'sell' else 'BUY'

            bracket = self.ib.bracketOrder(
                action=action,
                quantity=fs['recommended_contracts'],
                limitPrice=fs['entry'],
                takeProfitPrice=fs['target'],
                stopLossPrice=fs['stop']
            )

            # Place all orders
            trades = []
            for order in bracket:
                trade = self.ib.placeOrder(contract, order)
                trades.append(trade)

            # Get order IDs
            order_ids = [t.order.orderId for t in trades]

            mode = "PAPER" if self.paper_trading else "LIVE"
            print(f"\n  ✅ {mode} BRACKET ORDER PLACED")
            print(f"     {action} {fs['recommended_contracts']} {fs['symbol']}")
            print(f"     Entry: {fs['entry']}")
            print(f"     Stop: {fs['stop']}")
            print(f"     Target: {fs['target']}")
            print(f"     Order IDs: {order_ids}")

            return {
                "success": True,
                "order_ids": order_ids,
                "message": f"Bracket order placed: {order_ids}",
                "trades": trades
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Order failed: {e}"
            }

    def get_account_summary(self) -> dict:
        """Get account summary."""
        if not self.connected:
            return {}

        try:
            summary = self.ib.accountSummary()

            result = {}
            for item in summary:
                result[item.tag] = item.value

            return result

        except Exception as e:
            print(f"  ⚠ Could not fetch account summary: {e}")
            return {}

    def get_positions(self) -> dict:
        """
        Get open positions.

        Returns:
            Dict mapping contract symbol to position data:
            {
                "MES202606": {
                    "position": 10,  # positive = long, negative = short
                    "avgCost": 6357.5,
                    "marketValue": 63575.0,
                    "unrealizedPnL": 125.0
                }
            }
        """
        if not self.connected:
            return {}

        try:
            positions = self.ib.positions()

            result = {}
            for pos in positions:
                contract_id = f"{pos.contract.symbol}{pos.contract.lastTradeDateOrContractMonth}"
                result[contract_id] = {
                    "position": pos.position,
                    "avgCost": pos.avgCost,
                    "marketValue": pos.marketValue,
                    "unrealizedPnL": pos.unrealizedPnL,
                    "contract": pos.contract
                }

            return result

        except Exception as e:
            print(f"  ⚠ Could not fetch positions: {e}")
            return {}

    def cancel_all_orders(self, contract_symbol: str = None):
        """
        Cancel all open orders, optionally filtered by contract symbol.

        Args:
            contract_symbol: If provided, only cancel orders for this contract (e.g., "MES202606")

        Returns:
            Number of orders cancelled
        """
        if not self.connected:
            return 0

        try:
            open_trades = self.ib.openTrades()

            cancelled_count = 0
            for trade in open_trades:
                # Filter by contract if specified
                if contract_symbol:
                    trade_contract_id = f"{trade.contract.symbol}{trade.contract.lastTradeDateOrContractMonth}"
                    if trade_contract_id != contract_symbol:
                        continue

                # Cancel order
                self.ib.cancelOrder(trade.order)
                cancelled_count += 1

            if cancelled_count > 0:
                print(f"  ✓ Cancelled {cancelled_count} open orders")

            return cancelled_count

        except Exception as e:
            print(f"  ⚠ Could not cancel orders: {e}")
            return 0

    def close_position(self, contract_symbol: str):
        """
        Close a position with a market order.

        Args:
            contract_symbol: Contract identifier (e.g., "MES202606")

        Returns:
            {
                "success": bool,
                "status": str,
                "filled_price": float or None
            }
        """
        if not self.connected:
            return {"success": False, "status": "Not connected"}

        try:
            # Get position
            positions = self.get_positions()

            if contract_symbol not in positions:
                return {"success": False, "status": f"No position found for {contract_symbol}"}

            pos_data = positions[contract_symbol]
            position_size = pos_data["position"]
            contract = pos_data["contract"]

            if position_size == 0:
                return {"success": False, "status": "Position size is 0"}

            # Determine action (opposite of current position)
            action = 'SELL' if position_size > 0 else 'BUY'
            quantity = abs(position_size)

            # Place market order to close
            order = MarketOrder(action, quantity)

            trade = self.ib.placeOrder(contract, order)

            # Wait for fill (up to 10 seconds)
            import time
            for _ in range(20):
                self.ib.sleep(0.5)
                if trade.isDone():
                    break

            if trade.isDone():
                filled_price = trade.orderStatus.avgFillPrice
                return {
                    "success": True,
                    "status": "filled",
                    "filled_price": filled_price,
                    "quantity": quantity
                }
            else:
                return {
                    "success": False,
                    "status": f"Order not filled: {trade.orderStatus.status}",
                    "trade": trade
                }

        except Exception as e:
            return {
                "success": False,
                "status": f"Close failed: {e}"
            }


def test_connection():
    """Test IBKR connection."""
    print("\n" + "="*72)
    print("IBKR CONNECTION TEST")
    print("="*72)

    executor = IBKRExecutor(paper_trading=True)

    if executor.connect():
        print("\n  📊 Account Summary:")
        summary = executor.get_account_summary()

        if summary:
            print(f"     Net Liquidation: ${summary.get('NetLiquidation', 'N/A')}")
            print(f"     Available Funds: ${summary.get('AvailableFunds', 'N/A')}")
            print(f"     Buying Power: ${summary.get('BuyingPower', 'N/A')}")

        print("\n  📈 Open Positions:")
        positions = executor.get_positions()
        if positions:
            for pos in positions:
                print(f"     {pos.contract.symbol}: {pos.position} @ ${pos.avgCost:.2f}")
        else:
            print("     No open positions")

        executor.disconnect()

        print("\n✅ Connection test successful!")
        return True
    else:
        print("\n❌ Connection test failed")
        print("\nTroubleshooting:")
        print("1. Is TWS running?")
        print("2. Is API enabled? (File → Global Configuration → API → Enable ActiveX)")
        print("3. Is port 7497 allowed? (Check API settings)")
        print("4. Try restarting TWS")
        return False


if __name__ == "__main__":
    """Test IBKR executor."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Just test connection
        test_connection()
    else:
        # Test full order placement
        print("\n" + "="*72)
        print("IBKR EXECUTOR TEST - BRACKET ORDER")
        print("="*72)
        print("\n⚠️  This will place a PAPER TRADING order on IBKR")
        print("    Make sure TWS is running in PAPER TRADING mode\n")

        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

        # Create test signal (from futures_translator output)
        test_signal = {
            "futures_signal": {
                "symbol": "MES",
                "side": "sell",
                "entry": 6357.0,
                "stop": 6360.0,
                "target": 6348.0,
                "recommended_contracts": 1,  # Just 1 for testing
            }
        }

        executor = IBKRExecutor(paper_trading=True)

        if executor.connect():
            print("\n  📋 Placing test bracket order...")
            result = executor.place_bracket_order(test_signal)

            if result['success']:
                print(f"\n  ✅ {result['message']}")
                print(f"\n  Check TWS to see the orders!")
            else:
                print(f"\n  ❌ {result['message']}")

            executor.disconnect()
        else:
            print("\n  ❌ Could not connect to IBKR")
